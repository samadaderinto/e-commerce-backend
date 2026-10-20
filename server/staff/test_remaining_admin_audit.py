from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from cart.models import Cart, CartItem
from core.models import User
from payment.models import Order
from product.models import Product
from staff.models import PlatformCommissionWithdrawal
from staff.views import historical_top_stores, treasury_earnings
from store.models import MerchantWallet, Store, StoreEarningsLedger
from store.services import process_refund_deduction


@override_settings(ROOT_URLCONF='storefront.urls')
class RemainingAdminAuditTests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(email='remaining-admin@test.local', password='test')
        self.seller = User.objects.create_user(email='remaining-seller@test.local', password='test')
        self.buyer = User.objects.create_user(email='remaining-buyer@test.local', password='test')
        self.store = Store.objects.create(user=self.seller, name='Merchant')
        self.official = Store.objects.create(user=self.admin, name='Official', is_official=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def sale(self, store: Store, status: str = 'available') -> StoreEarningsLedger:
        wallet, _ = MerchantWallet.objects.get_or_create(user=store.user)
        order = Order.objects.create(
            user=self.buyer, ordered=True, status='delivered', paid_total=100, total=100,
            items_snapshot=[{'store': store.pk, 'is_digital': True}],
        )
        if status != 'pending':
            Order.objects.filter(pk=order.pk).update(created=timezone.now() - timedelta(days=8))
        return StoreEarningsLedger.objects.create(
            wallet=wallet, store=store, order=order, entry_type='sale', status=status,
            gross_amount=100, fee_amount=0 if store.is_official else 4,
            net_amount=100 if store.is_official else 96,
        )

    def test_full_and_partial_refunds_net_once_for_both_store_types(self) -> None:
        for store in (self.store, self.official):
            sale = self.sale(store)
            process_refund_deduction(sale.order, Decimal('25'), store)
            earnings = treasury_earnings()
            self.assertEqual(earnings.total, Decimal('75') if store.is_official else Decimal('3'))
            process_refund_deduction(sale.order, Decimal('75'), store)
            self.assertEqual(treasury_earnings().total, Decimal('0'))
            self.assertEqual(treasury_earnings(include_pending=True).total, Decimal('0'))
        response = self.client.get('/api/v1/admin/staff/commission-wallet/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['earned'], '0.00')
        dashboard = self.client.get('/api/v1/admin/staff/dashboard/')
        self.assertEqual(dashboard.data['financials']['commission_earned'], '0.00')

    def test_pending_refunds_stay_out_of_cleared_treasury_and_net_escrow(self) -> None:
        sale = self.sale(self.store, 'pending')
        official_sale = self.sale(self.official, 'pending')
        process_refund_deduction(sale.order, Decimal('25'), self.store)
        process_refund_deduction(official_sale.order, Decimal('50'), self.official)
        self.assertEqual(treasury_earnings().total, Decimal('0'))
        earnings = treasury_earnings(include_pending=True)
        self.assertEqual(earnings.marketplace_commission, Decimal('3'))
        self.assertEqual(earnings.official_revenue, Decimal('50'))
        self.assertEqual(earnings.escrow, Decimal('122'))

    def test_payout_movements_and_unrelated_reversals_do_not_change_revenue(self) -> None:
        self.sale(self.store, 'completed')
        self.sale(self.official)
        self.sale(self.store, 'reversed')
        StoreEarningsLedger.objects.create(
            store=self.official, wallet=MerchantWallet.objects.get(user=self.admin),
            entry_type='payout', status='completed', net_amount=-90,
        )
        self.assertEqual(treasury_earnings().total, Decimal('104'))

    def test_available_physical_sales_still_respect_delivery_hold_for_both_store_types(self) -> None:
        for store in (self.store, self.official):
            sale = self.sale(store)
            Order.objects.filter(pk=sale.order_id).update(
                created=timezone.now() - timedelta(days=30),
                delivered_at=timezone.now() - timedelta(days=1),
                items_snapshot=[{'store': store.pk, 'is_digital': False}],
            )
        self.assertEqual(treasury_earnings().total, Decimal('0'))
        dashboard = self.client.get('/api/v1/admin/staff/dashboard/')
        self.assertEqual(dashboard.data['financials']['escrow_total'], '196.00')
        response = self.client.post('/api/v1/admin/staff/commission-wallet/withdraw/', {
            'amount': '0.01', 'payout_method': 'bank', 'bank_account_id': 1,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        Order.objects.filter(store_ledger_entries__entry_type='sale').update(
            delivered_at=timezone.now() - timedelta(days=8),
        )
        self.assertEqual(treasury_earnings().total, Decimal('104'))

    def test_disputed_available_digital_sale_remains_protected(self) -> None:
        sale = self.sale(self.store)
        Order.objects.filter(pk=sale.order_id).update(payment_disputed=True)
        self.assertEqual(treasury_earnings().total, Decimal('0'))
        self.assertEqual(treasury_earnings(include_pending=True).escrow, Decimal('96'))

    def test_wallet_and_withdrawal_share_net_amount_and_reservations(self) -> None:
        sale = self.sale(self.store)
        process_refund_deduction(sale.order, Decimal('25'), self.store)
        self.sale(self.official)
        PlatformCommissionWithdrawal.objects.create(
            amount=100, payout_method='bank', requested_by=self.admin, reference='reserved',
        )
        PlatformCommissionWithdrawal.objects.create(
            amount=999, payout_method='bank', requested_by=self.admin,
            reference='failed', status='failed',
        )
        response = self.client.get('/api/v1/admin/staff/commission-wallet/')
        self.assertEqual(response.data['earned'], '103.00')
        self.assertEqual(response.data['available'], '3.00')
        with patch('core.bank_accounts.payout_account_details', return_value={'bank_name': 'Fixture'}):
            rejected = self.client.post('/api/v1/admin/staff/commission-wallet/withdraw/', {
                'amount': '3.01', 'payout_method': 'bank', 'bank_account_id': 1,
            }, format='json')
            self.assertEqual(rejected.status_code, 400)
            accepted = self.client.post('/api/v1/admin/staff/commission-wallet/withdraw/', {
                'amount': '3.00', 'payout_method': 'bank', 'bank_account_id': 1,
            }, format='json')
            self.assertEqual(accepted.status_code, 201, accepted.data)

    def test_snapshot_ranking_survives_product_deletion_and_counts_once(self) -> None:
        product = Product.objects.create(
            store=self.store, title='Archived', price=10, discount=0, available=10,
        )
        cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=product, quantity=2)
        snapshot = [{'product': product.pk, 'store': self.store.pk}, {'store': str(self.store.pk)}]
        Order.objects.create(
            user=self.buyer, cart=cart, ordered=True, status='confirmed', items_snapshot=snapshot,
        )
        product.delete()
        row = next(row for row in historical_top_stores() if row['id'] == self.store.pk)
        self.assertEqual(row['orders'], 1)
        self.assertEqual(row['products'], 0)

    def test_legacy_cart_fallback_does_not_override_recorded_snapshots(self) -> None:
        product = Product.objects.create(
            store=self.store, title='Legacy', price=10, discount=0, available=10,
        )
        for snapshot, status, ordered in (
            ([], 'confirmed', True), ([{'store': self.official.pk}], 'confirmed', True),
            ([{'title': 'Unknown store'}], 'confirmed', True),
            ([], 'cancelled', True), ([], 'confirmed', False),
        ):
            cart = Cart.objects.create(user=self.buyer)
            CartItem.objects.create(cart=cart, product=product, quantity=1)
            Order.objects.create(
                user=self.buyer, cart=cart, ordered=ordered, status=status, items_snapshot=snapshot,
            )
        counts = {row['id']: row['orders'] for row in historical_top_stores()}
        self.assertEqual(counts[self.store.pk], 1)
        self.assertEqual(counts[self.official.pk], 1)
