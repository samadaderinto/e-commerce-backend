"""Regression coverage for the 15 October app-wide audit fixes."""

from unittest.mock import patch
from urllib.parse import urlsplit

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from cart.models import Cart, CartItem
from core.models import Refund, User
from core.serializers import RefundsSerializer
from payment.models import Order, OrderFulfillment
from payment.services import process_order_refund
from product.models import Product
from store.models import Store
from storefront.views import order_data


@override_settings(ROOT_URLCONF="storefront.urls")
class AppAuditFixTests(TestCase):
    def setUp(self) -> None:
        self.buyer = User.objects.create_user(
            email="fix-buyer@test.com", password="Test-password-123!"
        )
        self.seller = User.objects.create_user(
            email="fix-seller@test.com", password="Test-password-123!"
        )
        self.other = User.objects.create_user(
            email="fix-other@test.com", password="Test-password-123!"
        )
        self.staff = User.objects.create_user(
            email="fix-staff@test.com", password="Test-password-123!", is_staff=True
        )
        self.store = Store.objects.create(
            user=self.seller,
            name="Digital store",
            status="active",
            verified_at=timezone.now(),
        )
        self.other_store = Store.objects.create(
            user=self.other,
            name="Physical store",
            status="active",
            verified_at=timezone.now(),
        )
        self.product = Product.objects.create(
            store=self.store,
            title="Digital edition",
            price="10.00",
            discount=0,
            available=0,
            is_digital=True,
        )
        self.client = APIClient()

    def test_snapshot_order_membership_and_store_data_isolation(self) -> None:
        own_event = {"store_id": self.store.pk, "description": "Digital delivery"}
        other_event = {"store_id": self.other_store.pk, "description": "Other shipment"}
        order = Order.objects.create(
            user=self.buyer,
            ordered=True,
            status="confirmed",
            total="20.00",
            paid_total="20.00",
            items_snapshot=[
                {
                    "product": self.product.pk,
                    "store": str(self.store.pk),
                    "is_digital": True,
                    "title": "Digital",
                    "quantity": 1,
                },
                {
                    "product": 999,
                    "store": self.other_store.pk,
                    "is_digital": False,
                    "title": "Physical",
                    "quantity": 1,
                },
            ],
            address_snapshot={"address": "Recorded physical address"},
            tracking_events=[own_event, other_event, {"description": "Unscoped event"}],
            tracking_number="OTHER-STORE-TRACKING",
            shipped_at=timezone.now(),
        )
        OrderFulfillment.objects.create(
            order=order,
            store=self.other_store,
            status="shipped",
            carrier="UPS",
            tracking_number="OTHER-STORE-TRACKING",
        )
        self.client.force_authenticate(self.seller)
        response = self.client.get(f"/api/v1/stores/{self.store.pk}/orders/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["id"], order.pk)
        self.assertFalse(row["has_physical_items"])
        self.assertEqual(row["shipping_address"], {})
        self.assertEqual(row["tracking_events"], [own_event])
        self.assertEqual(row["tracking_number"], "")
        self.assertEqual(row["tracking_url"], "")
        self.assertIsNone(row["shipped_at"])
        self.assertEqual([item["title"] for item in row["items"]], ["Digital"])
        self.client.force_authenticate(self.other)
        row = self.client.get(f"/api/v1/stores/{self.other_store.pk}/orders/").data[
            "results"
        ][0]
        self.assertEqual(row["shipping_address"], order.address_snapshot)
        self.assertEqual(row["tracking_events"], [other_event])
        self.assertTrue(row["has_physical_items"])
        self.assertEqual(row["tracking_number"], "OTHER-STORE-TRACKING")
        self.assertIn("OTHER-STORE-TRACKING", row["tracking_url"])
        updated = self.client.post(
            f"/api/v1/stores/{self.other_store.pk}/orders/{order.pk}/tracking/",
            {"status": "delivered", "carrier": "UPS", "tracking_number": "OWN-UPDATED"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertNotIn(own_event, updated.data["tracking_events"])
        self.assertIn("OWN-UPDATED", updated.data["tracking_url"])
        self.client.force_authenticate(self.buyer)
        self.assertEqual(
            self.client.get(f"/api/v1/stores/{self.store.pk}/orders/").status_code, 404
        )

    def test_legacy_cart_order_retains_its_single_store_events(self) -> None:
        cart = Cart.objects.create(user=self.buyer, ordered=True)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        order = Order.objects.create(
            user=self.buyer,
            cart=cart,
            ordered=True,
            status="confirmed",
            tracking_events=[{"description": "Legacy event"}],
        )
        self.client.force_authenticate(self.seller)
        row = self.client.get(f"/api/v1/stores/{self.store.pk}/orders/").data[
            "results"
        ][0]
        self.assertEqual(row["id"], order.pk)
        self.assertEqual(row["tracking_events"], order.tracking_events)
        self.assertEqual(row["items"][0]["product"], self.product.pk)

    def test_digital_variants_have_distinct_authorized_snapshot_downloads(self) -> None:
        first = default_storage.save("audit-fix/first.txt", ContentFile(b"FIRST"))
        second = default_storage.save("audit-fix/second.txt", ContentFile(b"SECOND"))
        order = Order.objects.create(
            user=self.buyer,
            ordered=True,
            status="delivered",
            total="20.00",
            paid_total="20.00",
            items_snapshot=[
                {
                    "product": self.product.pk,
                    "store": self.store.pk,
                    "is_digital": True,
                    "variant": "First",
                    "download_url": first,
                },
                {
                    "product": self.product.pk,
                    "store": self.store.pk,
                    "is_digital": True,
                    "variant": " Second + édition ",
                    "download_url": second,
                },
            ],
        )
        self.client.force_authenticate(self.buyer)
        items = order_data(order)["items"]
        self.assertNotEqual(items[0]["download_url"], items[1]["download_url"])
        for row, expected in zip(items, [b"FIRST", b"SECOND"]):
            url = urlsplit(row["download_url"])
            path = url.path.replace("/api/", "/api/v1/", 1).rstrip("/") + "/"
            response = self.client.get(path + "?" + url.query)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), expected)
        base = f"/api/v1/orders/{order.pk}/downloads/{self.product.pk}/"
        self.assertEqual(self.client.get(base).status_code, 404)
        self.assertEqual(
            self.client.get(base, {"variant": "Unpurchased"}).status_code, 404
        )
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(base, {"variant": "First"}).status_code, 404)
        self.client.force_authenticate(self.buyer)
        order.status = "refunded"
        order.save(update_fields=["status"])
        self.assertEqual(self.client.get(base, {"variant": "First"}).status_code, 404)

    def test_legacy_single_digital_purchase_keeps_its_download_url(self) -> None:
        path = default_storage.save("audit-fix/legacy.txt", ContentFile(b"LEGACY"))
        order = Order.objects.create(
            user=self.buyer,
            ordered=True,
            status="delivered",
            total="10.00",
            paid_total="10.00",
            items_snapshot=[
                {"product": self.product.pk, "is_digital": True, "download_url": path}
            ],
        )
        self.client.force_authenticate(self.buyer)
        response = self.client.get(
            f"/api/v1/orders/{order.pk}/downloads/{self.product.pk}/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"LEGACY")

    def test_failed_refund_records_clean_message_and_latest_actor_then_retries(
        self,
    ) -> None:
        order = Order.objects.create(
            user=self.buyer,
            ordered=True,
            status="confirmed",
            total="10.00",
            paid_total="10.00",
        )
        refund = Refund.objects.create(
            order=order,
            email=self.buyer.email,
            reason="Damaged",
            refund_type="original_payment",
        )
        admin = User.objects.create_superuser(
            email="fix-admin@test.com", password="Test-password-123!"
        )
        for actor in [self.staff, admin]:
            with patch(
                "payment.services.call_stripe_refund",
                side_effect=RuntimeError("private-provider-diagnostic"),
            ):
                with self.assertRaises(ValidationError):
                    process_order_refund(refund, actor, "Reviewed failure")
            refund.refresh_from_db()
            self.assertEqual(refund.status, "failed")
            self.assertEqual(refund.processed_by, actor)
            self.assertIsNotNone(refund.processed_at)
            self.assertEqual(refund.processing_reason, "Reviewed failure")
            self.assertEqual(
                RefundsSerializer(refund).data["processed_by_email"], actor.email
            )
            self.client.force_authenticate(self.buyer)
            response = self.client.get(f"/api/v1/orders/{order.pk}/refund/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.data["failure_reason"],
                "Payment provider refund failed. Support will review it.",
            )
            self.assertNotIn("ErrorDetail", str(order_data(order)))
            self.assertNotIn("private-provider-diagnostic", str(response.data))
        with patch("payment.services.call_stripe_refund", return_value="re_audit_fix"):
            process_order_refund(refund, self.staff, "Retry approved")
        refund.refresh_from_db()
        self.assertEqual(refund.status, "approved")
        self.assertEqual(refund.processed_by, self.staff)
        self.assertEqual(refund.failure_reason, "")

    def test_historical_failure_text_is_safe_in_successful_get_payloads(self) -> None:
        order = Order.objects.create(user=self.buyer, status="confirmed")
        refund = Refund.objects.create(
            order=order,
            email=self.buyer.email,
            reason="Damaged",
            status="failed",
            failure_reason="{'detail': ErrorDetail(string='old error', code='invalid')}",
        )
        expected = "Payment provider refund failed. Support will review it."
        self.assertEqual(RefundsSerializer(refund).data["failure_reason"], expected)
        self.assertEqual(order_data(order)["active_refund"]["failure_reason"], expected)
        self.client.force_authenticate(self.buyer)
        response = self.client.get(f"/api/v1/orders/{order.pk}/refund/")
        self.assertEqual(response.data["failure_reason"], expected)
        refund.status = "declined"
        refund.failure_reason = (
            "Review completed: the item is outside the return window."
        )
        self.assertEqual(
            RefundsSerializer(refund).data["failure_reason"], refund.failure_reason
        )

    def test_invalid_reset_id_returns_validation_error(self) -> None:
        for uid in [
            "!",
            urlsafe_base64_encode(b"not-an-integer"),
            urlsafe_base64_encode(b"9" * 100),
            urlsafe_base64_encode(b"0"),
            urlsafe_base64_encode(b"9223372036854775808"),
            urlsafe_base64_encode(b"999999999"),
        ]:
            with self.subTest(uid=uid):
                response = self.client.post(
                    "/api/v1/auth/reset/",
                    {"uid": uid, "token": "invalid", "password": "Test-password-123!"},
                    format="json",
                )
                self.assertEqual(response.status_code, 400, response.data)
