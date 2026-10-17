from django.urls import include, path
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import User
from core.models import Address, Refund
from cart.models import Cart
from payment.models import Coupon, DeliveryInfo, Order
from staff.models import PlatformCommissionWithdrawal
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

    def test_staff_can_complete_and_decline_pending_payouts(self) -> None:
        from store.models import Store, StorePayout

        seller = User.objects.create_user(email='payout-owner@test.com', password='Test-password-123!')
        store = Store.objects.create(user=seller, name='Payout store')
        self.client.force_authenticate(self.staff)
        for action, expected in [('approve', 'completed'), ('reject', 'rejected')]:
            payout = StorePayout.objects.create(store=store, amount='25.00', reference=f'STAFF-{action}')
            response = self.client.post(
                f'/staffs/payouts/{payout.pk}/process/',
                {'action': action, 'reason': 'Destination could not be verified'},
                format='json',
            )
            self.assertEqual(response.status_code, 200, response.data)
            payout.refresh_from_db()
            self.assertEqual(payout.status, expected)
            self.assertEqual(payout.processed_by_id, self.staff.pk)
            repeated = self.client.post(
                f'/staffs/payouts/{payout.pk}/process/', {'action': action}, format='json',
            )
            self.assertEqual(repeated.status_code, 400)

    def test_customer_cannot_process_payout(self) -> None:
        customer = User.objects.create_user(email='payout-customer@test.com', password='Test-password-123!')
        self.client.force_authenticate(customer)
        response = self.client.post('/staffs/payouts/1/process/', {'action': 'approve'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_store_catalog_audit_includes_authoritative_product_sales(self) -> None:
        from product.models import Product
        from store.models import Store

        seller = User.objects.create_user(email='catalog-owner@test.com', password='Test-password-123!')
        store = Store.objects.create(user=seller, name='Catalog audit store')
        product = Product.objects.create(
            store=store,
            title='Tracked product',
            description='Product used to verify the audit sales count.',
            price='12.00',
            discount=0,
            available=20,
            category='books',
            sales=17,
        )
        self.client.force_authenticate(self.staff)

        response = self.client.get(f'/staffs/stores/{store.pk}/products/')

        self.assertEqual(response.status_code, 200, response.data)
        row = next(item for item in response.data['results'] if item['id'] == product.pk)
        self.assertEqual(row['sales'], 17)

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
        self.assertIn('avatar_url', payload['user'])
        self.assertIn('wallet', payload)
        self.assertIn('orders', payload)

    def test_profile_order_filters_pagination_and_unfiltered_totals(self) -> None:
        self.client.force_authenticate(self.admin)
        matching = Order.objects.create(
            user=self.staff, ordered=True, status="delivered", total="50.00",
            carrier="UPS", payment_type="card", tracking_number="PROFILE-TRACK",
        )
        Order.objects.create(user=self.staff, ordered=True, status="pending", total="20.00")
        Order.objects.create(user=self.admin, ordered=True, status="delivered", total="90.00", carrier="UPS", payment_type="card", tracking_number="PROFILE-TRACK")
        url = f"/staffs/users/{self.staff.pk}/"
        response = self.client.get(url, {
            "order_search": "PROFILE-TRACK", "order_status": "delivered",
            "order_carrier": "UPS", "order_payment": "card", "order_ordering": "total",
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row["id"] for row in response.data["orders"]], [matching.pk])
        self.assertEqual(response.data["order_count"], 1)
        self.assertEqual(response.data["total_orders"], 2)
        self.assertEqual(str(response.data["lifetime_spent"]), "70.00")
        for _ in range(15):
            Order.objects.create(user=self.staff, ordered=True, status="pending", total="1.00")
        first = self.client.get(url)
        second = self.client.get(url, {"order_offset": 15})
        self.assertEqual(first.data["order_count"], 17)
        self.assertEqual(len(first.data["orders"]), 15)
        self.assertEqual(len(second.data["orders"]), 2)
        self.assertFalse({row["id"] for row in first.data["orders"]} & {row["id"] for row in second.data["orders"]})
        for params in [{"order_offset": -1}, {"order_ordering": "user"}, {"order_status": "unknown"}]:
            self.assertEqual(self.client.get(url, params).status_code, 400)

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

    def test_staff_cannot_block_or_unblock_non_official_store(self):
        from store.models import Store
        seller = User.objects.create_user(
            email="seller-to-block@example.com",
            password="Strong-password-123!",
            first_name="Shop",
            last_name="Owner",
            gender="male",
            phone1="+2348012345677",
        )
        store = Store.objects.create(
            user=seller,
            name="Community Boutique",
            username="comm-boutique",
            status=Store.STATUS_ACTIVE,
            is_official=False,
        )
        self.client.force_authenticate(self.staff)

        # Store status changes are reserved for business and technical admins.
        res_block = self.client.post(
            f"/staffs/stores/{store.pk}/block/",
            {"reason": "Policy violation"},
            format="json",
        )
        self.assertEqual(res_block.status_code, 403, res_block.data)
        store.refresh_from_db()
        self.assertEqual(store.status, Store.STATUS_ACTIVE)

        store.status = Store.STATUS_BLOCKED
        store.blocked_reason = "Existing moderation decision"
        store.save(update_fields=["status", "blocked_reason"])
        res_unblock = self.client.post(f"/staffs/stores/{store.pk}/unblock/")
        self.assertEqual(res_unblock.status_code, 403, res_unblock.data)
        store.refresh_from_db()
        self.assertEqual(store.status, Store.STATUS_BLOCKED)

    def test_staff_cannot_block_official_store(self):
        from store.models import Store
        official_store = Store.objects.create(
            user=self.admin,
            name="ProAce Official Store",
            username="proace-official",
            status=Store.STATUS_ACTIVE,
            is_official=True,
        )
        self.client.force_authenticate(self.staff)

        # The permission guard rejects staff before store-type validation.
        res = self.client.post(
            f"/staffs/stores/{official_store.pk}/block/",
            {"reason": "Unauthorized suspension"},
            format="json",
        )
        self.assertEqual(res.status_code, 403)
        official_store.refresh_from_db()
        self.assertEqual(official_store.status, Store.STATUS_ACTIVE)

    def test_store_model_guardrail_prevents_blocking_official_store(self):
        from store.models import Store
        from django.core.exceptions import ValidationError
        official_store = Store.objects.create(
            user=self.admin,
            name="ProAce Flagship",
            username="proace-flagship",
            status=Store.STATUS_ACTIVE,
            is_official=True,
        )
        official_store.status = Store.STATUS_BLOCKED
        with self.assertRaises(ValidationError):
            official_store.save()


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

    def test_staff_permission_update_rejects_unknown_fields_without_server_error(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f"/api/v1/admin/staff/users/{self.staff.pk}/",
            {"is_active": False, "email": "attacker@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)
        self.assertEqual(self.staff.email, "frontend.staff@example.com")


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

    def test_staff_cannot_override_digital_order_to_shipped_or_revert_delivered(self):
        # 1. Delivered digital orders cannot be reverted to shipped or picked up
        delivered_digital_order = Order.objects.create(
            user=self.customer,
            status="delivered",
            ordered=True,
            total="15.00",
            subtotal="15.00",
            paid_total="15.00",
            items_snapshot=[
                {"product": 99, "title": "Digital Audio Guide", "price": "15.00", "quantity": 1, "is_digital": True}
            ],
        )
        response = self.client.post(
            f"/staffs/orders/{delivered_digital_order.pk}/status/",
            {"status": "shipped", "reason": "Accidental physical dispatch override"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("Digital orders", str(response.data))

        # 2. Digital orders stuck in shipped can transition to delivered and clear shipped_at
        shipped_digital_order = Order.objects.create(
            user=self.customer,
            status="shipped",
            ordered=True,
            total="15.00",
            subtotal="15.00",
            paid_total="15.00",
            shipped_at=timezone.now(),
            items_snapshot=[
                {"product": 99, "title": "Digital Audio Guide", "price": "15.00", "quantity": 1, "is_digital": True}
            ],
        )
        response = self.client.post(
            f"/staffs/orders/{shipped_digital_order.pk}/status/",
            {"status": "delivered", "reason": "Immediate digital access granted"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        shipped_digital_order.refresh_from_db()
        self.assertEqual(shipped_digital_order.status, "delivered")
        self.assertIsNotNone(shipped_digital_order.delivered_at)
        self.assertIsNone(shipped_digital_order.shipped_at)

    def test_staff_can_override_mixed_order_to_shipped(self):
        mixed_order = Order.objects.create(
            user=self.customer,
            status="confirmed",
            ordered=True,
            total="35.00",
            subtotal="30.00",
            paid_total="35.00",
            items_snapshot=[
                {"product": 1, "title": "Physical Shirt", "price": "20.00", "quantity": 1, "is_digital": False},
                {"product": 2, "title": "Digital Album", "price": "10.00", "quantity": 1, "is_digital": True},
            ],
        )
        response = self.client.post(
            f"/staffs/orders/{mixed_order.pk}/status/",
            {"status": "shipped", "reason": "Dispatched physical goods from warehouse"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        mixed_order.refresh_from_db()
        self.assertEqual(mixed_order.status, "shipped")
        self.assertIsNotNone(mixed_order.shipped_at)

    def test_staff_can_process_refund_only_once(self):
        refund = Refund.objects.create(
            email=self.customer.email, order=self.order, reason="Item never arrived",
        )
        response = self.client.post(f"/staffs/refunds/{refund.pk}/process/", {"action": "approve", "reason": "Approved after support review."}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        refund.refresh_from_db()
        self.assertEqual(refund.status, Refund.STATUS_APPROVED)
        self.assertEqual(refund.processed_by, self.staff)
        self.assertEqual(response.data["refund"]["processed_by_email"], self.staff.email)
        listing = self.client.get("/staffs/refunds/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["results"][0]["processed_by_email"], self.staff.email)
        response = self.client.post(f"/staffs/refunds/{refund.pk}/process/", {"action": "approve", "reason": "Duplicate approval check."}, format="json")
        self.assertEqual(response.status_code, 400, response.data)

    def test_refund_processing_requires_an_explicit_valid_decision(self):
        refund = Refund.objects.create(
            email=self.customer.email,
            order=self.order,
            reason="Item never arrived",
        )
        for payload in (
            {"reason": "Reviewed by support."},
            {"action": "complete", "reason": "Reviewed by support."},
            {"action": "decline", "reason": "   "},
        ):
            response = self.client.post(
                f"/staffs/refunds/{refund.pk}/process/",
                payload,
                format="json",
            )
            self.assertEqual(response.status_code, 400, response.data)

        refund.refresh_from_db()
        self.assertEqual(refund.status, Refund.STATUS_PENDING)

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

    def test_payout_decision_requires_explicit_valid_action_and_rejection_reason(self) -> None:
        from store.models import StorePayout

        payout = StorePayout.objects.create(
            amount="25.00",
            reference="STAFF-EXPLICIT-DECISION",
        )
        self.client.force_authenticate(self.staff)

        for payload in ({}, {"action": "complete"}, {"action": "reject"}):
            response = self.client.post(
                f"/staffs/payouts/{payout.pk}/process/",
                payload,
                format="json",
            )
            self.assertEqual(response.status_code, 400, response.data)
            payout.refresh_from_db()
            self.assertEqual(payout.status, StorePayout.STATUS_PENDING)

    def test_treasury_withdrawal_requires_a_note_and_can_be_completed_once(self) -> None:
        admin = User.objects.create_superuser(
            email='treasury-admin@example.com', password='test-password'
        )
        withdrawal = PlatformCommissionWithdrawal.objects.create(
            requested_by=self.staff,
            amount='25.00',
            payout_method='bank',
            reference='TREASURY-COMPLETE-ONCE',
        )
        self.client.force_authenticate(admin)
        path = f'/staffs/commission-wallet/withdrawals/{withdrawal.pk}/process/'

        self.client.force_authenticate(self.staff)
        forbidden = self.client.post(
            path,
            {'action': 'complete', 'note': 'Not authorized.'},
            format='json',
        )
        self.assertEqual(forbidden.status_code, 403)
        self.client.force_authenticate(admin)

        missing_note = self.client.post(path, {'action': 'complete'}, format='json')
        self.assertEqual(missing_note.status_code, 400, missing_note.data)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, PlatformCommissionWithdrawal.STATUS_PENDING)

        response = self.client.post(
            path,
            {'action': 'complete', 'note': 'Wire sent; bank reference WIRE-123.'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, PlatformCommissionWithdrawal.STATUS_COMPLETED)
        self.assertEqual(withdrawal.processed_by_id, admin.pk)
        self.assertEqual(withdrawal.processing_note, 'Wire sent; bank reference WIRE-123.')

        repeated = self.client.post(
            path,
            {'action': 'complete', 'note': 'Duplicate request.'},
            format='json',
        )
        self.assertEqual(repeated.status_code, 400)

    def test_failed_treasury_withdrawal_releases_reserved_balance(self) -> None:
        admin = User.objects.create_superuser(
            email='treasury-fail-admin@example.com', password='test-password'
        )
        withdrawal = PlatformCommissionWithdrawal.objects.create(
            requested_by=self.staff,
            amount='25.00',
            payout_method='stripe',
            reference='TREASURY-FAILED-RELEASE',
        )
        self.client.force_authenticate(admin)
        response = self.client.post(
            f'/staffs/commission-wallet/withdrawals/{withdrawal.pk}/process/',
            {'action': 'fail', 'note': 'Provider rejected the transfer.'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, PlatformCommissionWithdrawal.STATUS_FAILED)
        summary = self.client.get('/staffs/commission-wallet/').data
        self.assertEqual(summary['withdrawn_or_pending'], '0.00')

    def test_staff_orders_list_search_and_filtering(self):
        self.order.carrier = "USPS"
        self.order.save(update_fields=["carrier"])
        # Create additional order
        other_order = Order.objects.create(
            user=self.customer, status="delivered", ordered=True,
            total="150.00", subtotal="140.00", payment_type="cash_on_delivery",
            carrier="UPS",
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

        # Filter by carrier and courier query params
        res_carrier = self.client.get("/staffs/orders/?carrier=UPS")
        self.assertEqual(res_carrier.status_code, 200)
        self.assertEqual(res_carrier.data["count"], 1)
        self.assertEqual(res_carrier.data["results"][0]["orderId"], other_order.orderId)

        res_courier = self.client.get("/staffs/orders/?courier=USPS")
        self.assertEqual(res_courier.status_code, 200)
        self.assertEqual(res_courier.data["count"], 1)
        self.assertEqual(res_courier.data["results"][0]["orderId"], self.order.orderId)

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

    def test_staff_created_coupon_persists_and_shows_staff_creator(self):
        self.client.force_authenticate(self.staff)
        payload = {
            "code": "STAFFPROMO",
            "discount": 15,
            "num_available": 50,
            "valid_to": (timezone.now() + timedelta(days=10)).isoformat(),
            "active": True,
        }
        create_res = self.client.post("/staffs/coupons/", payload, format="json")
        self.assertEqual(create_res.status_code, 201)
        self.assertEqual(self.staff.email, create_res.data["created_by"])

        # Listing coupons also shows the staff creator
        list_res = self.client.get("/staffs/coupons/?search=STAFFPROMO")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(list_res.data["count"], 1)
        self.assertEqual(self.staff.email, list_res.data["results"][0]["created_by"])

    def test_coupon_creator_email_uses_authenticated_admin(self) -> None:
        admin: User = User.objects.create_superuser(email="coupon.admin@example.com", password="Test-password-123!")
        self.client.force_authenticate(admin)
        response = self.client.post("/staffs/coupons/", {
            "code": "ADMINEMAIL", "discount": 10, "num_available": 20,
            "valid_to": (timezone.now() + timedelta(days=10)).isoformat(),
            "created_by": self.staff.email,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["created_by"], admin.email)
        self.assertEqual(Coupon.objects.get(code="ADMINEMAIL").created_by_id, admin.pk)
        legacy = Coupon.objects.create(
            code="UNATTRIBUTED", discount=5, num_available=10,
            valid_to=timezone.now() + timedelta(days=10),
        )
        response = self.client.get("/staffs/coupons/", {"search": legacy.code})
        self.assertEqual(response.data["results"][0]["created_by"], "")

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
        from core.bank_accounts import bank_cipher
        from core.models import StripePayoutDestination

        stripe_destination = StripePayoutDestination.objects.create(
            user=admin,
            label='Treasury Stripe',
            account_id_encrypted=bank_cipher().encrypt(b'acct_1234567890ABCDE').decode(),
            account_id_last4='BCDE',
            is_default=True,
        )
        withdraw_resp = self.client.post("/staffs/commission-wallet/withdraw/", {
            "amount": "150.00",
            "payout_method": "stripe",
            "stripe_destination_id": stripe_destination.pk,
        }, format="json")
        self.assertEqual(withdraw_resp.status_code, 201)
        self.assertEqual(withdraw_resp.data["status"], "pending")
        self.assertEqual(
            PlatformCommissionWithdrawal.objects.get(pk=withdraw_resp.data['id']).account_details,
            {
                'destination_type': 'stripe',
                'destination': 'acct_1234567890ABCDE',
                'destination_label': 'Treasury Stripe',
            },
        )

        # Check refreshed available balance
        resp2 = self.client.get("/staffs/commission-wallet/")
        self.assertEqual(resp2.data["available"], "54.00")
        self.assertEqual(resp2.data["withdrawn_or_pending"], "150.00")

    def test_dashboard_and_user_detail_include_referral_data(self) -> None:
        from decimal import Decimal
        from affiliates.models import Marketer, Referral

        marketer_user = User.objects.create_user(email="marketer@example.com", password="PassWord123!", first_name="Top", last_name="Affiliate")
        marketer = Marketer.objects.create(user=marketer_user, name="Top Affiliate")

        referred_user = User.objects.create_user(email="newshopper@example.com", password="PassWord123!", first_name="Jane", last_name="Shopper")
        Referral.objects.create(
            marketer=marketer,
            referred_user=referred_user,
            status=Referral.REWARDED,
            reward_amount=Decimal("25.00"),
        )

        admin = User.objects.create_superuser(email="admin.referrals@example.com", password="Admin-password-123!")
        self.client.force_authenticate(admin)

        # 1. Dashboard metrics check
        dash_resp = self.client.get("/staffs/dashboard/")
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn("referrals", dash_resp.data)
        self.assertEqual(dash_resp.data["referrals"]["total"], 1)
        self.assertEqual(dash_resp.data["referrals"]["rewarded"], 1)
        self.assertEqual(dash_resp.data["referrals"]["rewarded_amount"], "25.00")

        # 2. Referred user detail check
        detail_resp = self.client.get(f"/staffs/users/{referred_user.pk}/")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertIsNotNone(detail_resp.data.get("referral"))
        self.assertEqual(detail_resp.data["referral"]["referrer_name"], "Top Affiliate")
        self.assertEqual(detail_resp.data["referral"]["status"], "rewarded")
        self.assertEqual(detail_resp.data["referral"]["reward_amount"], "25.00")
        self.assertIsNone(detail_resp.data.get("affiliate"))

        # 3. Marketer user detail check
        marketer_detail_resp = self.client.get(f"/staffs/users/{marketer_user.pk}/")
        self.assertEqual(marketer_detail_resp.status_code, 200)
        self.assertIsNotNone(marketer_detail_resp.data.get("affiliate"))
        self.assertEqual(marketer_detail_resp.data["affiliate"]["referral_count"], 1)
        self.assertEqual(marketer_detail_resp.data["affiliate"]["rewarded_count"], 1)
        self.assertEqual(marketer_detail_resp.data["affiliate"]["credit_earned"], "25.00")


@override_settings(ROOT_URLCONF=__name__)
class NotificationRecordLookupTests(TestCase):
    def test_order_lookup_is_exact_and_still_requires_operator_access(self) -> None:
        admin = User.objects.create_superuser(email="lookup-admin@test.com", password="test")
        buyer = User.objects.create_user(email="lookup-buyer@test.com", password="test")
        target = Order.objects.create(user=buyer, total="12.00")
        Order.objects.create(user=buyer, total="23.00")
        client = APIClient()
        client.force_authenticate(admin)
        response = client.get("/staffs/orders/", {"record_id": target.pk, "limit": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], target.pk)
        self.assertEqual(client.get("/staffs/orders/", {"record_id": "bad"}).status_code, 400)
        client.force_authenticate(buyer)
        self.assertEqual(client.get("/staffs/orders/", {"record_id": target.pk}).status_code, 403)

    def test_store_orders_use_snapshots_and_preserve_search_and_pagination(self) -> None:
        from store.models import Store

        admin = User.objects.create_superuser(email="store-orders-admin@test.com", password="test")
        buyer = User.objects.create_user(email="store-orders-buyer@test.com", password="test")
        store = Store.objects.create(user=buyer, name="Target store")
        other = Store.objects.create(user=buyer, name="Other store")
        first = Order.objects.create(
            user=buyer, status="confirmed", total="10.00",
            items_snapshot=[{"store": store.pk, "title": "First"}],
        )
        mixed = Order.objects.create(
            user=buyer, status="shipped", total="30.00",
            items_snapshot=[{"store": str(store.pk)}, {"store": other.pk}],
        )
        Order.objects.create(user=buyer, total="9.00", items_snapshot=[{"store": other.pk}])
        client = APIClient()
        client.force_authenticate(admin)
        response = client.get("/staffs/orders/", {"store_id": store.pk, "limit": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 1)
        response = client.get("/staffs/orders/", {"store_id": store.pk, "search": first.orderId, "status": "confirmed"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], first.pk)
        response = client.get("/staffs/orders/", {"store_id": store.pk, "record_id": mixed.pk})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(client.get("/staffs/orders/", {"store_id": "invalid"}).status_code, 400)
        self.assertEqual(client.get("/staffs/orders/", {"store_id": 9999999}).status_code, 404)
        client.force_authenticate(buyer)
        self.assertEqual(client.get("/staffs/orders/", {"store_id": store.pk}).status_code, 403)

    def test_store_orders_only_use_cart_when_snapshot_is_empty(self) -> None:
        from cart.models import CartItem
        from payment.order_filters import orders_for_store
        from product.models import Product
        from store.models import Store

        buyer = User.objects.create_user(email="legacy-store-orders@test.com", password="test")
        store = Store.objects.create(user=buyer, name="Legacy store")
        other = Store.objects.create(user=buyer, name="Other legacy store")
        product = Product.objects.create(store=store, title="Legacy product", price="10.00", discount=0, available=10)
        cart = Cart.objects.create(user=buyer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        legacy = Order.objects.create(user=buyer, cart=cart, items_snapshot=[])
        authoritative = Order.objects.create(user=buyer, cart=cart, items_snapshot=[{"store": other.pk}])
        ids = set(orders_for_store(Order.objects.all(), store.pk).values_list("pk", flat=True))
        self.assertIn(legacy.pk, ids)
        self.assertNotIn(authoritative.pk, ids)

    def test_store_payments_are_scoped_filterable_and_read_only(self) -> None:
        from store.models import MerchantWallet, Store, StoreEarningsLedger, StorePayout

        admin = User.objects.create_superuser(email="store-payments-admin@test.com", password="test")
        owner = User.objects.create_user(email="store-payments-owner@test.com", password="test")
        store = Store.objects.create(user=owner, name="Payments store")
        other = Store.objects.create(user=owner, name="Other payments store")
        wallet = MerchantWallet.objects.create(user=owner)
        entry = StoreEarningsLedger.objects.create(
            wallet=wallet, store=store, entry_type="sale", gross_amount="10.00",
            fee_amount="0.40", net_amount="9.60", status="available", reference="STORE-SALE",
        )
        StoreEarningsLedger.objects.create(wallet=wallet, store=other, gross_amount="900.00", net_amount="900.00", reference="FOREIGN-SALE")
        payout = StorePayout.objects.create(store=store, wallet=wallet, amount="2.00", reference="STORE-PAYOUT")
        StorePayout.objects.create(store=other, wallet=wallet, amount="100.00", reference="FOREIGN-PAYOUT")
        StorePayout.objects.create(wallet=wallet, amount="200.00", reference="WALLET-PAYOUT")
        client = APIClient()
        client.force_authenticate(admin)
        summary = client.get(f"/staffs/stores/{store.pk}/financials/")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.data["gross_sales"], "10.00")
        self.assertEqual(summary.data["in_review"], "0.00")
        self.assertEqual(summary.data["payouts_pending"], "2.00")
        ledger = client.get(f"/staffs/stores/{store.pk}/ledger/", {"search": "STORE-SALE", "status": "available", "entry_type": "sale", "min_amount": "9", "limit": 1})
        self.assertEqual(ledger.status_code, 200)
        self.assertEqual(ledger.data["count"], 1)
        self.assertEqual(ledger.data["results"][0]["id"], entry.pk)
        hidden = client.get(f"/staffs/stores/{store.pk}/ledger/", {"search": "FOREIGN"})
        self.assertEqual(hidden.data["count"], 0)
        payouts = client.get("/staffs/payouts/", {"store_id": store.pk, "record_id": payout.pk, "status": "pending"})
        self.assertEqual(payouts.data["count"], 1)
        self.assertEqual(payouts.data["results"][0]["id"], payout.pk)
        self.assertEqual(client.get(f"/staffs/stores/{store.pk}/ledger/", {"start_date": "invalid"}).status_code, 400)
        self.assertEqual(client.post(f"/staffs/stores/{store.pk}/financials/", {}).status_code, 405)
        self.assertEqual(client.get("/staffs/payouts/", {"store_id": "invalid"}).status_code, 400)
        for url in [f"/staffs/stores/{store.pk}/financials/", f"/staffs/stores/{store.pk}/ledger/", f"/staffs/payouts/?store_id={store.pk}"]:
            client.force_authenticate(owner)
            self.assertEqual(client.get(url).status_code, 403)
        client.force_authenticate(admin)
        self.assertEqual(client.get("/staffs/stores/9999999/financials/").status_code, 404)
