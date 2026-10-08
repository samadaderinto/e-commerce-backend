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

        # Archive again and test permanent deletion from archive
        self.client.post(f"/notifications/{notification.pk}/archive/")
        self.assertEqual(self.client.get("/notifications/archived/").data["count"], 1)
        delete_resp = self.client.delete(f"/notifications/{notification.pk}/")
        self.assertEqual(delete_resp.status_code, 204)
        self.assertEqual(self.client.get("/notifications/archived/").data["count"], 0)
        self.assertFalse(Notification.objects.filter(pk=notification.pk).exists())

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
        self.assertEqual(set(message.fids or message.tokens), {"expired-token", "valid-token"})

    def test_full_text_search_filters_notifications(self):
        create_notification(
            recipient=self.user,
            verb="Refund processed for Order #10042",
            description="Your $45.00 return has cleared.",
        )
        create_notification(
            recipient=self.user,
            verb="Package arriving tomorrow",
            description="USPS tracking is updated.",
        )

        res1 = self.client.get("/notifications/", {"search": "refund"})
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.data["count"], 1)
        self.assertIn("Refund", res1.data["results"][0]["verb"])

        res2 = self.client.get("/notifications/", {"q": "tracking"})
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.data["count"], 1)
        self.assertIn("USPS", res2.data["results"][0]["description"])

        res3 = self.client.get("/notifications/", {"search": "nonexistent keyword"})
        self.assertEqual(res3.status_code, 200)
        self.assertEqual(res3.data["count"], 0)

    def test_category_filter_supports_store_and_affiliates(self):
        from store.models import Store

        store = Store.objects.create(
            user=self.user,
            name="Green Valley Store",
            username="green-valley",
        )

        create_notification(
            recipient=self.user,
            verb="Store verified",
            description="Green Valley Store is now live.",
            target=store,
            data={"event": "store_verified", "store_id": store.pk},
        )
        create_notification(
            recipient=self.user,
            verb="Referral Reward Earned: $25",
            description="You referred a new member!",
            data={"event": "referral_reward", "amount": "25.00"},
        )
        create_notification(
            recipient=self.user,
            verb="Account security alert",
            description="New login from a recognized device.",
        )

        res_store = self.client.get("/notifications/", {"category": "store"})
        self.assertEqual(res_store.status_code, 200)
        self.assertEqual(res_store.data["count"], 1)
        self.assertEqual(res_store.data["results"][0]["category"], "store")
        self.assertEqual(res_store.data["results"][0]["store"]["name"], "Green Valley Store")

        res_aff = self.client.get("/notifications/", {"category": "affiliates"})
        self.assertEqual(res_aff.status_code, 200)
        self.assertEqual(res_aff.data["count"], 1)
        self.assertEqual(res_aff.data["results"][0]["category"], "affiliates")

    def test_store_filter_by_id_and_slug(self):
        from store.models import Store

        store1 = Store.objects.create(user=self.user, name="Alpha Store", username="alpha-store")
        store2 = Store.objects.create(user=self.user, name="Beta Store", username="beta-store")

        create_notification(
            recipient=self.user,
            verb="Item sold in Alpha Store",
            description="New customer purchase in Alpha Store.",
            target=store1,
            data={"store_id": store1.pk},
        )
        create_notification(
            recipient=self.user,
            verb="Inventory low in Beta Store",
            description="Restock Beta Store soon.",
            target=store2,
            data={"store_id": store2.pk},
        )

        # By ID
        res_by_id = self.client.get("/notifications/", {"store": str(store1.pk)})
        self.assertEqual(res_by_id.status_code, 200)
        self.assertEqual(res_by_id.data["count"], 1)
        self.assertIn("Alpha", res_by_id.data["results"][0]["verb"])

        # By username
        res_by_user = self.client.get("/notifications/", {"store": "beta-store"})
        self.assertEqual(res_by_user.status_code, 200)
        self.assertEqual(res_by_user.data["count"], 1)
        self.assertIn("Beta", res_by_user.data["results"][0]["verb"])

        # Store-filtered counts endpoint
        counts_res = self.client.get("/notifications/counts/", {"store": str(store1.pk)})
        self.assertEqual(counts_res.status_code, 200)
        self.assertEqual(counts_res.data["unread"], 1)
        self.assertEqual(counts_res.data["total"], 1)

    def test_filters_action_returns_metadata(self):
        from store.models import Store

        store = Store.objects.create(user=self.user, name="My Shop", username="my-shop")
        create_notification(
            recipient=self.user,
            verb="Store verified",
            target=store,
            data={"event": "store_verified", "store_id": store.pk},
        )
        create_notification(
            recipient=self.user,
            verb="Referral Reward",
            data={"event": "referral_reward"},
        )

        res = self.client.get("/notifications/filters/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("categories", res.data)
        self.assertIn("stores", res.data)
        self.assertIn("counts", res.data)

        cat_ids = [c["id"] for c in res.data["categories"]]
        self.assertIn("all", cat_ids)
        self.assertIn("store", cat_ids)
        self.assertIn("affiliates", cat_ids)
        self.assertTrue(any(s["id"] == store.pk for s in res.data["stores"]))

    def test_super_admin_notification_filters_only_shows_official_stores(self):
        from store.models import Store
        from core.models import User

        admin = User.objects.create_superuser(email="superadmin@proace.com", password="Admin-Pass-123!")
        third_party_user = User.objects.create_user(email="thirdparty@seller.com", password="Seller-Pass-123!")

        third_party_store = Store.objects.create(user=third_party_user, name="Third Party Store", username="third-party", is_official=False)
        official_store = Store.objects.create(user=admin, name="Proace Official Store", username="proace-official", is_official=True)

        create_notification(
            recipient=admin,
            verb="Third-party store updated",
            target=third_party_store,
            data={"event": "store_updated", "store_id": third_party_store.pk},
        )
        create_notification(
            recipient=admin,
            verb="Official store updated",
            target=official_store,
            data={"event": "store_updated", "store_id": official_store.pk},
        )

        self.client.force_authenticate(admin)
        res = self.client.get("/notifications/filters/")
        self.assertEqual(res.status_code, 200)

        store_ids = [s["id"] for s in res.data["stores"]]
        self.assertIn(official_store.pk, store_ids)
        self.assertNotIn(third_party_store.pk, store_ids)

    def test_elasticsearch_notification_document_mapping(self):
        from notification.search import notification_document
        from store.models import Store

        store = Store.objects.create(user=self.user, name="ES Store", username="es-store")
        notif = create_notification(
            recipient=self.user,
            verb="Item Purchased",
            description="A buyer purchased an item.",
            level="success",
            target=store,
            data={"event": "new_order", "store_id": store.pk},
        )
        doc = notification_document(notif)
        self.assertEqual(doc["id"], notif.id)
        self.assertEqual(doc["recipient_id"], self.user.id)
        self.assertEqual(doc["verb"], "Item Purchased")
        self.assertEqual(doc["category"], "store")
        self.assertEqual(doc["store_id"], store.pk)
        self.assertEqual(doc["store_name"], "ES Store")
        self.assertTrue(doc["unread"])
        self.assertFalse(doc["deleted"])

    def test_elasticsearch_search_notification_ids_with_mock(self):
        from notification.search import search_notification_ids

        mock_response = {
            "hits": {
                "total": {"value": 1},
                "hits": [{"_id": "42"}],
            }
        }

        with (
            override_settings(ELASTICSEARCH_ENABLED=True),
            patch("notification.search.client") as mock_client_fn,
        ):
            mock_es = mock_client_fn.return_value
            mock_es.search.return_value = mock_response

            results = search_notification_ids("refund", recipient_id=self.user.id)
            self.assertIsNotNone(results)
            self.assertEqual(results["count"], 1)
            self.assertEqual(results["ids"], [42])

