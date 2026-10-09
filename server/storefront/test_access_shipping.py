import re
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import User, Address
from core.onboarding import invite_staff
from notification.models import NotificationDelivery
from payment.models import Order
from payment.carriers import live_rates, calculate_carrier_rates
from store.models import Store, StoreAddress
from product.models import Product


@override_settings(ROOT_URLCONF='storefront.urls')
class AccessAndShippingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='root@test.com', password='Root-password-123!')
        self.business = User.objects.create_staffuser(email='business@test.com', password='Business-password-123!', is_business_admin=True)
        self.staff = User.objects.create_staffuser(email='staff@test.com', password='Staff-password-123!')
        self.buyer = User.objects.create_user(email='buyer@test.com', password='Buyer-password-123!')
        self.seller = User.objects.create_user(email='seller@test.com', password='Seller-password-123!')
        self.store = Store.objects.create(user=self.seller, name='Store', status='active', verified_at=timezone.now())
        StoreAddress.objects.create(store=self.store, is_default=True, **{'address': '1 Main St', 'city': 'Tampa', 'state': 'FL', 'country': 'US', 'zip': '33602'})
        self.product = Product.objects.create(store=self.store, title='Product', price=Decimal('20'), discount=0, available=10, weight=Decimal('2'))
        self.address = Address.objects.create(user=self.buyer, address='123 Test St', zip='33601', country='US', state='FL', city='Tampa')
        self.client = APIClient()

    def test_backoffice_roles_cannot_shop_or_store_personal_addresses(self):
        for user in [self.admin, self.business, self.staff]:
            self.client.force_authenticate(user)
            for path in ['cart', 'wishlist', 'addresses', 'orders', 'wallet', 'checkout/shipping-rates']:
                with self.subTest(user=user.role, path=path):
                    self.assertEqual(self.client.get(f'/api/v1/{path}/').status_code, 403)
            self.assertEqual(self.client.post('/api/v1/cart/', {'product': self.product.pk, 'quantity': 1}).status_code, 403)
            self.assertEqual(self.client.post('/api/v1/checkout/', {}).status_code, 403)

    def test_admin_peers_are_not_listed_or_mutable(self):
        self.client.force_authenticate(self.business)
        listing = self.client.get('/api/v1/admin/staff/').data['results']
        self.assertEqual([row['id'] for row in listing], [self.staff.pk])
        for target in [self.admin, self.business]:
            self.assertEqual(self.client.post(f'/api/v1/admin/staff/{target.pk}/block/').status_code, 404)
            self.assertEqual(self.client.patch(f'/api/v1/admin/staff/users/{target.pk}/', {'is_active': False}, format='json').status_code, 400)
            target.refresh_from_db()
            self.assertTrue(target.is_active)

    def test_staff_store_assignment_controls_product_and_order_access(self):
        self.client.force_authenticate(self.staff)
        # Staff locked out of third-party store
        self.assertEqual(self.client.get('/api/v1/stores/').data['count'], 0)
        self.assertEqual(self.client.get(f'/api/v1/stores/{self.store.pk}/products/').status_code, 404)
        self.store.assigned_staff.add(self.staff)
        # Assignment deprecated: staff still locked out of third-party seller interface
        self.assertEqual(self.client.get('/api/v1/stores/').data['count'], 0)
        self.assertEqual(self.client.get(f'/api/v1/stores/{self.store.pk}/products/').status_code, 404)

        # Proace Official Store: all staff automatically granted access upon login
        official_store = Store.objects.create(
            user=self.admin, name='Official Store', is_official=True, status='active', verified_at=timezone.now()
        )
        prod = Product.objects.create(store=official_store, title='Official Product', price=Decimal('30'), discount=0, available=5)
        self.assertEqual(self.client.get('/api/v1/stores/').data['count'], 1)
        self.assertEqual(self.client.get(f'/api/v1/stores/{official_store.pk}/products/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/v1/products/{prod.pk}/').status_code, 200)

        # Staff cannot create stores, delete stores, or approve sellers
        self.assertEqual(self.client.post('/api/v1/stores/', {'name': 'Forbidden', 'username': 'forbidden', 'address': {'address': '1 Main St', 'city': 'Tampa', 'state': 'FL', 'country': 'US', 'zip': '33602'}}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/v1/stores/{official_store.pk}/delete/').status_code, 403)
        self.assertEqual(self.client.post(f'/api/v1/admin/stores/{self.store.pk}/approve/').status_code, 403)

    def test_invitation_verification_then_credentials_then_mandatory_change(self):
        self.client.force_authenticate(self.business)
        response = self.client.post('/api/v1/admin/staff/', {'email': 'invited@test.com', 'first_name': 'Invited', 'last_name': 'Staff', 'phone1': '+2348012345678', 'gender': 'female'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn('password', response.data)
        self.assertNotIn('staff_invitation_secret', response.data)
        user = User.objects.get(email='invited@test.com')
        self.assertFalse(user.is_active)
        self.assertEqual(self.client.post(f'/api/v1/admin/staff/{user.pk}/unblock/').status_code, 400)
        delivery = NotificationDelivery.objects.get(recipient=user)
        token = delivery.body.split('?token=')[1]
        self.client.force_authenticate(None)
        verified = self.client.post('/api/v1/auth/verify/', {'token': token}, format='json')
        self.assertEqual(verified.status_code, 200, verified.data)
        self.assertEqual(len(mail.outbox), 1)
        password = re.search(r'Temporary password: ([^\n]+)', mail.outbox[0].body).group(1)
        self.assertNotIn(password, delivery.body)
        self.assertIn('Forgot Password', mail.outbox[0].body)
        self.assertEqual(self.client.post('/api/v1/auth/verify/', {'token': token}, format='json').status_code, 400)
        login = self.client.post('/api/v1/auth/login/', {'email': user.email, 'password': password}, format='json')
        self.assertEqual(login.status_code, 200)
        access = login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        self.assertEqual(self.client.get('/api/v1/admin/staff/dashboard/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/me/').status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.staff_email_verified)
        self.assertEqual(user.staff_invitation_secret, '')


    def test_missing_store_address_blocks_digital_and_physical_sales(self) -> None:
        self.client.force_authenticate(self.buyer)
        StoreAddress.objects.filter(store=self.store).delete()
        for digital in (False, True):
            self.product.is_digital = digital
            self.product.save()
            response = self.client.post('/api/v1/cart/', {'product': self.product.pk, 'quantity': 1}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('store_address', response.data['error']['details'])

    def test_shipping_quotes_do_not_fall_back_to_tampa(self) -> None:
        self.client.force_authenticate(self.buyer)
        self.client.post('/api/v1/cart/', {'product': self.product.pk, 'quantity': 1}, format='json')
        StoreAddress.objects.filter(store=self.store).delete()
        response = self.client.get(f'/api/v1/checkout/shipping-rates/?address={self.address.pk}&carrier=UPS')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('store_address', response.data['error']['details'])

    def test_military_address_consistency_and_partial_updates(self) -> None:
        self.client.force_authenticate(self.buyer)
        for city, state, zipcode in [('Djibouti', 'AE', '09012'), ('APO', 'CA', '90210'), ('APO', 'AE', '90210')]:
            response = self.client.post('/api/v1/addresses/', {'address': 'Unit 1 Box 2', 'city': city, 'state': state, 'zip': zipcode, 'country': 'US'}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        response = self.client.post('/api/v1/addresses/', {'address': 'Unit 1 Box 2', 'city': 'APO', 'state': 'AE', 'zip': '09012', 'country': 'US'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        response = self.client.patch(f"/api/v1/addresses/{response.data['id']}/", {'zip': '90210'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)

    def test_military_carriers_blocked_in_demo_live_and_checkout(self) -> None:
        from payment.carriers import calculate_carrier_rates
        from rest_framework.exceptions import ValidationError
        for mode in ('demo', 'live'):
            with override_settings(SHIPPING_RATE_MODE=mode):
                for carrier in ('UPS', 'FEDEX', 'DHL'):
                    with self.assertRaises(ValidationError):
                        calculate_carrier_rates(carrier, '33602', '09012', Decimal('1'), Decimal('20'), True)
        self.address.city, self.address.state, self.address.zip = 'APO', 'AE', '09012'
        self.address.save()
        self.client.force_authenticate(self.buyer)
        self.client.post('/api/v1/cart/', {'product': self.product.pk, 'quantity': 1}, format='json')
        for carrier in ('UPS', 'FEDEX', 'DHL'):
            response = self.client.get(f'/api/v1/checkout/shipping-rates/?address={self.address.pk}&carrier={carrier}')
            self.assertEqual(response.status_code, 400, response.data)
            response = self.client.post('/api/v1/checkout/', {'address': self.address.pk, 'checkout_key': str(uuid4()), 'shipping_service': carrier.lower() + '_03'}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(self.client.get(f'/api/v1/checkout/shipping-rates/?address={self.address.pk}&carrier=USPS').status_code, 200)

    def test_preexisting_commercial_quote_cannot_pay_for_military_delivery(self) -> None:
        from payment.shipping_quotes import issue_quote
        from cart.models import Cart
        self.address.city, self.address.state, self.address.zip = 'APO', 'AE', '09012'
        self.address.save()
        self.client.force_authenticate(self.buyer)
        self.client.post('/api/v1/cart/', {'product': self.product.pk, 'quantity': 1}, format='json')
        cart = Cart.objects.get(user=self.buyer, ordered=False)
        token = issue_quote({'carrier': 'UPS', 'service_id': 'ups_03', 'amount': '8.00'}, self.buyer, cart, self.address)
        response = self.client.post('/api/v1/checkout/', {'address': self.address.pk, 'checkout_key': str(uuid4()), 'shipping_service': 'ups_03', 'shipping_quote': token}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('carrier', response.data['error']['details'])
        self.product.refresh_from_db()
        self.assertEqual(self.product.available, 10)
        self.assertFalse(Order.objects.filter(user=self.buyer).exists())

    def rates(self, carrier='UPS'):
        self.client.force_authenticate(self.buyer)
        self.client.post('/api/v1/cart/', {'product': self.product.pk, 'quantity': 1}, format='json')
        response = self.client.get(f'/api/v1/checkout/shipping-rates/?address={self.address.pk}&carrier={carrier}')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_quote_is_preserved_in_order_and_price_is_server_validated(self):
        rate = self.rates()[0]
        self.assertLess(len(rate['quote_token']), 500)
        response = self.client.post('/api/v1/checkout/', {'address': self.address.pk, 'checkout_key': str(uuid4()), 'shipping_service': rate['service_id'], 'shipping_quote': rate['quote_token'], 'amount': '0.01'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data['id'])
        self.assertEqual(order.total, Decimal('20') + Decimal(rate['amount']))
        self.assertEqual(order.delivery.total, Decimal(rate['amount']))
        self.assertEqual(order.carrier, 'UPS')
        self.assertEqual(order.shipping_snapshot['service_id'], rate['service_id'])

    def test_quote_rejects_changed_cart_and_forged_service(self):
        rate = self.rates()[0]
        self.client.post('/api/v1/cart/', {'product': self.product.pk, 'quantity': 1}, format='json')
        response = self.client.post('/api/v1/checkout/', {'address': self.address.pk, 'checkout_key': str(uuid4()), 'shipping_service': rate['service_id'], 'shipping_quote': rate['quote_token']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        response = self.client.post('/api/v1/checkout/', {'address': self.address.pk, 'checkout_key': str(uuid4()), 'shipping_service': 'ups_free_hacked'}, format='json')
        self.assertEqual(response.status_code, 400)

    @override_settings(CHECKOUT_TAX_RATE=Decimal('.1'))
    def test_shipping_quote_includes_configured_tax(self):
        rate = self.rates()[0]
        self.assertEqual(rate['tax'], '2.00')
        response = self.client.post('/api/v1/checkout/', {'address': self.address.pk, 'checkout_key': str(uuid4()), 'shipping_service': rate['service_id'], 'shipping_quote': rate['quote_token']}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.data['total']), Decimal('22') + Decimal(rate['amount']))

    @patch('payment.carriers.live_rates', side_effect=ValueError('unavailable'))
    @patch.dict('os.environ', {'SHIPPING_RATE_MODE': 'live'})
    def test_live_failure_does_not_fall_back_to_demo(self, mocked):
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            calculate_carrier_rates('UPS', '33602', '33601', Decimal('1'), Decimal('20'), True)

    @patch('payment.carriers.live_rates')
    def test_multi_origin_cart_sums_each_shipment(self, mocked):
        mocked.return_value = [{'service_id': 'ups_03', 'name': 'UPS Ground', 'amount': '8.00', 'carrier': 'UPS', 'currency': 'USD', 'source': 'live'}]
        other = Store.objects.create(user=self.seller, name='Second', status='active', verified_at=timezone.now())
        StoreAddress.objects.create(store=other, is_default=True, zip='10001', country='US', state='NY', city='New York', address='Test')
        product = Product.objects.create(store=other, title='Other', price='10', discount=0, available=2)
        self.client.force_authenticate(self.buyer)
        self.client.post('/api/v1/cart/', {'product': product.pk, 'quantity': 1}, format='json')
        with patch.dict('os.environ', {'SHIPPING_RATE_MODE': 'live'}):
            rate = self.rates()[0]
        self.assertEqual(rate['amount'], '16.00')
        self.assertEqual(len(rate['shipments']), 2)
        self.assertEqual(mocked.call_count, 2)

    @patch('storefront.views.stripe.checkout.Session.retrieve')
    @patch('storefront.views.stripe.checkout.Session.create')
    @override_settings(STRIPE_SECRET='sk_test_placeholder')
    def test_stripe_payment_intent_metadata_and_paid_quote_reuse(self, create_session, retrieve_session):
        from types import SimpleNamespace
        rate = self.rates('FEDEX')[0]
        create_session.return_value = SimpleNamespace(id='cs_test', url='https://checkout.stripe.test')
        response = self.client.post('/api/v1/checkout/wallet-session/', {'address': self.address.pk, 'checkout_key': str(uuid4()), 'shipping_service': rate['service_id'], 'shipping_quote': rate['quote_token']}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        args = create_session.call_args.kwargs
        self.assertEqual(args['payment_intent_data']['metadata'], args['metadata'])
        self.assertEqual(args['metadata']['carrier'], 'FEDEX')
        retrieve_session.return_value = {'currency': 'usd', 'payment_status': 'paid', 'client_reference_id': str(self.buyer.pk),
                                         'metadata': args['metadata'], 'amount_total': args['line_items'][0]['price_data']['unit_amount']}
        with patch('payment.carriers.live_rates', side_effect=AssertionError('Paid quote must not be rerated')):
            response = self.client.post('/api/v1/checkout/wallet-confirm/', {'session_id': 'cs_test'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Order.objects.get(pk=response.data['id']).shipping_snapshot['amount'], rate['amount'])

    def test_quote_rejects_other_customer_and_changed_address(self):
        rate = self.rates()[0]
        self.address.city = 'Changed destination'
        self.address.save()
        response = self.client.post('/api/v1/checkout/', {'address': self.address.pk, 'checkout_key': str(uuid4()), 'shipping_service': rate['service_id'], 'shipping_quote': rate['quote_token']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)


from django.test import SimpleTestCase


@patch.dict('os.environ', {'SHIPPING_SANDBOX': 'true', 'USPS_CLIENT_ID': 'test', 'USPS_CLIENT_SECRET': 'test',
                           'UPS_CLIENT_ID': 'test', 'UPS_CLIENT_SECRET': 'test', 'UPS_ACCOUNT_NUMBER': 'test',
                           'FEDEX_CLIENT_ID': 'test', 'FEDEX_CLIENT_SECRET': 'test', 'FEDEX_ACCOUNT_NUMBER': 'test',
                           'DHL_API_KEY': 'test', 'DHL_API_SECRET': 'test', 'DHL_ACCOUNT_NUMBER': 'test'})
class CarrierAdapterTests(SimpleTestCase):
    @patch('payment.carriers.request_json')
    def test_usps_oauth_and_v3_prices(self, request):
        request.side_effect = [{'access_token': 'test'}, {'totalBasePrice': 5.5}, {'totalBasePrice': 9.5}, {'totalBasePrice': 30}]
        rates = live_rates('USPS', '33602', '33601', Decimal('2'))
        self.assertEqual(len(rates), 3)
        self.assertEqual(rates[0]['amount'], '5.50')
        self.assertIn('/prices/v3/base-rates/search', request.call_args.args[0])
        self.assertEqual(request.call_args.kwargs['data']['weight'], 2.0)

    @patch('payment.carriers.request_json')
    def test_ups_singleton_rating_response(self, request):
        request.side_effect = [{'access_token': 'test'}, {'RateResponse': {'RatedShipment': {'Service': {'Code': '03'}, 'TotalCharges': {'MonetaryValue': '8.25', 'CurrencyCode': 'USD'}}}}]
        rate = live_rates('UPS', '33602', '33601', Decimal('2'))[0]
        self.assertEqual(rate['service_id'], 'ups_03')
        self.assertEqual(rate['amount'], '8.25')
        self.assertIn('/Shop', request.call_args.args[0])

    @patch('payment.carriers.request_json')
    def test_fedex_rate_response(self, request):
        request.side_effect = [{'access_token': 'test'}, {'output': {'rateReplyDetails': [{'serviceType': 'FEDEX_GROUND', 'serviceName': 'FedEx Ground', 'ratedShipmentDetails': [{'totalNetCharge': 9.75, 'currency': 'USD'}]}]}}]
        rate = live_rates('FEDEX', '33602', '33601', Decimal('2'))[0]
        self.assertEqual(rate['amount'], '9.75')
        self.assertEqual(rate['service_id'], 'fedex_FEDEX_GROUND')

    @patch('payment.carriers.request_json')
    def test_dhl_billing_currency(self, request):
        request.return_value = {'products': [{'productCode': 'N', 'productName': 'Express Domestic', 'totalPrice': [{'currencyType': 'BILLC', 'price': 30.5, 'priceCurrency': 'USD'}]}]}
        rate = live_rates('DHL', '33602', '33601', Decimal('2'))[0]
        self.assertEqual(rate['amount'], '30.50')
        self.assertIn('/test/rates', request.call_args.args[0])

    @patch('payment.carriers.request_json')
    def test_dhl_filters_out_partner_usps_products(self, request):
        request.return_value = {
            'products': [
                {'productCode': '2', 'productName': 'USPS Ground Advantage', 'totalPrice': [{'currencyType': 'BILLC', 'price': 6.28, 'priceCurrency': 'USD'}]},
                {'productCode': 'H', 'productName': 'Economy Select', 'totalPrice': [{'currencyType': 'BILLC', 'price': 11.10, 'priceCurrency': 'USD'}]},
                {'productCode': 'D', 'productName': 'Express Worldwide', 'totalPrice': [{'currencyType': 'BILLC', 'price': 30.95, 'priceCurrency': 'USD'}]},
            ]
        }
        rates = live_rates('DHL', '33602', '33601', Decimal('2'))
        self.assertEqual(len(rates), 2)
        self.assertEqual([r['name'] for r in rates], ['DHL Economy Select', 'DHL Express Worldwide'])
        self.assertTrue(all(r['carrier'] == 'DHL' for r in rates))
        self.assertTrue(all('USPS' not in r['name'] for r in rates))

