from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import include, path
from django.utils import timezone
from rest_framework.test import APIClient
from types import SimpleNamespace
from unittest.mock import patch

from core.models import User
from notification.models import Notification, NotificationDelivery, PushDevice
from notification.tasks import deliver_notification_task, recover_notification_deliveries
from notification.views import create_notification, notify_staff


urlpatterns = [
    path("notifications/", include("notification.urls")),
]


@override_settings(ROOT_URLCONF=__name__)
class NotificationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="pass12345",
            first_name="Buyer",
            last_name="One",
            gender="male",
            phone1="+2348012345678",
        )
        self.staff = User.objects.create_staffuser(
            email="staff@example.com",
            password="pass12345",
            first_name="Staff",
            last_name="One",
            gender="female",
            phone1="+2348012345679",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_user_can_list_and_count_own_notifications(self):
        create_notification(
            recipient=self.user,
            verb="order shipped",
            description="Your order is on the way.",
            data={"event": "order_shipped"},
        )
        create_notification(
            recipient=self.staff,
            verb="staff only",
            description="Hidden from buyer.",
        )

        response = self.client.get("/notifications/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["verb"], "order shipped")

        counts = self.client.get("/notifications/counts/")
        self.assertEqual(counts.status_code, 200, counts.data)
        self.assertEqual(counts.data["unread"], 1)
        self.assertEqual(counts.data["total"], 1)

    def test_mark_read_unread_archive_and_restore(self):
        notification = create_notification(recipient=self.user, verb="refund requested")

        read = self.client.post(f"/notifications/{notification.pk}/mark-read/")
        self.assertEqual(read.status_code, 200, read.data)
        self.assertFalse(read.data["unread"])

        unread = self.client.post(f"/notifications/{notification.pk}/mark-unread/")
        self.assertEqual(unread.status_code, 200, unread.data)
        self.assertTrue(unread.data["unread"])

        archived = self.client.post(f"/notifications/{notification.pk}/archive/")
        self.assertEqual(archived.status_code, 200, archived.data)
        self.assertTrue(archived.data["deleted"])
        self.assertEqual(self.client.get("/notifications/").data["count"], 0)
        self.assertEqual(self.client.get("/notifications/archived/").data["count"], 1)

        restored = self.client.post(f"/notifications/{notification.pk}/restore/")
        self.assertEqual(restored.status_code, 200, restored.data)
        self.assertFalse(restored.data["deleted"])

    def test_mark_all_read_and_event_filter(self):
        create_notification(recipient=self.user, verb="one", data={"event": "orders"})
        create_notification(recipient=self.user, verb="two", data={"event": "refunds"})

        filtered = self.client.get("/notifications/", {"event": "refunds"})
        self.assertEqual(filtered.status_code, 200, filtered.data)
        self.assertEqual(filtered.data["count"], 1)
        self.assertEqual(filtered.data["results"][0]["verb"], "two")

        response = self.client.post("/notifications/mark-all-read/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["updated"], 2)
        self.assertEqual(Notification.objects.filter(recipient=self.user, unread=True).count(), 0)

    def test_event_filter_preserves_recipient_state_and_level_filters(self):
        create_notification(
            recipient=self.user,
            verb="matching unread warning",
            level="warning",
            data={"event": "order_update"},
        )
        read = create_notification(
            recipient=self.user,
            verb="matching read warning",
            level="warning",
            data={"event": "order_update"},
        )
        read.mark_as_read()
        create_notification(
            recipient=self.user,
            verb="other event",
            level="warning",
            data={"event": "refund_update"},
        )

        response = self.client.get(
            "/notifications/",
            {"event": "order_update", "state": "read", "level": "warning"},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["verb"], "matching read warning")

    def test_notify_staff_only_targets_active_staff(self):
        inactive_staff = User.objects.create_staffuser(
            email="inactive@example.com",
            password="pass12345",
            first_name="Inactive",
            last_name="Staff",
            gender="female",
            phone1="+2348012345680",
            is_active=False,
        )

        notify_staff("dashboard alert", actor=self.user, data={"event": "dashboard_alert"})

        self.assertTrue(Notification.objects.filter(recipient=self.staff).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.user).exists())
        self.assertFalse(Notification.objects.filter(recipient=inactive_staff).exists())

    @override_settings(
        EMAIL_BACKEND="notification.email_backend.ResendEmailBackend",
        RESEND_API_KEY="re_test_key",
    )
    def test_actionable_notifications_email_and_can_opt_out(self):
        with patch("notification.email_backend.resend.Emails.send") as send_email:
            with patch("notification.tasks.deliver_notification_task.apply_async") as enqueue:
                with self.captureOnCommitCallbacks(execute=True):
                    notification = create_notification(
                        recipient=self.user,
                        verb="wallet credited",
                        description="Your wallet was credited.",
                        data={"event": "wallet_credited"},
                    )
                    create_notification(
                        recipient=self.user,
                        verb="quiet update",
                        data={"email": False},
                    )

            delivery = NotificationDelivery.objects.get(notification=notification)
            self.assertEqual(delivery.status, NotificationDelivery.STATUS_QUEUED)
            self.assertEqual(enqueue.call_count, 1)
            send_email.assert_not_called()
            result = deliver_notification_task.run(delivery.pk)

        self.assertEqual(result["status"], NotificationDelivery.STATUS_SENT)
        send_email.assert_called_once()
        payload = send_email.call_args.args[0]
        self.assertEqual(payload["to"], [self.user.email])
        self.assertIn("wallet was credited", payload["text"])
        notification.refresh_from_db()
        self.assertTrue(notification.emailed)

    def test_failed_email_delivery_is_retained_for_retry(self):
        delivery = NotificationDelivery.objects.create(
            channel=NotificationDelivery.CHANNEL_EMAIL,
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Test",
            body="Message",
        )

        with patch(
            "notification.tasks._deliver_email",
            side_effect=RuntimeError("Resend unavailable"),
        ):
            result = deliver_notification_task.run(delivery.pk)

        delivery.refresh_from_db()
        self.assertEqual(result["status"], NotificationDelivery.STATUS_PENDING)
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(delivery.last_error, "Resend unavailable")
        self.assertGreater(delivery.available_at, timezone.now())

    @override_settings(
        NOTIFICATION_DELIVERY_MAX_ATTEMPTS=8,
        NOTIFICATION_DELIVERY_STALE_SECONDS=1,
    )
    def test_recovery_requeues_stale_deliveries(self):
        delivery = NotificationDelivery.objects.create(
            channel=NotificationDelivery.CHANNEL_EMAIL,
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Test",
            body="Message",
            status=NotificationDelivery.STATUS_QUEUED,
        )
        NotificationDelivery.objects.filter(pk=delivery.pk).update(
            updated_at=timezone.now() - timedelta(minutes=1)
        )

        with patch("notification.tasks.deliver_notification_task.apply_async") as enqueue:
            result = recover_notification_deliveries.run()

        delivery.refresh_from_db()
        self.assertEqual(result["queued"], 1)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_QUEUED)
        enqueue.assert_called_once()

    @override_settings(
        NOTIFICATION_DELIVERY_MAX_ATTEMPTS=8,
        NOTIFICATION_DELIVERY_STALE_SECONDS=1,
    )
    def test_recovery_fails_stale_delivery_after_final_attempt(self):
        delivery = NotificationDelivery.objects.create(
            channel=NotificationDelivery.CHANNEL_EMAIL,
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Test",
            body="Message",
            status=NotificationDelivery.STATUS_PROCESSING,
            attempts=8,
        )
        NotificationDelivery.objects.filter(pk=delivery.pk).update(
            updated_at=timezone.now() - timedelta(minutes=1)
        )

        with patch("notification.tasks.deliver_notification_task.apply_async") as enqueue:
            result = recover_notification_deliveries.run()

        delivery.refresh_from_db()
        self.assertEqual(result["queued"], 0)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_FAILED)
        self.assertEqual(
            delivery.last_error,
            "Worker stopped during the final delivery attempt.",
        )
        enqueue.assert_not_called()

    @override_settings(FCM_ENABLED=True)
    def test_user_can_register_and_unregister_only_their_push_device(self):
        response = self.client.post(
            "/notifications/devices/",
            {"token": "browser-token"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        device = PushDevice.objects.get(token="browser-token")
        self.assertEqual(device.user, self.user)

        self.client.force_authenticate(self.staff)
        response = self.client.delete(
            "/notifications/devices/",
            {"token": "browser-token"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(PushDevice.objects.filter(pk=device.pk).exists())

        self.client.force_authenticate(self.user)
        response = self.client.delete(
            "/notifications/devices/",
            {"token": "browser-token"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(PushDevice.objects.filter(pk=device.pk).exists())

    @override_settings(FCM_ENABLED=True)
    def test_push_device_token_is_reassigned_to_the_new_account(self):
        PushDevice.objects.create(user=self.user, token="shared-browser-token")

        self.client.force_authenticate(self.staff)
        response = self.client.post(
            "/notifications/devices/",
            {"token": "shared-browser-token"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            PushDevice.objects.get(token="shared-browser-token").user,
            self.staff,
        )

    def test_push_device_registration_requires_fcm_to_be_enabled(self):
        response = self.client.post(
            "/notifications/devices/",
            {"token": "browser-token"},
            format="json",
        )

        self.assertEqual(response.status_code, 503, response.data)
        self.assertFalse(PushDevice.objects.exists())

    @override_settings(FCM_ENABLED=True, FIREBASE_PROJECT_ID="test-project")
    def test_push_task_sends_data_only_messages_and_removes_expired_tokens(self):
        notification = create_notification(
            recipient=self.user,
            verb="order shipped",
            description="Your order is on the way.",
            data={"event": "order_shipped", "url": "/account/orders"},
        )
        delivery = NotificationDelivery.objects.create(
            channel=NotificationDelivery.CHANNEL_PUSH,
            notification=notification,
            recipient=self.user,
        )
        PushDevice.objects.create(user=self.user, token="expired-token")
        PushDevice.objects.create(user=self.user, token="valid-token")
        send_result = SimpleNamespace(
            success_count=1,
            responses=[
                SimpleNamespace(success=True, exception=None),
                SimpleNamespace(
                    success=False,
                    exception=SimpleNamespace(
                        code="messaging/registration-token-not-registered",
                    ),
                ),
            ],
        )

        with (
            patch("firebase_admin.get_app", side_effect=ValueError),
            patch("firebase_admin.initialize_app", return_value=object()),
            patch("firebase_admin.messaging.send_each_for_multicast", return_value=send_result) as send,
        ):
            result = deliver_notification_task.run(delivery.pk)

        self.assertEqual(result["status"], NotificationDelivery.STATUS_SENT)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(
            list(PushDevice.objects.values_list("token", flat=True)),
            ["valid-token"],
        )
        message = send.call_args.args[0]
        self.assertIsNone(message.notification)
        self.assertEqual(message.data["recipient_id"], str(self.user.pk))
        self.assertEqual(message.data["url"], "/account/orders")
