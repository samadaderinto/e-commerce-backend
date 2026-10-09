"""Transactional email coverage for security, moderation, and receipt routing."""
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import User
from notification.models import Notification, NotificationDelivery
from notification.views import account_access_notification, create_notification, password_changed_notification
from product.models import Product
from store.models import Store


@override_settings(ROOT_URLCONF="storefront.urls")
class TransactionalEmailTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(email="email-owner@test.com", password="OldPassword2026!")
        self.admin = User.objects.create_user(email="email-admin@test.com", password="AdminPassword2026!", is_business_admin=True, is_staff=True)
        self.store = Store.objects.create(user=self.owner, name="Email Shop")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @contextmanager
    def deliver_callbacks(self) -> Iterator[None]:
        # Inspect persisted outbox deliveries without sending mail or touching external services.
        with patch("notification.delivery._dispatch_delivery"), patch("notification.realtime.broker"), patch("notification.search.schedule_index_notification"):
            with self.captureOnCommitCallbacks(execute=True):
                yield

    def test_store_verification_sends_one_branded_email_and_repeat_is_silent(self) -> None:
        with self.deliver_callbacks():
            response = self.client.post(f"/api/v1/admin/stores/{self.store.pk}/approve/")
        self.assertEqual(response.status_code, 200)
        delivery = NotificationDelivery.objects.get(recipient=self.owner)
        self.assertTrue(delivery.is_html)
        self.assertIn("now public", delivery.body)
        self.assertIsNotNone(delivery.notification_id)
        with self.deliver_callbacks():
            self.client.post(f"/api/v1/admin/stores/{self.store.pk}/approve/")
        self.assertEqual(NotificationDelivery.objects.filter(recipient=self.owner).count(), 1)

    def test_backoffice_block_includes_escaped_reason_and_restore_sends_email(self) -> None:
        with self.deliver_callbacks():
            response = self.client.post(
                f"/api/v1/admin/staff/stores/{self.store.pk}/block/",
                {"reason": "Check <documents> & identity"},
            )
        self.assertEqual(response.status_code, 200)
        delivery = NotificationDelivery.objects.get(recipient=self.owner)
        self.assertIn("Check &lt;documents&gt; &amp; identity", delivery.body)
        self.assertNotIn("Check <documents>", delivery.body)
        with self.deliver_callbacks():
            response = self.client.post(f"/api/v1/admin/staff/stores/{self.store.pk}/unblock/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(NotificationDelivery.objects.filter(recipient=self.owner).count(), 2)

    def test_account_suspension_notifies_inactive_owner_and_noop_is_silent(self) -> None:
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.deliver_callbacks():
            account_access_notification(self.owner, True, False)
            account_access_notification(self.owner, False, False)
        delivery = NotificationDelivery.objects.get(recipient=self.owner)
        self.assertTrue(delivery.is_html)
        self.assertIn("suspended", delivery.body)

    def test_account_permission_endpoint_sends_security_email(self) -> None:
        with self.deliver_callbacks():
            response = self.client.patch(
                f"/api/v1/admin/staff/users/{self.owner.pk}/", {"is_active": False}, format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(NotificationDelivery.objects.filter(recipient=self.owner).count(), 1)

    def test_password_change_sends_confirmation_without_password(self) -> None:
        self.client.force_authenticate(self.owner)
        with self.deliver_callbacks():
            response = self.client.post(
                "/api/v1/password/change/",
                {"current_password": "OldPassword2026!", "password": "NewSecretPassword2026!"},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        delivery = NotificationDelivery.objects.get(recipient=self.owner)
        self.assertIn("password has been changed", delivery.body)
        self.assertNotIn("NewSecretPassword2026!", delivery.body)
        self.assertNotIn("OldPassword2026!", delivery.body)

    def test_rollback_does_not_queue_security_email(self) -> None:
        with self.deliver_callbacks():
            try:
                with transaction.atomic():
                    password_changed_notification(self.owner)
                    raise ValueError("rollback")
            except ValueError:
                pass
        self.assertFalse(NotificationDelivery.objects.filter(recipient=self.owner).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.owner).exists())

    def test_dedicated_email_suppression_keeps_inbox(self) -> None:
        with self.deliver_callbacks():
            notification = create_notification(
                self.owner, "refund approved", data={"event": "refund_approved", "email": False},
            )
        self.assertTrue(Notification.objects.filter(pk=notification.pk).exists())
        self.assertFalse(NotificationDelivery.objects.filter(recipient=self.owner).exists())

    def test_owner_gets_low_stock_email_once_per_threshold_crossing(self) -> None:
        product = Product.objects.create(store=self.store, title="Stock item", price=10, discount=0, available=9)
        with self.deliver_callbacks():
            product.available = 4
            product.save()
        delivery = NotificationDelivery.objects.get(recipient=self.owner)
        self.assertTrue(delivery.is_html)
        self.assertIn("Remaining stock", delivery.body)
        with self.deliver_callbacks():
            product.available = 3
            product.save()
        self.assertEqual(NotificationDelivery.objects.filter(recipient=self.owner).count(), 1)
        with self.deliver_callbacks():
            product.available = 0
            product.save()
        self.assertEqual(NotificationDelivery.objects.filter(recipient=self.owner).count(), 2)

    def test_password_reset_sends_security_confirmation(self) -> None:
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        self.client.force_authenticate(user=None)
        with self.deliver_callbacks():
            response = self.client.post(
                "/api/v1/auth/reset/",
                {
                    "uid": urlsafe_base64_encode(force_bytes(self.owner.pk)),
                    "token": default_token_generator.make_token(self.owner),
                    "password": "ResetSecretPassword2026!",
                },
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        delivery = NotificationDelivery.objects.get(recipient=self.owner)
        self.assertTrue(delivery.is_html)
        self.assertNotIn("ResetSecretPassword2026!", delivery.body)

    def test_staff_block_and_restore_send_once_per_change(self) -> None:
        self.owner.is_staff = True
        self.owner.save(update_fields=["is_staff"])
        for action in ["block", "block", "unblock", "unblock"]:
            with self.deliver_callbacks():
                response = self.client.post(f"/api/v1/admin/staff/{self.owner.pk}/{action}/")
            self.assertEqual(response.status_code, 200)
        self.assertEqual(NotificationDelivery.objects.filter(recipient=self.owner).count(), 2)

    def test_payout_decisions_send_one_html_email(self) -> None:
        from store.models import MerchantWallet, StorePayout

        wallet = MerchantWallet.objects.create(user=self.owner)
        for action in ["approve", "reject"]:
            payout = StorePayout.objects.create(store=self.store, wallet=wallet, amount=10, reference=action)
            with self.deliver_callbacks():
                response = self.client.post(
                    f"/api/v1/admin/staff/payouts/{payout.pk}/process/",
                    {"action": action, "reason": "Review failed"},
                )
            self.assertEqual(response.status_code, 200)
        deliveries = NotificationDelivery.objects.filter(recipient=self.owner)
        self.assertEqual(deliveries.count(), 2)
        self.assertTrue(all(delivery.is_html for delivery in deliveries))

    def test_outbox_is_persisted_before_commit_and_dispatch_waits(self) -> None:
        with patch("notification.delivery._dispatch_delivery") as dispatch:
            with transaction.atomic():
                notification = create_notification(self.owner, "durable event")
                delivery = NotificationDelivery.objects.get(notification=notification)
                self.assertEqual(delivery.status, NotificationDelivery.STATUS_PENDING)
                dispatch.assert_not_called()

    def test_template_failure_rolls_back_inbox_and_outbox(self) -> None:
        with patch("utils.functions.get_template", side_effect=ValueError("render failed")):
            with self.assertRaises(ValueError):
                password_changed_notification(self.owner)
        self.assertFalse(Notification.objects.filter(recipient=self.owner).exists())
        self.assertFalse(NotificationDelivery.objects.filter(recipient=self.owner).exists())

    def test_wallet_topup_sends_one_receipt_and_keeps_inbox(self) -> None:
        from decimal import Decimal
        from payment.funding import notify_funding

        with self.deliver_callbacks():
            notify_funding(self.owner, Decimal("10.00"))
        delivery = NotificationDelivery.objects.get(recipient=self.owner)
        self.assertTrue(delivery.is_html)
        self.assertTrue(Notification.objects.filter(recipient=self.owner, data__event="wallet_topup").exists())

    def test_shipment_omits_unknown_carrier_and_tracking(self) -> None:
        from utils.functions import send_mail

        send_mail("order-shipped", self.owner.email, {"orderId": "REAL-ORDER"})
        delivery = NotificationDelivery.objects.get(recipient=self.owner)
        self.assertNotIn("Carrier:", delivery.body)
        self.assertNotIn("Tracking number:", delivery.body)
        self.assertNotIn("USPS", delivery.body)

    def test_delivery_notice_has_no_sample_verification_code(self) -> None:
        from utils.functions import send_mail

        send_mail("delivery-confirmation", self.owner.email, {"orderId": "REAL-ORDER"})
        delivery = NotificationDelivery.objects.get(recipient=self.owner)
        self.assertIn("marked as delivered", delivery.body)
        self.assertNotIn("98097", delivery.body)
        self.assertNotIn("verify", delivery.body.lower())

    def test_payout_omits_missing_bank_reference_and_store(self) -> None:
        from utils.functions import send_mail

        send_mail("payout-processed", self.owner.email, {"amount": "10.00", "status": "Completed"})
        delivery = NotificationDelivery.objects.get(recipient=self.owner)
        for absent in ["Destination bank:", "Reference ID:", "Store:", "Notes:"]:
            self.assertNotIn(absent, delivery.body)
        self.assertIn("$10.00", delivery.body)
