from django.urls import include, path
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import User
from core.models import Address, Refund
from cart.models import Cart
from payment.models import Coupon, DeliveryInfo, Order
from django.utils import timezone
from datetime import timedelta


urlpatterns = [path("staffs/", include("staff.urls"))]


@override_settings(ROOT_URLCONF=__name__)
class StaffAdministrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="Admin-password-123!",
        )
        self.staff = User.objects.create_staffuser(
            email="staff@example.com",
            password="Staff-password-123!",
        )
        self.client = APIClient()

    def test_user_detail_serializes_notification_timestamp(self) -> None:
        from django.contrib.contenttypes.models import ContentType
        from notification.models import Notification

        activity = Notification.objects.create(
            recipient=self.staff, actor_content_type=ContentType.objects.get_for_model(User),
            actor_object_id=str(self.admin.pk), verb='Account updated', description='Staff activity',
        )
        self.client.force_authenticate(self.admin)
        response = self.client.get(f'/staffs/users/{self.staff.pk}/')
        self.assertEqual(response.status_code, 200, response.data)
        payload = response.json()
        self.assertEqual(payload['activity'][0]['id'], activity.pk)
        self.assertEqual(payload['activity'][0]['created'], activity.timestamp.isoformat())
        self.assertEqual(payload['user']['id'], self.staff.pk)
        self.assertIn('wallet', payload)
        self.assertIn('orders', payload)

    def staff_payload(self):
        return {
            "email": "new.staff@example.com",
            "first_name": "New",
            "last_name": "Staff",
            "phone1": "+2348012345678",
            "gender": "female",
        }

    def test_admin_can_create_staff(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post("/staffs/staffs/", self.staff_payload(), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        created = User.objects.get(email="new.staff@example.com")
        self.assertTrue(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertFalse(created.is_active)
        self.assertFalse(created.must_change_password)
        self.assertFalse(created.staff_email_verified)
        self.assertFalse(created.check_password("New-staff-password-123!"))
        self.assertNotIn("password", response.data)

    def test_staff_cannot_create_or_list_staff(self):
        self.client.force_authenticate(self.staff)

        self.assertEqual(self.client.get("/staffs/staffs/").status_code, 403)
        self.assertEqual(
            self.client.post("/staffs/staffs/", self.staff_payload(), format="json").status_code,
            403,
        )

    def test_admin_can_block_and_unblock_staff(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(f"/staffs/staffs/{self.staff.pk}/block/")
        self.assertEqual(response.status_code, 200, response.data)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)

        response = self.client.post(f"/staffs/staffs/{self.staff.pk}/unblock/")
        self.assertEqual(response.status_code, 200, response.data)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    def test_staff_cannot_block_another_staff(self):
        other_staff = User.objects.create_staffuser(
            email="other.staff@example.com",
            password="Other-password-123!",
        )
        self.client.force_authenticate(self.staff)

        response = self.client.post(f"/staffs/staffs/{other_staff.pk}/block/")

        self.assertEqual(response.status_code, 403)
        other_staff.refresh_from_db()
        self.assertTrue(other_staff.is_active)

    def test_admin_accounts_cannot_be_blocked_through_staff_endpoint(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(f"/staffs/staffs/{self.admin.pk}/block/")

        self.assertEqual(response.status_code, 404)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


@override_settings(ROOT_URLCONF="storefront.urls")
class StaffFrontendApiIntegrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="frontend.admin@example.com",
            password="Admin-password-123!",
        )
        self.staff = User.objects.create_staffuser(
            email="frontend.staff@example.com",
            password="Staff-password-123!",
        )
        self.client = APIClient()

    def test_frontend_session_exposes_admin_role_and_routes_staff_actions(self):
        self.client.force_authenticate(self.admin)

        me = self.client.get("/api/v1/me/")
        listing = self.client.get("/api/v1/admin/staff/")
        blocked = self.client.post(f"/api/v1/admin/staff/{self.staff.pk}/block/")

        self.assertEqual(me.status_code, 200, me.data)
        self.assertTrue(me.data["is_superuser"])
        self.assertEqual(listing.status_code, 200, listing.data)
        self.assertEqual(listing.data["results"][0]["id"], self.staff.pk)
        self.assertEqual(blocked.status_code, 200, blocked.data)
        self.assertFalse(blocked.data["is_active"])

    def test_frontend_staff_route_rejects_non_admin_staff(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get("/api/v1/admin/staff/")

        self.assertEqual(response.status_code, 403)


@override_settings(ROOT_URLCONF=__name__)
class StaffEmergencyOperationsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_staffuser(email="operator@example.com", password="test-password")
        self.customer = User.objects.create_user(email="customer@example.com", password="test-password")
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        cart = Cart.objects.create(user=self.customer, ordered=True)
        address = Address.objects.create(
            user=self.customer, address="1 Support Road", zip="10001",
            country="US", state="NY", city="New York",
        )
        delivery = DeliveryInfo.objects.create(
            user=self.customer, address=address, method="home delivery", delivery_type="standard",
        )
        self.order = Order.objects.create(
            user=self.customer, cart=cart, delivery=delivery, status="confirmed", ordered=True,
            total="25.00", subtotal="20.00", paid_total="25.00",
        )

    def test_staff_can_deactivate_and_delete_unused_coupon(self):
        coupon = Coupon.objects.create(
            code="HELP10", valid_to=timezone.now() + timedelta(days=7),
            discount=10, num_available=20,
        )
        response = self.client.patch(f"/staffs/coupons/{coupon.pk}/", {"active": False}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        coupon.refresh_from_db()
        self.assertFalse(coupon.active)
        response = self.client.delete(f"/staffs/coupons/{coupon.pk}/")
        self.assertEqual(response.status_code, 204, response.data)
        self.assertFalse(Coupon.objects.filter(pk=coupon.pk).exists())

    def test_used_coupon_must_be_deactivated_instead_of_deleted(self):
        coupon = Coupon.objects.create(
            code="USED10", valid_to=timezone.now() + timedelta(days=7),
            discount=10, num_available=20, num_used=1,
        )
        response = self.client.delete(f"/staffs/coupons/{coupon.pk}/")
        self.assertEqual(response.status_code, 400, response.data)

    def test_staff_can_override_order_status_with_audited_reason(self):
        response = self.client.post(
            f"/staffs/orders/{self.order.pk}/status/",
            {"status": "shipped", "reason": "Merchant lost access and confirmed dispatch by phone."},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "shipped")
        self.assertEqual(self.order.tracking_events[-1]["actor_id"], self.staff.pk)
        self.assertEqual(self.customer.notifications.filter(data__event="order_status_override").count(), 1)

    def test_staff_can_process_refund_only_once(self):
        refund = Refund.objects.create(
            email=self.customer.email, order=self.order, reason="Item never arrived",
        )
        response = self.client.post(f"/staffs/refunds/{refund.pk}/process/", {"action": "approve", "reason": "Approved after support review."}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        refund.refresh_from_db()
        self.assertEqual(refund.status, Refund.STATUS_APPROVED)
        self.assertEqual(refund.processed_by, self.staff)
        response = self.client.post(f"/staffs/refunds/{refund.pk}/process/", {"action": "approve", "reason": "Duplicate approval check."}, format="json")
        self.assertEqual(response.status_code, 400, response.data)

    def test_staff_can_process_original_payment_refund_via_api(self):
        self.order.payment_type = "user_wallet"
        self.order.wallet_paid = self.order.paid_total
        self.order.save()
        refund = Refund.objects.create(
            email=self.customer.email,
            order=self.order,
            reason="Item broke on arrival",
            refund_type=Refund.REFUND_TYPE_ORIGINAL_PAYMENT,
        )
        response = self.client.post(f"/staffs/refunds/{refund.pk}/process/", {"action": "approve", "reason": "Approved after payment review."}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        refund.refresh_from_db()
        self.assertEqual(refund.status, Refund.STATUS_APPROVED)
        self.assertTrue(refund.provider_reference.startswith("WALLET-TX-"))

    def test_staff_approve_refund_with_store_earnings_ledger(self):
        from decimal import Decimal
        from store.models import Store, StoreEarningsLedger, MerchantWallet
        store = Store.objects.create(user=self.staff, name="Test Store", username="test-store")
        wallet = MerchantWallet.objects.create(user=self.staff, pending_balance=Decimal("50.00"))
        StoreEarningsLedger.objects.create(
            order=self.order,
            store=store,
            wallet=wallet,
            entry_type=StoreEarningsLedger.TYPE_SALE,
            gross_amount=Decimal("25.00"),
            fee_amount=Decimal("1.00"),
            net_amount=Decimal("24.00"),
            status=StoreEarningsLedger.STATUS_PENDING,
        )
        self.order.payment_type = "wallet"
        self.order.wallet_paid = self.order.paid_total
        self.order.save()
        refund = Refund.objects.create(
            email=self.customer.email,
            order=self.order,
            reason="Customer request",
            refund_type=Refund.REFUND_TYPE_ORIGINAL_PAYMENT,
        )
        response = self.client.post(f"/staffs/refunds/{refund.pk}/process/", {"action": "approve", "reason": "Approved after ledger review."}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        refund.refresh_from_db()
        self.assertEqual(refund.status, Refund.STATUS_APPROVED)
        wallet.refresh_from_db()
        self.assertEqual(wallet.pending_balance, Decimal("26.00"))

    def test_staff_cannot_approve_original_card_refund_without_provider_reference(self) -> None:
        self.order.payment_type = "card"
        self.order.stripe_session_id = None
        self.order.save()
        refund = Refund.objects.create(
            email=self.customer.email,
            order=self.order,
            reason="Card order refund",
            refund_type=Refund.REFUND_TYPE_ORIGINAL_PAYMENT,
        )
        response = self.client.post(f"/staffs/refunds/{refund.pk}/process/", {"action": "approve", "reason": "Approved after card review."}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        refund.refresh_from_db()
        self.assertEqual(refund.status, Refund.STATUS_FAILED)
        self.assertEqual(refund.provider_reference, "")

    def test_staff_order_status_cancel_restores_inventory_via_api(self):
        self.order.payment_type = 'user_wallet'
        self.order.wallet_paid = self.order.paid_total
        from product.models import Product
        from store.models import Store
        store = Store.objects.create(user=self.staff, name="Official Store", username="official-store", status=Store.STATUS_ACTIVE, verified_at=timezone.now())
        product = Product.objects.create(store=store, title="Coffee Mug", price="15.00", discount=0, available=10, sales=1, is_digital=False)
        self.order.items_snapshot = [{"product": product.pk, "quantity": 1, "is_digital": False, "unit_price": "15.00"}]
        self.order.save()

        response = self.client.post(
            f"/staffs/orders/{self.order.pk}/status/",
            {"status": "cancelled", "reason": "Customer cancellation verified by telephone."},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "cancelled")
        product.refresh_from_db()
        self.assertEqual(product.available, 11)
        self.assertEqual(product.sales, 0)

    def test_staff_order_status_rejects_invalid_transition_via_api(self):
        response = self.client.post(
            f"/staffs/orders/{self.order.pk}/status/",
            {"status": "delivered", "reason": "Attempting jump directly from confirmed to delivered."},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_staff_digital_asset_download_from_managed_storage(self):
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        from product.models import Product
        from store.models import Store

        store = Store.objects.create(user=self.staff, name="Digital Shop", username="digital-shop", status=Store.STATUS_ACTIVE)
        path = default_storage.save("digital_products/test_doc.pdf", ContentFile(b"%PDF-1.4 sample content"))
        url = default_storage.url(path)
        product = Product.objects.create(
            store=store, title="Ebook", price="9.99", discount=0, available=0,
            is_digital=True, digital_file_url=f"http://testserver{url}",
        )

        response = self.client.get(f"/staffs/products/{product.pk}/digital-asset/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("test_doc.pdf", response.headers.get("Content-Disposition", ""))

    def test_staff_digital_asset_blocks_private_ip_ssrf(self):
        from product.models import Product
        from store.models import Store

        store = Store.objects.create(user=self.staff, name="Malicious URL Shop", username="mal-shop", status=Store.STATUS_ACTIVE)
        product = Product.objects.create(
            store=store, title="Exploit Asset", price="9.99", discount=0, available=0,
            is_digital=True, digital_file_url="http://169.254.169.254/latest/meta-data/",
        )

        response = self.client.get(f"/staffs/products/{product.pk}/digital-asset/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("prohibited", response.data.get("detail", "").lower())

    def test_staff_orders_list_search_and_filtering(self):
        # Create additional order
        other_order = Order.objects.create(
            user=self.customer, status="delivered", ordered=True,
            total="150.00", subtotal="140.00", payment_type="cash_on_delivery",
        )
        # Filter status
        res = self.client.get("/staffs/orders/?status=delivered")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["orderId"], other_order.orderId)

        # Filter payment_type
        res = self.client.get("/staffs/orders/?payment_type=cash_on_delivery")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)

        # Search by orderId
        res = self.client.get(f"/staffs/orders/?search={self.order.orderId}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)

        # Ordering by total descending
        res = self.client.get("/staffs/orders/?ordering=-total")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["results"][0]["orderId"], other_order.orderId)

    def test_staff_coupons_list_search_and_active_filtering(self):
        c1 = Coupon.objects.create(code="ALPHA10", discount=10, active=True, num_available=100, valid_to=timezone.now() + timedelta(days=5))
        c2 = Coupon.objects.create(code="BETA20", discount=20, active=False, num_available=100, valid_to=timezone.now() + timedelta(days=5))

        # Filter active
        res = self.client.get("/staffs/coupons/?active=true")
        self.assertEqual(res.status_code, 200)
        codes = [row["code"] for row in res.data["results"]]
        self.assertIn("ALPHA10", codes)
        self.assertNotIn("BETA20", codes)

        # Search code
        res = self.client.get("/staffs/coupons/?search=BETA")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["code"], "BETA20")

        # Ordering by discount
        res = self.client.get("/staffs/coupons/?ordering=-discount")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["results"][0]["code"], "BETA20")

    def test_staff_refunds_list_search_and_filtering(self):
        r1 = Refund.objects.create(email="user1@example.com", order=self.order, status=Refund.STATUS_PENDING, refund_type=Refund.REFUND_TYPE_STORE_CREDIT, reason="Wrong item")
        r2 = Refund.objects.create(email="user2@example.com", order=self.order, status=Refund.STATUS_APPROVED, refund_type=Refund.REFUND_TYPE_ORIGINAL_PAYMENT, reason="Damaged box")

        # Filter status
        res = self.client.get("/staffs/refunds/?status=pending")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["id"], r1.id)

        # Filter refund_type
        res = self.client.get("/staffs/refunds/?refund_type=original_payment")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["id"], r2.id)

        # Search reason
        res = self.client.get("/staffs/refunds/?search=Wrong")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["id"], r1.id)

    def test_platform_commission_wallet_includes_official_store_sales(self):
        from decimal import Decimal
        from store.models import Store, StoreEarningsLedger, MerchantWallet
        admin = User.objects.create_superuser(email="admin.finance@example.com", password="Admin-password-123!")
        self.client.force_authenticate(admin)

        # 3P store with $100 sale, 4% platform fee ($4.00)
        merchant_user = User.objects.create_user(email="vendor@example.com", password="passWord123!")
        third_party_store = Store.objects.create(user=merchant_user, name="Third Party Store", is_official=False)
        m_wallet = MerchantWallet.objects.create(user=merchant_user)
        StoreEarningsLedger.objects.create(
            wallet=m_wallet,
            store=third_party_store,
            entry_type=StoreEarningsLedger.TYPE_SALE,
            gross_amount=Decimal("100.00"),
            fee_amount=Decimal("4.00"),
            net_amount=Decimal("96.00"),
            status=StoreEarningsLedger.STATUS_AVAILABLE,
            reference="ORD-3P-001",
        )

        # Official store with $200 sale, 0% platform fee, $200.00 net sales
        official_store = Store.objects.create(user=admin, name="Official Store", is_official=True)
        admin_wallet = MerchantWallet.objects.create(user=admin)
        StoreEarningsLedger.objects.create(
            wallet=admin_wallet,
            store=official_store,
            entry_type=StoreEarningsLedger.TYPE_SALE,
            gross_amount=Decimal("200.00"),
            fee_amount=Decimal("0.00"),
            net_amount=Decimal("200.00"),
            status=StoreEarningsLedger.STATUS_AVAILABLE,
            reference="ORD-OFFICIAL-001",
        )

        # Query commission-wallet endpoint
        resp = self.client.get("/staffs/commission-wallet/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["marketplace_commission"], "4.00")
        self.assertEqual(resp.data["official_stores_revenue"], "200.00")
        self.assertEqual(resp.data["earned"], "204.00")
        self.assertEqual(resp.data["available"], "204.00")

        # Admin can withdraw combined treasury funds
        withdraw_resp = self.client.post("/staffs/commission-wallet/withdraw/", {
            "amount": "150.00",
            "payout_method": "stripe",
            "account_details": {"destination": "Stripe Corporate Balance"},
        }, format="json")
        self.assertEqual(withdraw_resp.status_code, 201)
        self.assertEqual(withdraw_resp.data["status"], "pending")

        # Check refreshed available balance
        resp2 = self.client.get("/staffs/commission-wallet/")
        self.assertEqual(resp2.data["available"], "54.00")
        self.assertEqual(resp2.data["withdrawn_or_pending"], "150.00")
