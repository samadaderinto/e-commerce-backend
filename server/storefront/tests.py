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
from core.services import credit_user_wallet
from notification.models import NotificationDelivery

from notification.tasks import deliver_notification_task
from payment.models import Coupon, CouponRedemption, Order
from product.models import Product
from store.models import Schedule, Store
from store.services import publish_due_products
from storefront.serializers import unit_price
from storefront.views import order_data


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
        self.buyer.is_business_admin = True
        self.buyer.save(update_fields=['is_staff', 'is_business_admin'])
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
        self.assertEqual(response.data['items'][0]['download_url'], f"/api/orders/{response.data['id']}/downloads/{self.product.pk}")

    def test_digital_checkout_succeeds_without_any_address(self):
        self.product.is_digital = True
        self.product.digital_file_url = 'https://downloads.example.com/guide.pdf'
        self.product.save(update_fields=['is_digital', 'digital_file_url'])
        self.add(1)

        rate_res = self.client.get('/api/v1/checkout/shipping-rates/')
        self.assertEqual(rate_res.status_code, 200)
        self.assertEqual(rate_res.data[0]['carrier'], 'DIGITAL')
        self.assertEqual(rate_res.data[0]['amount'], '0.00')

        response = self.client.post('/api/v1/checkout/', {
            'checkout_key': str(uuid4()),
            'shipping_quote': rate_res.data[0]['quote_token'],
            'shipping_service': 'digital_delivery',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['total'], '8500.00')
        self.assertEqual(response.data['address'], {'country': 'Worldwide', 'digital': True})
        order = Order.objects.get(pk=response.data['id'])
        self.assertIsNone(order.delivery.address)
        self.assertEqual(order.delivery.delivery_type, 'digital_delivery')

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

    def test_address_deletion_does_not_destroy_or_lose_order_address_snapshot(self):
        # 1. Buyer places an order with this address
        self.add(1)
        checkout_response = self.checkout()
        self.assertEqual(checkout_response.status_code, 201)
        order_id = checkout_response.data['id']
        order_ref = checkout_response.data['reference']
        original_address = checkout_response.data['address']
        self.assertEqual(original_address['address'], '12 Test Road')

        # 2. Buyer deletes the address months later
        delete_response = self.client.delete(f'/api/v1/addresses/?id={self.address.pk}')
        self.assertEqual(delete_response.status_code, 204)

        # 3. Address is no longer visible in active address list
        list_response = self.client.get('/api/v1/addresses/')
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 0)

        # 4. The order is NOT deleted (preventing critical data loss cascade)
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.orderId, order_ref)

        # 5. Order detail continues to return the complete snapshotted address
        order_detail = self.client.get(f'/api/v1/orders/{order_id}/')
        self.assertEqual(order_detail.status_code, 200)
        self.assertEqual(order_detail.data['address']['address'], '12 Test Road')
        self.assertEqual(order_detail.data['address']['city'], 'Tampa')
        self.assertEqual(order_detail.data['address']['state'], 'Florida')
        self.assertEqual(order_detail.data['address']['zip'], '33601')

    def test_user_account_deletion_preserves_orders_and_financial_records(self):
        # 1. Place an order as the buyer
        self.add(1)
        checkout_response = self.checkout()
        self.assertEqual(checkout_response.status_code, 201)
        order_id = checkout_response.data['id']

        # 2. Delete the buyer's user account (e.g. GDPR erasure or account closure)
        buyer_email = self.buyer.email
        self.buyer.delete()

        # 3. Order is NOT deleted - financial and audit trail is preserved
        order = Order.objects.filter(pk=order_id).first()
        self.assertIsNotNone(order)
        self.assertIsNone(order.user)
        self.assertEqual(order.buyer_email, buyer_email)
        self.assertEqual(order.address_snapshot['address'], '12 Test Road')
        self.assertEqual(len(order.items_snapshot), 1)

        # 4. Merchant and staff order retrieval continues to work seamlessly
        data = order_data(order)
        self.assertEqual(data['reference'], order.orderId)
        self.assertEqual(data['address']['address'], '12 Test Road')
        self.assertEqual(data['buyer_email'], buyer_email)

    def test_address_can_be_updated_via_patch(self):
        response = self.client.patch(
            f'/api/v1/addresses/{self.address.pk}/',
            {'address': '456 Updated Ave', 'city': 'Orlando', 'zip': '32801'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.address.refresh_from_db()
        self.assertEqual(self.address.address, '456 Updated Ave')
        self.assertEqual(self.address.city, 'Orlando')
        self.assertEqual(self.address.zip, '32801')

        response2 = self.client.patch(
            f'/api/v1/addresses/?id={self.address.pk}',
            {'address': '789 Query Ave'},
            format='json',
        )
        self.assertEqual(response2.status_code, 200)
        self.address.refresh_from_db()
        self.assertEqual(self.address.address, '789 Query Ave')


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
        self.buyer.is_business_admin = True
        self.buyer.save(update_fields=['is_staff', 'is_business_admin'])
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

    def test_physical_order_can_request_refund_within_7_days(self):
        self.add()
        order_resp = self.checkout()
        order_id = order_resp.data['id']
        refund_resp = self.client.post(f'/api/v1/orders/{order_id}/refund/', {'reason': 'wrong_item_received', 'product_ids': [self.product.pk]}, format='json')
        self.assertEqual(refund_resp.status_code, 201)
        self.assertEqual(refund_resp.data['refund_amount'], '17000.00')
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.status, 'confirmed')

    def test_order_refund_fails_after_7_days(self):
        self.add()
        order_resp = self.checkout()
        order_id = order_resp.data['id']
        Order.objects.filter(pk=order_id).update(created=timezone.now() - timedelta(days=8))
        refund_resp = self.client.post(f'/api/v1/orders/{order_id}/refund/', {'reason': 'Late return'}, format='json')
        self.assertEqual(refund_resp.status_code, 400)
        self.assertIn('expired', refund_resp.data['error']['message'])

    def test_digital_order_is_non_refundable(self):
        digital_product = Product.objects.create(
            title='Ebook Guide', description='Digital product',
            price=Decimal('100.00'), discount=0, available=100, is_digital=True,
            digital_file_url='https://example.com/ebook.pdf',
            store=self.store, brand='ProAce Digital',
        )
        self.client.post('/api/v1/cart/', {'product': digital_product.pk, 'quantity': 1}, format='json')
        order_resp = self.checkout()
        order_id = order_resp.data['id']
        refund_resp = self.client.post(f'/api/v1/orders/{order_id}/refund/', {'reason': 'Changed mind'}, format='json')
        self.assertEqual(refund_resp.status_code, 400)
        self.assertIn('non-refundable', refund_resp.data['error']['message'])

    def test_merchant_dashboard_reports_escrow_and_cleared_balances(self):
        self.add(1)
        self.checkout()
        self.client.force_authenticate(self.seller)
        resp = self.client.get(f'/api/v1/stores/{self.store.pk}/dashboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('wallet', resp.data)
        wallet = resp.data['wallet']
        self.assertEqual(wallet['platform_fee_percent'], '4.00')
        self.assertEqual(wallet['refund_window_days'], 7)
        self.assertTrue(Decimal(wallet['gross_sales']) > 0)
        self.assertTrue(Decimal(wallet['in_review']) > 0)

    def test_user_wallet_balance_and_transactions_query(self):
        resp = self.client.get('/api/v1/wallet/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['balance'], '0.00')
        self.assertEqual(resp.data['transactions'], [])

        from core.services import credit_user_wallet
        credit_user_wallet(self.buyer, Decimal('50.00'), 'Promotional Bonus', source='deposit')
        resp = self.client.get('/api/v1/wallet/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['balance'], '50.00')
        self.assertEqual(len(resp.data['transactions']), 1)
        self.assertEqual(resp.data['transactions'][0]['amount'], '50.00')

    def test_user_wallet_checkout_success_and_insufficient_balance(self):
        self.add(1)
        # Attempt wallet checkout with $0 balance -> 400
        checkout_resp = self.client.post('/api/v1/checkout/', {
            'checkout_key': str(uuid4()),
            'address': self.address.pk,
            'payment_type': 'user_wallet',
        }, format='json')
        self.assertEqual(checkout_resp.status_code, 400)
        self.assertIn('Insufficient wallet balance', checkout_resp.data['error']['message'])

        # Credit wallet with sufficient funds
        from core.services import credit_user_wallet
        credit_user_wallet(self.buyer, Decimal('20000.00'), 'Store Credit Deposit', source='deposit')
        checkout_resp = self.client.post('/api/v1/checkout/', {
            'checkout_key': str(uuid4()),
            'address': self.address.pk,
            'payment_type': 'user_wallet',
        }, format='json')
        self.assertEqual(checkout_resp.status_code, 201)
        self.assertEqual(checkout_resp.data['payment_type'], 'user_wallet')

        # Check that wallet was debited
        wallet_resp = self.client.get('/api/v1/wallet/')
        self.assertTrue(Decimal(wallet_resp.data['balance']) < Decimal('20000.00'))

    def test_refund_with_store_credit_credits_user_wallet_when_staff_approves(self):
        self.add(1)
        order_resp = self.checkout()
        order_id = order_resp.data['id']

        refund_resp = self.client.post(f'/api/v1/orders/{order_id}/refund/', {
            'reason': 'item_damaged',
            'product_ids': [self.product.pk],
            'refund_type': 'store_credit',
        }, format='json')
        self.assertEqual(refund_resp.status_code, 201)
        self.assertEqual(refund_resp.data['refund_type'], 'store_credit')
        refund_id = refund_resp.data['refund_id']

        # Staff approves refund
        staff_admin = User.objects.create(email='admin_tester@proace.com', is_staff=True, is_business_admin=True, is_active=True)
        self.client.force_authenticate(staff_admin)
        process_resp = self.client.post(f'/api/v1/admin/staff/refunds/{refund_id}/process/', {
            'action': 'approve',
            'reason': 'Damage confirmed from customer evidence.',
        }, format='json')
        self.assertEqual(process_resp.status_code, 200)

        # Buyer wallet is credited
        self.client.force_authenticate(self.buyer)
        wallet_resp = self.client.get('/api/v1/wallet/')
        self.assertTrue(Decimal(wallet_resp.data['balance']) > 0)

    def test_merchant_payout_request_validates_available_balance(self):
        self.add(1)
        self.checkout()
        self.client.force_authenticate(self.seller)

        # Immediate payout request fails because funds are in 7-day review escrow
        payout_resp = self.client.post(f'/api/v1/stores/{self.store.pk}/payouts/', {
            'amount': '20.00',
            'payout_method': 'bank_transfer',
            'account_details': {'bank_name': 'Chase', 'account_number': '123456789'},
        }, format='json')
        self.assertEqual(payout_resp.status_code, 400)
        self.assertIn('exceeds available cleared balance', payout_resp.data['error']['message'])

        # Backdate the order past the 7-day refund window
        Order.objects.filter(user=self.buyer).update(created=timezone.now() - timedelta(days=8))

        # Payout request now succeeds
        payout_resp = self.client.post(f'/api/v1/stores/{self.store.pk}/payouts/', {
            'amount': '10.00',
            'payout_method': 'bank_transfer',
            'account_details': {'bank_name': 'Chase', 'account_number': '123456789'},
        }, format='json')
        self.assertEqual(payout_resp.status_code, 201)
        self.assertEqual(payout_resp.data['status'], 'pending')
        payout_id = payout_resp.data['id']

        # Staff processes payout
        staff_admin = User.objects.create(email='staff_payout_admin@proace.com', is_staff=True, is_business_admin=True, is_active=True)
        self.client.force_authenticate(staff_admin)
        staff_payout_resp = self.client.post(f'/api/v1/admin/staff/payouts/{payout_id}/process/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(staff_payout_resp.status_code, 200)
        self.assertEqual(staff_payout_resp.data['payout']['status'], 'completed')

    def test_order_tracking_workflow(self):
        # 1. Buyer places order
        self.add(1)
        checkout_resp = self.checkout()
        self.assertEqual(checkout_resp.status_code, 201)
        order_id = checkout_resp.data['id']

        # 2. Store owner updates tracking number and ships order
        self.client.force_authenticate(self.seller)
        tracking_resp = self.client.post(f'/api/v1/stores/{self.store.pk}/orders/{order_id}/tracking/', {
            'tracking_number': '9400100000000000000001',
            'carrier': 'USPS',
            'status': 'shipped',
        }, format='json')
        self.assertEqual(tracking_resp.status_code, 200)
        self.assertEqual(tracking_resp.data['status'], 'shipped')
        self.assertEqual(tracking_resp.data['tracking_number'], '9400100000000000000001')
        self.assertIn('TrackConfirmAction', tracking_resp.data['tracking_url'])

        # 3. Buyer views order tracking
        self.client.force_authenticate(self.buyer)
        track_view_resp = self.client.get(f'/api/v1/orders/{order_id}/tracking/')
        self.assertEqual(track_view_resp.status_code, 200)
        self.assertEqual(track_view_resp.data['tracking_number'], '9400100000000000000001')
        self.assertIn('live_tracking', track_view_resp.data)

        # 4. Staff member can view tracking and order details for any order
        staff_member = User.objects.create(email='staff_tracker@proace.com', is_staff=True, is_active=True)
        self.client.force_authenticate(staff_member)
        staff_track_resp = self.client.get(f'/api/v1/orders/{order_id}/tracking/')
        self.assertEqual(staff_track_resp.status_code, 200)
        self.assertEqual(staff_track_resp.data['tracking_number'], '9400100000000000000001')

        staff_detail_resp = self.client.get(f'/api/v1/orders/{order_id}/')
        self.assertEqual(staff_detail_resp.status_code, 200)
        self.assertEqual(staff_detail_resp.data['tracking_number'], '9400100000000000000001')

        # 5. Superuser / Admin can also view tracking and order details
        super_admin = User.objects.create(email='super_admin@proace.com', is_superuser=True, is_staff=True, is_active=True)
        self.client.force_authenticate(super_admin)
        admin_track_resp = self.client.get(f'/api/v1/orders/{order_id}/tracking/')
        self.assertEqual(admin_track_resp.status_code, 200)
        self.assertEqual(admin_track_resp.data['tracking_number'], '9400100000000000000001')

    def test_verified_buyer_product_review_lifecycle(self):
        other_user = User.objects.create(email='unverified_random@proace.com', is_active=True)
        self.client.force_authenticate(other_user)

        # 1. Unverified user who hasn't bought product is rejected
        post_resp = self.client.post(f'/api/v1/products/{self.product.pk}/reviews/', {
            'rating': 5,
            'label': 'Fake review',
            'comment': 'I did not buy this item.',
        }, format='json')
        self.assertEqual(post_resp.status_code, 403)
        self.assertIn('verified buyers', post_resp.data['detail'].lower())

        # 2. Buyer purchases the product
        self.client.force_authenticate(self.buyer)
        self.add(1)
        checkout_resp = self.checkout()
        self.assertEqual(checkout_resp.status_code, 201)

        # 3. Verified buyer posts a review
        review_resp = self.client.post(f'/api/v1/products/{self.product.pk}/reviews/', {
            'rating': 4,
            'label': 'Great product',
            'comment': 'High quality material and fast delivery.',
        }, format='json')
        self.assertEqual(review_resp.status_code, 201)
        self.assertTrue(review_resp.data['is_verified_buyer'])
        self.assertTrue(review_resp.data['is_own_review'])

        # 4. Check that product average_rating updated
        self.product.refresh_from_db()
        self.assertEqual(float(self.product.average_rating), 4.0)

        # 5. Buyer edits their review (updates in place, single comment per buyer)
        update_resp = self.client.post(f'/api/v1/products/{self.product.pk}/reviews/', {
            'rating': 5,
            'label': 'Updated: Excellent product',
            'comment': 'After a week of use, it is a 5-star product.',
        }, format='json')
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.data['id'], review_resp.data['id'])
        self.assertEqual(update_resp.data['rating'], 5)

        # Average rating recalculates
        self.product.refresh_from_db()
        self.assertEqual(float(self.product.average_rating), 5.0)

        # 6. Listing reviews shows the verified buyer tag
        get_resp = self.client.get(f'/api/v1/products/{self.product.pk}/reviews/')
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(len(get_resp.data), 1)
        self.assertTrue(get_resp.data[0]['is_verified_buyer'])

    def test_review_photos_and_validation(self):
        self.client.force_authenticate(self.buyer)
        self.add(1)
        self.checkout()

        # Valid 2 photos
        review_resp = self.client.post(f'/api/v1/products/{self.product.pk}/reviews/', {
            'rating': 5,
            'label': 'With Photos',
            'comment': 'Here are pictures of the item.',
            'images': ['https://example.com/photo1.jpg', 'https://example.com/photo2.jpg'],
        }, format='json')
        self.assertEqual(review_resp.status_code, 201)
        self.assertEqual(len(review_resp.data['images']), 2)

        # Rejects more than 3 photos
        too_many_resp = self.client.post(f'/api/v1/products/{self.product.pk}/reviews/', {
            'rating': 5,
            'label': 'Too many photos',
            'comment': 'Attempting 4 photos',
            'images': [
                'https://example.com/1.jpg',
                'https://example.com/2.jpg',
                'https://example.com/3.jpg',
                'https://example.com/4.jpg',
            ],
        }, format='json')
        self.assertEqual(too_many_resp.status_code, 400)
        self.assertIn('up to 3 photos', str(too_many_resp.data))

    def test_product_variants_and_flash_sale_serialization(self):
        self.product.variants = [
            {'name': 'Size: Small', 'price_delta': '0.00', 'available': 10},
            {'name': 'Size: Large', 'price_delta': '5.00', 'available': 5},
        ]
        self.product.flash_sale_end = timezone.now() + timedelta(days=2)
        self.product.save()

        resp = self.client.get(f'/api/v1/products/{self.product.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['variants']), 2)
        self.assertEqual(resp.data['variants'][1]['name'], 'Size: Large')
        self.assertIsNotNone(resp.data['flash_sale_end'])


class UnverifiedStorePreviewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email='unverified_owner@test.com', password='Strong-password-123')
        self.stranger = User.objects.create_user(email='stranger@test.com', password='Strong-password-123')
        self.staff = User.objects.create_superuser(email='staff_admin@test.com', password='Strong-password-123')

        self.unverified_store = Store.objects.create(
            user=self.owner,
            name='Fresh Onboarding Store',
            username='fresh_store',
            status=Store.STATUS_PENDING,
            verified_at=None,
        )
        self.unverified_product = Product.objects.create(
            store=self.unverified_store,
            title='Prototype Widget',
            description='Exclusive draft widget',
            category='electronics',
            price='49.99',
            discount=0,
            available=10,
            visibility=True,
        )

        self.anon_client = APIClient()
        self.owner_client = APIClient()
        self.owner_client.force_authenticate(self.owner)
        self.stranger_client = APIClient()
        self.stranger_client.force_authenticate(self.stranger)
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(self.staff)

    def test_unverified_store_allows_owner_product_creation_with_visibility_true(self):
        resp = self.owner_client.post(
            f'/stores/{self.unverified_store.pk}/products/',
            {
                'title': 'New Sample Item',
                'description': 'Description here',
                'category': 'electronics',
                'price': '29.99',
                'available': 5,
                'visibility': True,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['visibility'])

    def test_unverified_store_public_view_is_private_to_owner_and_staff(self):
        url = f'/api/v1/stores/{self.unverified_store.pk}/public/'

        # Anonymous and other users get 404
        self.assertEqual(self.anon_client.get(url).status_code, 404)
        self.assertEqual(self.stranger_client.get(url).status_code, 404)

        # Owner gets 200 with is_preview=True and is_verified=False
        owner_resp = self.owner_client.get(url)
        self.assertEqual(owner_resp.status_code, 200)
        self.assertFalse(owner_resp.data['is_verified'])
        self.assertTrue(owner_resp.data['is_preview'])
        self.assertEqual(owner_resp.data['name'], 'Fresh Onboarding Store')

        # Staff gets 200
        staff_resp = self.staff_client.get(url)
        self.assertEqual(staff_resp.status_code, 200)

    def test_unverified_store_products_list_is_private(self):
        url = f'/api/v1/products/?store={self.unverified_store.pk}'

        # General marketplace / anonymous receives 0 results
        anon_resp = self.anon_client.get(url)
        self.assertEqual(anon_resp.status_code, 200)
        self.assertEqual(anon_resp.data['count'], 0)

        stranger_resp = self.stranger_client.get(url)
        self.assertEqual(stranger_resp.status_code, 200)
        self.assertEqual(stranger_resp.data['count'], 0)

        # Owner receives their products in preview mode
        owner_resp = self.owner_client.get(url)
        self.assertEqual(owner_resp.status_code, 200)
        self.assertEqual(owner_resp.data['count'], 1)
        self.assertEqual(owner_resp.data['results'][0]['id'], self.unverified_product.pk)
        self.assertFalse(owner_resp.data['results'][0]['store_verified'])

        # Staff receives products as well
        staff_resp = self.staff_client.get(url)
        self.assertEqual(staff_resp.status_code, 200)
        self.assertEqual(staff_resp.data['count'], 1)

    def test_unverified_store_product_detail_is_private(self):
        url = f'/api/v1/products/{self.unverified_product.pk}/'

        # Anonymous and other users get 404
        self.assertEqual(self.anon_client.get(url).status_code, 404)
        self.assertEqual(self.stranger_client.get(url).status_code, 404)

        # Owner gets 200
        owner_resp = self.owner_client.get(url)
        self.assertEqual(owner_resp.status_code, 200)
        self.assertEqual(owner_resp.data['title'], 'Prototype Widget')
        self.assertFalse(owner_resp.data['store_verified'])

        # Staff gets 200
        staff_resp = self.staff_client.get(url)
        self.assertEqual(staff_resp.status_code, 200)


class ExtendedStorefrontFeatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='buyer@test.com', password='Strong-password-123')
        self.seller = User.objects.create_user(email='seller@test.com', password='Strong-password-123')
        self.staff = User.objects.create_superuser(email='staff@test.com', password='Strong-password-123')

        self.store = Store.objects.create(
            user=self.seller, name='Prime Store', username='prime_store', status=Store.STATUS_ACTIVE, verified_at=timezone.now()
        )
        self.product = Product.objects.create(
            store=self.store, title='Smart Watch', description='Fitness tracker',
            category='electronics', price='100.00', discount=0, available=10, visibility=True
        )
        from product.models import Specification
        Specification.objects.create(
            product=self.product, serial='SW-100', attributes='Bluetooth 5.0, GPS',
            height=Decimal('1.50'), width=Decimal('1.50'), breadth=Decimal('0.50'),
            weight=Decimal('0.30'), color='Black'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_catalog_exposes_product_specifications(self):
        resp = self.client.get(f'/api/v1/products/{self.product.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('specifications', resp.data)
        specs = resp.data['specifications']
        self.assertIsNotNone(specs)
        self.assertEqual(specs['serial'], 'SW-100')
        self.assertEqual(specs['color'], 'Black')

    def test_coupon_validation_endpoint(self):
        # Create active coupon
        coupon = Coupon.objects.create(
            code='SAVE20', discount=20,
            active=True, valid_to=timezone.now() + timezone.timedelta(days=10),
            num_available=10,
        )
        # Empty cart fails
        resp = self.client.post('/api/v1/checkout/validate-coupon/', {'code': 'SAVE20'}, format='json')
        self.assertEqual(resp.status_code, 400)

        # Add item to cart
        self.client.post('/api/v1/cart/', {'product': self.product.pk, 'quantity': 1}, format='json')

        # Valid coupon succeeds
        resp = self.client.post('/api/v1/checkout/validate-coupon/', {'code': 'SAVE20'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['valid'])
        self.assertEqual(resp.data['discount_amount'], '20.00')

        # Invalid coupon fails
        resp = self.client.post('/api/v1/checkout/validate-coupon/', {'code': 'INVALID'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_self_service_order_cancellation(self):
        address = Address.objects.create(user=self.user, address='123 Main St', city='Tampa', state='FL', country='US', zip='33602')
        order = Order.objects.create(
            user=self.user, status='confirmed', ordered=True,
            total=Decimal('100.00'), subtotal=Decimal('100.00'),
            items_snapshot=[{'product': self.product.pk, 'title': 'Smart Watch', 'quantity': 2, 'unit_price': '50.00', 'is_digital': False}],
            address_snapshot={'address': '123 Main St'},
        )
        self.product.available = 8
        self.product.sales = 2
        self.product.save()

        cancel_resp = self.client.post(f'/api/v1/orders/{order.pk}/cancel/', {}, format='json')
        self.assertEqual(cancel_resp.status_code, 200)

        # Order status updated
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')

        # Inventory restocked
        self.product.refresh_from_db()
        self.assertEqual(self.product.available, 10)
        self.assertEqual(self.product.sales, 0)

        # Wallet credited
        from core.services import get_or_create_user_wallet
        wallet = get_or_create_user_wallet(self.user)
        self.assertEqual(wallet.balance, Decimal('100.00'))

    def test_review_creation_and_moderation(self):
        from core.models import Review
        # Buy product so user is verified
        order = Order.objects.create(
            user=self.user, status='delivered', ordered=True,
            total=Decimal('100.00'), subtotal=Decimal('100.00'),
            items_snapshot=[{'product': self.product.pk, 'title': 'Smart Watch', 'quantity': 1, 'unit_price': '100.00', 'is_digital': False}],
        )
        post_resp = self.client.post(
            f'/api/v1/products/{self.product.pk}/reviews/',
            {'rating': 5, 'label': 'Great watch!', 'comment': 'Works wonderfully.'},
            format='json',
        )
        self.assertEqual(post_resp.status_code, 201)
        review_id = post_resp.data['id']

        # Author can delete their review
        del_resp = self.client.delete(f'/api/v1/products/{self.product.pk}/reviews/?review_id={review_id}')
        self.assertEqual(del_resp.status_code, 204)
        self.assertFalse(Review.objects.filter(pk=review_id).exists())





