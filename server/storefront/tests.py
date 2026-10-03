from decimal import Decimal
from datetime import timedelta
import json
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core import mail, signing
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from cart.models import CartItem
from core.models import Address, User
from notification.models import NotificationDelivery
from notification.tasks import deliver_notification_task
from payment.models import Coupon, CouponRedemption, Order
from product.models import Product
from store.models import Schedule, Store
from store.services import publish_due_products
from storefront.serializers import unit_price


class UnitPriceTests(SimpleTestCase):
    def test_discounted_price_is_rounded_half_up_to_cents(self):
        product = SimpleNamespace(price=Decimal('10.05'), discount=10)

        self.assertEqual(unit_price(product), Decimal('9.05'))

    def test_undiscounted_price_is_returned_to_cents(self):
        product = SimpleNamespace(price=Decimal('12.30'), discount=0)

        self.assertEqual(unit_price(product), Decimal('12.30'))


class OpenApiDocumentationTests(SimpleTestCase):
    def test_openapi_schema_documents_storefront_and_authentication(self):
        response = self.client.get(
            '/api/schema/',
            HTTP_ACCEPT='application/vnd.oai.openapi+json',
        )

        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)
        self.assertEqual(schema['openapi'], '3.0.3')
        self.assertIn('/api/v1/products/', schema['paths'])
        self.assertIn('/api/v1/products/{id}/', schema['paths'])
        self.assertIn('/api/v1/cart/', schema['paths'])
        self.assertIn('/api/v1/checkout/', schema['paths'])
        self.assertIn('/api/v1/notifications/', schema['paths'])
        self.assertIn('/api/v1/admin/stores/', schema['paths'])
        self.assertIn('jwtAuth', schema['components']['securitySchemes'])
        self.assertNotIn('security', schema['paths']['/api/v1/products/']['get'])
        self.assertEqual(
            schema['paths']['/api/v1/cart/']['get']['security'],
            [{'jwtAuth': []}],
        )
        for path, operation, parameter in [
            ('/api/v1/addresses/', 'delete', 'id'),
            ('/api/v1/cart/', 'delete', 'product'),
            ('/api/v1/wishlist/', 'delete', 'product'),
        ]:
            with self.subTest(path=path):
                operation_schema = schema['paths'][path][operation]
                self.assertIn(
                    parameter,
                    [item['name'] for item in operation_schema['parameters']],
                )
                self.assertNotIn('requestBody', operation_schema)
        self.assertIn(
            'CatalogPage',
            schema['paths']['/api/v1/products/']['get']['responses']['200']
            ['content']['application/json']['schema']['$ref'],
        )

    def test_swagger_and_redoc_pages_are_available(self):
        for path in ['/api/docs/', '/api/redoc/']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn('text/html', response['Content-Type'])


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class StorefrontTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(email='buyer@test.com', password='Strong-test-password-123', first_name='Alex')
        self.seller = User.objects.create_user(email='seller@test.com', password='Strong-test-password-123')
        self.store = Store.objects.create(user=self.seller, name='Test store', status=Store.STATUS_ACTIVE, verified_at=timezone.now())
        self.product = Product.objects.create(store=self.store, title='A speaker', description='Portable', category='electronics', price='10000.00', discount=15, available=5)
        self.address = Address.objects.create(user=self.buyer, address='12 Test Road', city='Tampa', state='Florida', country='United States', zip='33601')
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)

    def add(self, quantity=2):
        return self.client.post('/api/v1/cart/', {'product': self.product.pk, 'quantity': quantity}, format='json')

    def checkout(self, **kwargs):
        data = {'address': self.address.pk, 'checkout_key': str(uuid4())}
        data.update(kwargs)
        return self.client.post('/api/v1/checkout/', data, format='json')

    def test_public_catalog_excludes_drafts_and_blocked_stores(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/v1/products/').data['count'], 1)
        self.product.visibility = False
        self.product.save()
        self.assertEqual(self.client.get(f'/api/v1/products/{self.product.pk}/').status_code, 404)
        self.product.visibility = True
        self.product.save()
        self.store.status = Store.STATUS_BLOCKED
        self.store.save()
        self.assertEqual(self.client.get('/api/v1/products/').data['count'], 0)

    def test_store_must_be_staff_approved_before_it_can_be_public(self):
        pending_store = Store.objects.create(user=self.seller, name='Awaiting review')
        pending_product = Product.objects.create(
            store=pending_store, title='Pending product', price='500.00', discount=0, available=2
        )
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/v1/products/').data['count'], 1)
        self.assertEqual(self.client.get(f'/api/v1/products/{pending_product.pk}/').status_code, 404)

        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.get('/api/v1/admin/stores/').status_code, 403)
        self.buyer.is_staff = True
        self.buyer.save(update_fields=['is_staff'])
        self.assertEqual(self.client.get('/api/v1/admin/stores/').data['results'][0]['id'], pending_store.pk)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/v1/admin/stores/{pending_store.pk}/approve/')
        self.assertEqual(response.status_code, 200, response.data)
        pending_store.refresh_from_db()
        self.assertEqual(pending_store.status, Store.STATUS_ACTIVE)
        self.assertIsNotNone(pending_store.verified_at)
        self.assertEqual(pending_store.verified_by, self.buyer)

        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/v1/products/').data['count'], 2)

    def test_scheduled_products_remain_queued_until_store_is_approved(self):
        pending_store = Store.objects.create(user=self.seller, name='Scheduled store')
        product = Product.objects.create(
            store=pending_store, title='Scheduled product', price='500.00',
            discount=0, available=2, visibility=False,
        )
        schedule = Schedule.objects.create(
            store=pending_store, product=product, make_visible_at=timezone.now() - timedelta(minutes=1)
        )

        self.assertEqual(publish_due_products(), 0)
        product.refresh_from_db()
        self.assertFalse(product.visibility)
        self.assertTrue(Schedule.objects.filter(pk=schedule.pk).exists())

    def test_cart_uses_session_owner_and_discounted_prices(self):
        response = self.client.post('/api/v1/cart/', {'product': self.product.pk, 'quantity': 2, 'user': self.seller.pk}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['subtotal'], '17000.00')
        self.assertEqual(CartItem.objects.get().cart.user, self.buyer)
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.get('/api/v1/cart/').data['items'], [])

    def test_cart_validates_stock_and_fractional_quantities(self):
        self.assertEqual(self.add(6).status_code, 400)
        self.assertEqual(self.add(1.5).status_code, 400)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_physical_checkout_rejects_non_us_delivery_address(self):
        self.address.country = 'Nigeria'
        self.address.save(update_fields=['country'])
        self.add(1)

        response = self.checkout()

        self.assertEqual(response.status_code, 400)
        self.assertIn('only within the United States', str(response.data))
        self.assertEqual(Order.objects.count(), 0)

    def test_digital_checkout_is_worldwide_free_and_exposes_download_in_order(self):
        self.address.country = 'Nigeria'
        self.address.save(update_fields=['country'])
        self.product.is_digital = True
        self.product.digital_file_url = 'https://downloads.example.com/book.pdf'
        self.product.save(update_fields=['is_digital', 'digital_file_url'])
        self.add(1)

        response = self.checkout()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['total'], '8500.00')
        self.assertTrue(response.data['items'][0]['is_digital'])
        self.assertEqual(
            response.data['items'][0]['download_url'],
            'https://downloads.example.com/book.pdf',
        )

    def test_cannot_add_products_from_any_owned_store_even_with_spoofed_user(self):
        for name in ['First store', 'Second store']:
            store = Store.objects.create(user=self.buyer, name=name, status=Store.STATUS_ACTIVE, verified_at=timezone.now())
            product = Product.objects.create(store=store, title=name, price=100, discount=0, available=5)
            response = self.client.post('/api/v1/cart/', {'product': product.pk, 'user': self.seller.pk}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('any store you own', str(response.data))
        self.assertFalse(CartItem.objects.exists())
        self.assertEqual(self.add(1).status_code, 200)

    def test_existing_own_item_is_unpurchasable_but_can_be_removed(self):
        self.add(1)
        self.store.user = self.buyer
        self.store.save()
        response = self.client.get('/api/v1/cart/')
        self.assertFalse(response.data['items'][0]['purchasable'])
        self.assertTrue(response.data['items'][0]['product']['is_own_store'])
        response = self.client.patch('/api/v1/cart/', {'product': self.product.pk, 'quantity': 2}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CartItem.objects.get().quantity, 1)
        self.assertEqual(self.client.delete(f'/api/v1/cart/?product={self.product.pk}').status_code, 200)
        self.assertFalse(CartItem.objects.exists())

    def test_mixed_cart_self_purchase_rolls_back_entire_checkout(self):
        self.add(1)
        cart = CartItem.objects.get().cart
        store = Store.objects.create(user=self.buyer, name='Own store', status=Store.STATUS_ACTIVE, verified_at=timezone.now())
        product = Product.objects.create(store=store, title='Own product', price=100, discount=0, available=5)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        response = self.checkout(user=self.seller.pk)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('any store you own', str(response.data))
        for item in [self.product, product]:
            item.refresh_from_db()
            self.assertEqual(item.available, 5)
            self.assertEqual(item.sales, 0)
        cart.refresh_from_db()
        self.assertFalse(cart.ordered)
        self.assertEqual(cart.cart_items.count(), 2)
        self.assertFalse(Order.objects.exists())

    def test_catalog_ownership_is_specific_to_authenticated_account(self):
        url = f'/api/v1/products/{self.product.pk}/'
        self.assertFalse(self.client.get(url).data['is_own_store'])
        self.client.force_authenticate(self.seller)
        self.assertTrue(self.client.get(url).data['is_own_store'])
        self.client.force_authenticate(None)
        self.assertFalse(self.client.get(url).data['is_own_store'])

    def test_cart_and_address_delete_accept_documented_query_parameters(self):
        self.add(1)
        removed_item = self.client.delete(f'/api/v1/cart/?product={self.product.pk}')
        removed_address = self.client.delete(f'/api/v1/addresses/?id={self.address.pk}')

        self.assertEqual(removed_item.status_code, 200)
        self.assertEqual(removed_item.data['items'], [])
        self.assertEqual(removed_address.status_code, 204)
        self.assertFalse(Address.objects.filter(pk=self.address.pk).exists())

    def test_checkout_creates_real_order_and_is_idempotent(self):
        self.add()
        key = str(uuid4())
        with self.captureOnCommitCallbacks(execute=True):
            response = self.checkout(checkout_key=key)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['total'], '17006.65')
        self.product.refresh_from_db()
        self.assertEqual(self.product.available, 3)
        again = self.checkout(checkout_key=key)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.data['id'], response.data['id'])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(self.client.get('/api/v1/cart/').data['items'], [])

    def test_shipping_rates_endpoint_returns_usps_options(self):
        self.add(2)
        response = self.client.get(f'/api/v1/checkout/shipping-rates/?address={self.address.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.data) >= 3)
        service_ids = [r['service_id'] for r in response.data]
        self.assertIn('usps_ground_advantage', service_ids)
        self.assertIn('usps_priority_mail', service_ids)
        self.assertIn('usps_priority_express', service_ids)

    def test_order_snapshot_survives_price_changes(self):
        self.add()
        response = self.checkout()
        self.product.price = Decimal('20000')
        self.product.title = 'Changed title'
        self.product.save()
        response = self.client.get(f"/api/v1/orders/{response.data['id']}/")
        self.assertEqual(response.data['items'][0]['title'], 'A speaker')
        self.assertEqual(response.data['items'][0]['unit_price'], '8500.00')

    def test_checkout_rejects_foreign_address_and_orders_are_private(self):
        self.add()
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.checkout().status_code, 404)
        self.client.force_authenticate(self.buyer)
        order = self.checkout()
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.get(f"/api/v1/orders/{order.data['id']}/").status_code, 404)

    def test_checkout_rolls_back_stock_on_invalid_coupon(self):
        self.add()
        self.assertEqual(self.checkout(coupon='NOTVALID').status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.available, 5)
        self.assertEqual(Order.objects.count(), 0)

    def test_coupon_types_and_one_redemption_per_user(self):
        coupon = Coupon.objects.create(code='TOTAL10', valid_to=timezone.now() + timedelta(days=1), discount=10, num_available=10, type=Coupon.ORDER_TOTAL)
        self.add(2)
        response = self.checkout(coupon='total10')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['total'], '15306.65')
        self.assertEqual(CouponRedemption.objects.filter(coupon=coupon, user=self.buyer).count(), 1)
        self.product.refresh_from_db()
        self.product.available = 3
        self.product.save()
        self.add(1)
        response = self.checkout(coupon='TOTAL10')
        self.assertEqual(response.status_code, 400)
        self.assertIn('already used', str(response.data))

    def test_product_quantity_coupon_applies_only_to_qualifying_product(self):
        coupon = Coupon.objects.create(code='BUY2', valid_to=timezone.now() + timedelta(days=1), discount=20, num_available=10, type=Coupon.PRODUCT_QUANTITY, product=self.product, minimum_quantity=2)
        self.add(2)
        response = self.checkout(coupon='BUY2')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['total'], '13606.65')

    def test_admin_can_create_targeted_coupon_but_customer_cannot(self):
        self.client.force_authenticate(self.buyer)
        payload = {'code': 'ADMIN10', 'valid_to': (timezone.now() + timedelta(days=1)).isoformat(), 'discount': 10, 'num_available': 5, 'type': 'category', 'category': 'electronics', 'minimum_quantity': 1}
        self.assertEqual(self.client.post('/api/v1/admin/coupons/', payload, format='json').status_code, 403)
        self.buyer.is_staff = True
        self.buyer.save(update_fields=['is_staff'])
        response = self.client.post('/api/v1/admin/coupons/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_checkout_revalidates_stock(self):
        self.add()
        self.product.available = 1
        self.product.save()
        self.assertEqual(self.checkout().status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_unconfigured_card_payment_never_creates_an_order(self):
        self.add()
        self.assertEqual(self.checkout(payment_type='card').status_code, 400)
        self.assertFalse(Order.objects.exists())

    @override_settings(STRIPE_SECRET='sk_test', STRIPE_WALLET_PAYMENT_METHODS='paypal,cashapp')
    @patch('storefront.views.stripe.checkout.Session.create')
    def test_wallet_checkout_excludes_paypal_from_configured_methods(self, create_session):
        create_session.return_value = SimpleNamespace(id='cs_test', url='https://checkout.test')
        self.add()

        response = self.client.post(
            '/api/v1/checkout/wallet-session/',
            {'address': self.address.pk, 'checkout_key': str(uuid4())},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['payment_methods'], ['cashapp'])
        self.assertEqual(create_session.call_args.kwargs['payment_method_types'], ['cashapp'])

    def test_registration_requires_verification_and_hashes_password(self):
        self.client.force_authenticate(None)
        response = self.client.post('/api/v1/auth/register/', {'email': 'new@test.com', 'first_name': 'New', 'last_name': 'Customer', 'phone1': '+2348012345678', 'password': 'Strong-new-password-123', 'is_staff': True, 'is_superuser': True}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email='new@test.com')
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('Strong-new-password-123'))
        delivery = NotificationDelivery.objects.get(
            channel=NotificationDelivery.CHANNEL_EMAIL,
            recipient_email=user.email,
        )
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_PENDING)
        self.assertEqual(len(mail.outbox), 0)
        result = deliver_notification_task.run(delivery.pk)
        self.assertEqual(result['status'], NotificationDelivery.STATUS_SENT)
        self.assertEqual(len(mail.outbox), 1)
        token = signing.dumps({'user': user.pk}, salt='proace-verify')
        response = self.client.post('/api/v1/auth/verify/', {'token': token}, format='json')
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_saved_items_are_persistent_and_scoped(self):
        self.assertEqual(self.client.post('/api/v1/wishlist/', {'product': self.product.pk}).status_code, 200)
        self.assertEqual(len(self.client.get('/api/v1/wishlist/').data), 1)
        self.assertEqual(
            self.client.delete(f'/api/v1/wishlist/?product={self.product.pk}').status_code,
            204,
        )
        self.assertEqual(self.client.get('/api/v1/wishlist/').data, [])
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.get('/api/v1/wishlist/').data, [])

    def test_anonymous_cannot_checkout_or_read_private_data(self):
        self.client.force_authenticate(None)
        for path in ['me', 'cart', 'orders', 'addresses', 'wishlist', 'stores']:
            self.assertEqual(self.client.get(f'/api/v1/{path}/').status_code, 401)

    def test_catalog_rejects_invalid_filters(self):
        for params in [{'page': 'no'}, {'min_price': '-10'}, {'store': 'abc'}]:
            self.assertEqual(self.client.get('/api/v1/products/', params).status_code, 400)
