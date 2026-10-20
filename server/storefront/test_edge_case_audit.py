"""Reproduce boundary failures found in the comprehensive commerce audit."""

from datetime import timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from django.core import signing
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from cart.models import Cart, CartItem
from core.models import Address, Refund, User, UserWalletTransaction
from core.social_auth import authenticate_social_user, verify_google_credential
from payment.fulfillment import update_fulfillment
from payment.models import Order, OrderFulfillment
from payment.services import process_order_refund, validate_return_window
from payment.shipping_quotes import cart_rates, issue_quote, verify_quote
from product.models import Product
from store.models import Store, StoreAddress
from storefront.views import tokens

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from tempfile import TemporaryDirectory
from notification.models import NotificationDelivery
from store.models import MerchantWallet, StorePayout
from store.services import process_payout_status_change


@override_settings(ROOT_URLCONF='storefront.urls', STRIPE_SECRET='sk_test_audit')
class EdgeCaseAuditTests(TestCase):
    def setUp(self) -> None:
        self.buyer = User.objects.create_user(email='edge-buyer@test.com', password='test')
        self.seller = User.objects.create_user(email='edge-seller@test.com', password='test')
        self.store = Store.objects.create(
            user=self.seller, name='Edge store', status='active', verified_at=timezone.now(),
        )
        self.origin = StoreAddress.objects.create(
            store=self.store, address='1 Test St', city='Tampa', state='FL',
            country='US', zip='33602', is_default=True,
        )
        self.product = Product.objects.create(
            store=self.store, title='Edge item', price=Decimal('10'), discount=0, available=10,
        )
        self.address = Address.objects.create(
            user=self.buyer, address='2 Test St', city='Tampa', state='FL', country='US', zip='33601',
        )
        self.cart = Cart.objects.create(user=self.buyer)
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)

    def order(self, digital: bool = False) -> Order:
        return Order.objects.create(
            user=self.buyer, status='delivered', ordered=True,
            total=10, paid_total=10, wallet_paid=10, payment_type='user_wallet',
            items_snapshot=[{
                'product': self.product.pk, 'store': self.store.pk, 'title': 'Edge item',
                'quantity': 1, 'unit_price': '10', 'net_total': '10', 'line_total': '10',
                'variant': '', 'is_digital': digital,
            }],
        )

    def test_partner_listing_is_rejected_in_cart_and_existing_cart_checkout(self) -> None:
        self.product.product_type = Product.PRODUCT_TYPE_AFFILIATE_CLICKBANK
        self.product.save()
        response = self.client.post('/api/v1/cart/', {'product': self.product.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.cart.cart_items.exists())
        CartItem.objects.create(cart=self.cart, product=self.product)
        self.assertFalse(self.client.get('/api/v1/cart/').data['items'][0]['purchasable'])
        response = self.client.post('/api/v1/checkout/', {
            'checkout_key': str(uuid4()), 'payment_type': 'user_wallet', 'address': self.address.pk,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_removed_variant_cart_remains_readable_and_removable(self) -> None:
        self.product.variants = [{'name': 'New', 'available': 10, 'price_delta': '0'}]
        self.product.save()
        CartItem.objects.create(cart=self.cart, product=self.product, variant='Retired')
        response = self.client.get('/api/v1/cart/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['items'][0]['purchasable'])
        response = self.client.delete(
            f'/api/v1/cart/?product={self.product.pk}&variant=Retired',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['items'], [])

    def test_variant_stock_exhaustion_marks_existing_cart_unpurchasable(self) -> None:
        self.product.variants = [{'name': 'Large', 'available': 0, 'price_delta': '0'}]
        self.product.save()
        CartItem.objects.create(cart=self.cart, product=self.product, variant='Large')
        self.assertFalse(self.client.get('/api/v1/cart/').data['items'][0]['purchasable'])

    def test_repeated_digital_addition_never_increases_entitlement_quantity(self) -> None:
        self.product.is_digital = True
        self.product.digital_file_url = 'digital_products/edge.txt'
        self.product.save()
        for _ in range(2):
            response = self.client.post('/api/v1/cart/', {
                'product': self.product.pk, 'quantity': 5,
            }, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['items'][0]['quantity'], 1)

    def test_social_login_cannot_reactivate_inactive_accounts(self) -> None:
        self.buyer.is_active = False
        self.buyer.save()
        for provider in ('google', 'apple'):
            with self.assertRaises(PermissionDenied):
                authenticate_social_user(provider, {'credential': f'dev-{provider}:{self.buyer.email}'})
        self.buyer.refresh_from_db()
        self.assertFalse(self.buyer.is_active)

    def test_verification_link_is_one_use_and_cannot_undo_deactivation(self) -> None:
        self.buyer.is_active = False
        self.buyer.save()
        token = signing.dumps({'user': self.buyer.pk, 'version': self.buyer.credential_version}, salt='proace-verify')
        self.client.force_authenticate(None)
        response = self.client.post('/api/v1/auth/verify/', {'token': token}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post('/api/v1/auth/verify/', {'token': token}, format='json').status_code, 400)
        self.buyer.refresh_from_db()
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.delete('/api/v1/me/').status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post('/api/v1/auth/verify/', {'token': token}, format='json').status_code, 400)
        self.buyer.refresh_from_db()
        self.assertFalse(self.buyer.is_active)

    def test_revoked_credential_version_cannot_refresh(self) -> None:
        refresh = tokens(self.buyer)['refresh']
        self.buyer.credential_version += 1
        self.buyer.save()
        self.client.force_authenticate(None)
        response = self.client.post('/api/v1/auth/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(response.status_code, 401)

    def test_delivery_not_creation_starts_return_window_and_edit_uses_same_clock(self) -> None:
        order = self.order()
        Order.objects.filter(pk=order.pk).update(
            created=timezone.now() - timedelta(days=30), delivered_at=timezone.now() - timedelta(days=1),
        )
        response = self.client.post(f'/api/v1/orders/{order.pk}/refund/', {
            'reason': 'item_damaged', 'product_ids': [self.product.pk],
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        response = self.client.patch(f'/api/v1/orders/{order.pk}/refund/', {
            'reason': 'wrong_item_received',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_store_delivery_controls_return_clock_for_multistore_orders(self) -> None:
        order = self.order()
        order.delivered_at = timezone.now()
        order.save()
        OrderFulfillment.objects.create(
            order=order, store=self.store, status='delivered',
            delivered_at=timezone.now() - timedelta(days=8),
        )
        with self.assertRaises(ValidationError):
            validate_return_window(order, order.items_snapshot)

    def test_tracking_edit_does_not_extend_delivery_timestamp(self) -> None:
        order = self.order()
        delivered = timezone.now() - timedelta(days=5)
        order.delivered_at = delivered
        order.save()
        OrderFulfillment.objects.create(order=order, store=self.store, status='delivered', delivered_at=delivered)
        update_fulfillment(order, self.store, 'delivered', 'USPS', 'real-test-tracking')
        self.assertEqual(order.delivered_at, delivered)

    def test_digital_only_merchant_tracking_returns_validation_error(self) -> None:
        order = self.order(digital=True)
        self.client.force_authenticate(self.seller)
        response = self.client.post(f'/api/v1/stores/{self.store.pk}/orders/{order.pk}/tracking/', {
            'status': 'shipped', 'carrier': 'USPS', 'tracking_number': 'test',
        }, format='json')
        self.assertEqual(response.status_code, 400, response.data)

    def test_parcel_and_origin_changes_invalidate_quotes(self) -> None:
        CartItem.objects.create(cart=self.cart, product=self.product)
        rate = {'service_id': 'usps_ground_advantage', 'amount': '5.00', 'carrier': 'USPS'}
        for model, field, value in [(self.product, 'length', Decimal('20')), (self.origin, 'zip', '10001')]:
            token = issue_quote(rate, self.buyer, self.cart, self.address)
            setattr(model, field, value)
            model.save()
            with self.assertRaises(ValidationError):
                verify_quote(token, self.buyer, self.cart, self.address, rate['service_id'])

    @patch('payment.carriers.calculate_carrier_rates')
    def test_stores_in_same_zip_have_separate_shipments(self, quote: Any) -> None:
        second = Store.objects.create(user=self.seller, name='Second', status='active', verified_at=timezone.now())
        StoreAddress.objects.create(store=second, address='3 Test St', city='Tampa', state='FL', country='US', zip='33602', is_default=True)
        other = Product.objects.create(store=second, title='Other', price=10, discount=0, available=10)
        CartItem.objects.create(cart=self.cart, product=self.product)
        CartItem.objects.create(cart=self.cart, product=other)
        quote.side_effect = lambda *args: [{'service_id': 'usps_ground_advantage', 'carrier': 'USPS', 'amount': '5.00'}]
        rates = cart_rates('USPS', self.cart, self.address)
        self.assertEqual(quote.call_count, 2)
        self.assertEqual(rates[0]['amount'], '10.00')
        self.assertEqual(len(rates[0]['shipments']), 2)

    @patch('payment.services.call_stripe_refund', side_effect=RuntimeError('SECRET database password'))
    def test_refund_errors_and_persisted_customer_details_do_not_leak_internals(self, provider: Any) -> None:
        order = self.order()
        order.payment_type = 'card'
        order.wallet_paid = 0
        order.save()
        refund = Refund.objects.create(order=order, email=self.buyer.email, reason='Damaged', refund_type='original_payment')
        with self.assertRaises(ValidationError) as error:
            process_order_refund(refund, self.seller)
        refund.refresh_from_db()
        self.assertEqual(refund.status, 'failed')
        self.assertNotIn('SECRET', str(error.exception))
        self.assertNotIn('SECRET', refund.failure_reason)

    @patch('core.social_auth.requests.get')
    def test_malformed_google_provider_response_is_a_clean_validation_error(self, provider: Any) -> None:
        provider.return_value.status_code = 200
        provider.return_value.json.return_value = []
        with self.assertRaises(ValidationError):
            verify_google_credential('not-a-development-token')

    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_audit')
    def test_unsigned_webhook_cannot_credit_a_wallet(self) -> None:
        response = self.client.post('/api/v1/stripe/webhook/', {
            'type': 'checkout.session.completed', 'data': {'object': {
                'id': 'cs_forged', 'payment_status': 'paid', 'currency': 'usd',
                'amount_total': 50000, 'client_reference_id': str(self.buyer.pk),
                'metadata': {'wallet_topup': 'true'},
            }},
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(UserWalletTransaction.objects.filter(wallet__user=self.buyer).exists())

    @override_settings(STRIPE_WEBHOOK_SECRET='')
    def test_unconfigured_webhook_is_unavailable(self) -> None:
        response = self.client.post('/api/v1/stripe/webhook/', {}, format='json')
        self.assertEqual(response.status_code, 503)

    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_audit')
    @patch('storefront.views.stripe.Webhook.construct_event', side_effect=ValueError('SECRET signature'))
    def test_invalid_webhook_signature_does_not_leak_provider_details(self, verify: Any) -> None:
        response = self.client.post('/api/v1/stripe/webhook/', {}, format='json', HTTP_STRIPE_SIGNATURE='invalid')
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('SECRET', str(response.data))

    def test_treasury_rejects_invalid_amounts_and_payloads(self) -> None:
        admin = User.objects.create_superuser(email='edge-admin@test.com', password='test')
        self.client.force_authenticate(admin)
        for amount in ('NaN', 'Infinity', 'abc', '-1', '0', '1.001', '99999999999999999999'):
            response = self.client.post('/api/v1/admin/staff/commission-wallet/withdraw/', {'amount': amount}, format='json')
            self.assertEqual(response.status_code, 400, response.data)

    @patch('stripe.Transfer.create')
    def test_bank_payout_does_not_use_stripe_even_when_connected(self, transfer: Any) -> None:
        from store.models import StoreEarningsLedger

        wallet = MerchantWallet.objects.create(user=self.seller, stripe_account_id='acct_test')
        StoreEarningsLedger.objects.create(
            wallet=wallet, store=self.store, gross_amount=5, net_amount=5,
            status=StoreEarningsLedger.STATUS_AVAILABLE,
        )
        payout = StorePayout.objects.create(wallet=wallet, store=self.store, amount=5, reference='edge-bank', payout_method='bank_transfer')
        process_payout_status_change(payout, 'approve', self.seller)
        transfer.assert_not_called()

    def test_unconfigured_stripe_payout_is_not_marked_completed(self) -> None:
        wallet = MerchantWallet.objects.create(user=self.seller)
        payout = StorePayout.objects.create(wallet=wallet, store=self.store, amount=5, reference='edge-stripe', payout_method='stripe_connect')
        with self.assertRaises(ValidationError):
            process_payout_status_change(payout, 'approve', self.seller)
        payout.refresh_from_db()
        self.assertEqual(payout.status, 'pending')

    @patch('stripe.Transfer.create')
    def test_stripe_payout_requires_connected_account_payouts_enabled(self, transfer: Any) -> None:
        from unittest.mock import patch as mock_patch
        from store.models import StoreEarningsLedger

        wallet = MerchantWallet.objects.create(
            user=self.seller,
            stripe_account_id='acct_test_pending',
            stripe_details_submitted=True,
            stripe_payouts_enabled=True,
        )
        StoreEarningsLedger.objects.create(
            wallet=wallet, store=self.store, gross_amount=5, net_amount=5,
            status=StoreEarningsLedger.STATUS_AVAILABLE,
        )
        payout = StorePayout.objects.create(
            wallet=wallet,
            store=self.store,
            amount=5,
            reference='edge-stripe-pending',
            payout_method=StorePayout.METHOD_STRIPE_CONNECT,
        )

        with mock_patch(
            'stripe.Account.retrieve',
            return_value={
                'details_submitted': True,
                'payouts_enabled': False,
            },
        ) as retrieve:
            with self.assertRaises(ValidationError):
                process_payout_status_change(payout, 'approve', self.seller)

        payout.refresh_from_db()
        self.assertEqual(payout.status, StorePayout.STATUS_PENDING)
        retrieve.assert_called_once_with('acct_test_pending')
        transfer.assert_not_called()

    def test_account_closure_receipt_is_escaped_and_matches_retained_data(self) -> None:
        self.buyer.first_name = '<script>bad()</script>'
        self.buyer.save()
        order = self.order(digital=True)
        self.client.delete('/api/v1/me/')
        receipt = NotificationDelivery.objects.filter(recipient=self.buyer).latest('pk')
        self.assertNotIn('<script>', receipt.body)
        self.assertIn('&lt;script&gt;', receipt.body)
        self.assertNotIn('permanently deleted', receipt.body)
        self.assertNotIn('anonymized archival', receipt.body)
        self.assertTrue(Order.objects.filter(pk=order.pk, user=self.buyer).exists())

    def test_paid_snapshot_download_survives_deleted_listing(self) -> None:
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            path = default_storage.save('digital_products/original.txt', ContentFile(b'original purchase'))
            order = self.order(digital=True)
            order.items_snapshot[0]['download_url'] = path
            order.save()
            product_id = self.product.pk
            self.product.delete()
            response = self.client.get(f'/api/v1/orders/{order.pk}/downloads/{product_id}/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'original purchase')

    def test_merchant_cannot_reference_another_products_uploaded_asset(self) -> None:
        self.product.is_digital = True
        self.product.digital_file_url = 'https://example.com/original.pdf'
        self.product.save()
        self.client.force_authenticate(self.seller)
        response = self.client.patch(f'/api/v1/stores/{self.store.pk}/products/{self.product.pk}/', {
            'digital_file_url': 'digital_products/999/999/stolen.pdf',
        }, format='json')
        self.assertEqual(response.status_code, 400, response.data)
