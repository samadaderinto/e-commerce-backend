from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import User
from product.models import Product, ProductModerationEvent
from store.models import Store
from notification.models import Notification
from storefront.views import catalog, cart_data
from cart.models import Cart, CartItem
from payment.models import Order
from staff.serializers import StoreAuditProductSerializer


class ProductModerationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            email="admin@test.com",
            password="Admin-password-123!",
        )
        self.staff = User.objects.create_staffuser(
            email="staff@test.com",
            password="Staff-password-123!",
        )
        self.merchant = User.objects.create_user(
            email="merchant@test.com",
            password="Merchant-password-123!",
            first_name="Store",
            last_name="Owner",
        )
        self.shopper = User.objects.create_user(
            email="shopper@test.com",
            password="Shopper-password-123!",
            first_name="Customer",
            last_name="One",
        )
        self.store = Store.objects.create(
            user=self.merchant,
            name="Apex Athletics",
            username="apex-athletics",
            status=Store.STATUS_ACTIVE,
            verified_at=timezone.now(),
        )
        from store.models import StoreAddress
        StoreAddress.objects.create(
            store=self.store,
            address="123 Athletic Way",
            city="Portland",
            state="OR",
            zip="97201",
            country="US",
            is_default=True,
        )
        self.product = Product.objects.create(
            store=self.store,
            title="Premium Running Shoes",
            description="High performance running shoes",
            category="shoes",
            price=Decimal("120.00"),
            discount=0,
            available=20,
            visibility=True,
        )

    def test_staff_can_block_and_restore_product_with_audit_trail(self):
        self.client.force_authenticate(self.staff)
        block_response = self.client.post(
            f"/api/v1/admin/staff/products/{self.product.pk}/moderation/",
            {"action": "block", "reason": "suspected scam"},
            format="json",
        )
        self.assertEqual(block_response.status_code, 200, block_response.data)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_blocked)
        self.assertEqual(self.product.blocked_reason, "suspected scam")
        self.assertEqual(self.product.blocked_by, self.staff)
        self.assertIsNotNone(self.product.blocked_at)

        # Audit event created
        event = ProductModerationEvent.objects.filter(product=self.product).latest("created")
        self.assertEqual(event.action, "block")
        self.assertEqual(event.actor, self.staff)
        self.assertEqual(event.reason, "suspected scam")

        # In-app notification to merchant
        notif = Notification.objects.filter(recipient=self.merchant, target_object_id=self.product.pk).latest("timestamp")
        self.assertEqual(notif.verb, "product blocked")
        self.assertIn("suspected scam", notif.description)
        self.assertEqual(notif.data.get("event"), "product_blocked")
        self.assertEqual(notif.data.get("product_title"), "Premium Running Shoes")

        # Serializer includes audit events and blocked_by_email
        audit_data = StoreAuditProductSerializer(self.product).data
        self.assertTrue(audit_data["is_blocked"])
        self.assertEqual(audit_data["blocked_by_email"], self.staff.email)
        self.assertEqual(len(audit_data["moderation_events"]), 1)
        self.assertEqual(audit_data["moderation_events"][0]["actor_email"], self.staff.email)

        # Restore product
        restore_response = self.client.post(
            f"/api/v1/admin/staff/products/{self.product.pk}/moderation/",
            {"action": "restore", "reason": "Verified legitimate inventory by compliance review"},
            format="json",
        )
        self.assertEqual(restore_response.status_code, 200, restore_response.data)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_blocked)
        self.assertEqual(self.product.blocked_reason, "")
        self.assertIsNone(self.product.blocked_by)
        self.assertIsNone(self.product.blocked_at)

        # Second audit event created
        restore_event = ProductModerationEvent.objects.filter(product=self.product).latest("created")
        self.assertEqual(restore_event.action, "restore")
        self.assertEqual(restore_event.actor, self.staff)

        # In-app notification for restore
        restore_notif = Notification.objects.filter(recipient=self.merchant, target_object_id=self.product.pk).latest("timestamp")
        self.assertEqual(restore_notif.verb, "product restored")

    def test_blocking_requires_a_valid_non_empty_reason(self):
        self.client.force_authenticate(self.staff)
        for invalid_reason in ["", "   "]:
            response = self.client.post(
                f"/api/v1/admin/staff/products/{self.product.pk}/moderation/",
                {"action": "block", "reason": invalid_reason},
                format="json",
            )
            self.assertEqual(response.status_code, 400)
            self.product.refresh_from_db()
            self.assertFalse(self.product.is_blocked)

    def test_blocked_product_immediately_excluded_from_public_listings_and_shoppers(self):
        self.assertIn(self.product, catalog())

        # Block the product
        self.product.is_blocked = True
        self.product.blocked_reason = "prohibited item"
        self.product.save(update_fields=["is_blocked", "blocked_reason"])

        # Excluded from catalog
        self.assertNotIn(self.product, catalog())

        # Public visitor gets 404
        self.client.logout()
        detail_response = self.client.get(f"/api/v1/products/{self.product.pk}/")
        self.assertEqual(detail_response.status_code, 404)

        # Authenticated shopper gets 404
        self.client.force_authenticate(self.shopper)
        detail_response = self.client.get(f"/api/v1/products/{self.product.pk}/")
        self.assertEqual(detail_response.status_code, 404)

        # Staff can preview
        self.client.force_authenticate(self.staff)
        preview_response = self.client.get(f"/api/v1/products/{self.product.pk}/")
        self.assertEqual(preview_response.status_code, 200)

    def test_blocked_product_in_cart_is_not_purchasable_and_checkout_rejected(self):
        # Shopper adds to cart while active
        cart = Cart.objects.create(user=self.shopper, ordered=False)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)

        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        req = factory.get("/api/v1/cart/")
        req.user = self.shopper

        cart_info = cart_data(cart, req)
        self.assertTrue(cart_info["items"][0]["purchasable"])

        # Staff blocks product
        self.product.is_blocked = True
        self.product.blocked_reason = "misleading description"
        self.product.save(update_fields=["is_blocked", "blocked_reason"])

        cart_info_blocked = cart_data(cart, req)
        self.assertFalse(cart_info_blocked["items"][0]["purchasable"])

        # Attempting checkout with blocked item in cart is rejected
        self.client.force_authenticate(self.shopper)
        checkout_response = self.client.post(
            "/api/v1/checkout/",
            {"cart_key": str(cart.pk)},
            format="json",
        )
        self.assertEqual(checkout_response.status_code, 400)

    def test_existing_orders_and_records_remain_intact(self):
        order = Order.objects.create(
            user=self.shopper,
            orderId="ORDER-BLOCKED-123",
            total=Decimal("120.00"),
            status="confirmed",
            items_snapshot=[{
                "product": self.product.pk,
                "title": self.product.title,
                "price": str(self.product.price),
                "quantity": 1,
            }],
        )

        # Block the product
        self.client.force_authenticate(self.staff)
        self.client.post(
            f"/api/v1/admin/staff/products/{self.product.pk}/moderation/",
            {"action": "block", "reason": "another policy violation"},
            format="json",
        )

        # Existing order and items remain intact
        order.refresh_from_db()
        self.assertEqual(order.status, "confirmed")
        self.assertEqual(len(order.items_snapshot), 1)
        self.assertEqual(order.items_snapshot[0]["product"], self.product.pk)

    def test_merchant_can_edit_product_but_cannot_unblock_or_bypass_block(self):
        self.product.is_blocked = True
        self.product.blocked_reason = "misleading description"
        self.product.save(update_fields=["is_blocked", "blocked_reason"])

        self.client.force_authenticate(self.merchant)

        # Merchant edits title and description to address the issue
        edit_response = self.client.patch(
            f"/api/v1/stores/{self.store.pk}/products/{self.product.pk}/",
            {"description": "Updated accurate description complying with platform rules."},
            format="json",
        )
        self.assertEqual(edit_response.status_code, 200, edit_response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.description, "Updated accurate description complying with platform rules.")
        # Remains blocked
        self.assertTrue(self.product.is_blocked)

        # Merchant tries to send is_blocked = False
        bypass_response = self.client.patch(
            f"/api/v1/stores/{self.store.pk}/products/{self.product.pk}/",
            {"is_blocked": False},
            format="json",
        )
        self.assertEqual(bypass_response.status_code, 200)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_blocked)  # Still blocked, is_blocked is read-only

    def test_blocked_product_cannot_be_deleted(self):
        from rest_framework.exceptions import ValidationError

        self.product.is_blocked = True
        self.product.blocked_reason = "suspected scam"
        self.product.save(update_fields=["is_blocked", "blocked_reason"])

        # 1. Merchant attempts DELETE via API
        self.client.force_authenticate(self.merchant)
        delete_response = self.client.delete(
            f"/api/v1/stores/{self.store.pk}/products/{self.product.pk}/"
        )
        self.assertEqual(delete_response.status_code, 400)
        self.assertIn("Blocked products cannot be deleted", str(delete_response.data))

        # 2. Direct model delete() call raises ValidationError
        with self.assertRaises(ValidationError) as ctx:
            self.product.delete()
        self.assertIn("Blocked products cannot be deleted while under platform moderation.", str(ctx.exception))

        # Product still exists in database
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
