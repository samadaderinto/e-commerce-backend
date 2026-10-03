from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from cart.cache import get_cached_active_cart_data, get_cached_cart_data
from cart.models import Cart, CartItem
from core.models import Address, User
from payment.models import DeliveryInfo, Order
from product.cache import get_cached_landing_products, get_cached_product_data, get_cached_store_product_data
from product.models import Product, ProductImg
from store.models import Schedule, Store, StoreAddress, StoreInfo
from store.services import publish_due_products
from utils.cache import invalidate_revision


class MerchantTests(TestCase):
    def setUp(self):
        cache.clear()
        for helper in [get_cached_landing_products, get_cached_product_data,
                       get_cached_store_product_data, get_cached_cart_data,
                       get_cached_active_cart_data]:
            helper.cache_clear()
        self.owner = User.objects.create_user(email='owner@example.com', password='test-password')
        self.other = User.objects.create_user(email='other@example.com', password='test-password')
        verified_at = timezone.now()
        self.store = Store.objects.create(
            user=self.owner,
            name='My shop',
            status=Store.STATUS_ACTIVE,
            verified_at=verified_at,
        )
        self.other_store = Store.objects.create(
            user=self.other,
            name='Other shop',
            status=Store.STATUS_ACTIVE,
            verified_at=verified_at,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.url = f'/stores/{self.store.pk}/'
        self.products_url = self.url + 'products/'
        self.product = self.make_product(self.store)
        self.foreign_product = self.make_product(self.other_store, title='Foreign product')

    def make_product(self, store, **kwargs):
        data = dict(store=store, title='Speaker', description='Portable speaker',
                    price='100.00', discount=10, available=4, category='electronics')
        data.update(kwargs)
        return Product.objects.create(**data)

    def product_payload(self, **kwargs):
        data = dict(title='Headphones', description='Wireless headphones',
                    price='125.50', category='electronics', tags=['audio'])
        data.update(kwargs)
        return data

    def make_order(self, status='confirmed', ordered=True, mixed=False, quantity=2, product=None):
        target_product = product or self.product
        cart = Cart.objects.create(user=self.other, ordered=ordered)
        CartItem.objects.create(cart=cart, product=target_product, quantity=quantity)
        if mixed:
            CartItem.objects.create(cart=cart, product=self.foreign_product, quantity=9)
        address = Address.objects.create(user=self.other, address='1 Test Road',
                                         zip='100001', country='Nigeria', state='Lagos', city='Ikeja')
        delivery = DeliveryInfo.objects.create(user=self.other, address=address,
                                               method='home delivery', delivery_type='standard')
        return Order.objects.create(user=self.other, cart=cart, delivery=delivery,
                                    status=status, ordered=ordered)

    def test_anonymous_is_denied(self):
        self.client.force_authenticate(None)
        for url in ['/stores/', self.url, self.products_url, self.url + 'dashboard/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.post('/stores/', {'name': 'Anonymous'}).status_code, 401)

    def test_store_onboarding_uses_authenticated_owner(self):
        response = self.client.post('/stores/', {
            'name': 'New shop', 'user': self.other.pk,
            'profile': {'email': 'merchant@example.com', 'bio': 'Electronics'},
            'address': {'address': '1 Main Road', 'country': 'Nigeria', 'state': 'Lagos', 'city': 'Ikeja'},
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        store = Store.objects.get(pk=response.data['id'])
        self.assertEqual(store.user, self.owner)
        self.assertTrue(store.username)
        self.assertTrue(StoreInfo.objects.filter(store=store, email='merchant@example.com').exists())
        self.assertTrue(StoreAddress.objects.filter(store=store, is_default=True).exists())

    def test_invalid_onboarding_is_atomic(self):
        count = Store.objects.count()
        response = self.client.post('/stores/', {'name': 'Invalid', 'address': {'city': 'Lagos'}}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Store.objects.count(), count)

    def test_stores_are_private_and_owner_cannot_be_changed(self):
        data = self.client.get('/stores/').data
        self.assertEqual([row['id'] for row in data['results']], [self.store.pk])
        self.assertEqual(self.client.get(f'/stores/{self.other_store.pk}/').status_code, 404)
        self.assertEqual(self.client.patch(self.url, {'user': self.other.pk}, format='json').status_code, 200)
        self.store.refresh_from_db()
        self.assertEqual(self.store.user, self.owner)

    def test_profile_and_pickup_address_are_updated(self):
        for bio in ['First', 'Updated']:
            self.assertEqual(self.client.patch(self.url + 'profile/', {'bio': bio, 'email': 'shop@example.com'}, format='json').status_code, 200)
        self.assertEqual(StoreInfo.objects.filter(store=self.store).count(), 1)
        self.assertEqual(self.client.get(self.url + 'profile/').data['bio'], 'Updated')
        address = {'address': '2 Main Road', 'country': 'Nigeria', 'state': 'Lagos', 'city': 'Ikeja'}
        for _ in range(2):
            self.assertEqual(self.client.put(self.url + 'pickup-address/', address, format='json').status_code, 200)
        self.assertEqual(StoreAddress.objects.filter(store=self.store, is_default=True).count(), 1)
        self.assertTrue(self.client.get(self.url + 'onboarding/').data['complete'])

    def test_create_product_defaults_to_draft_and_protects_fields(self):
        response = self.client.post(self.products_url, self.product_payload(
            store=self.other_store.pk, sales=999, sponsored=True, average_rating='5.00'), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        product = Product.objects.get(pk=response.data['id'])
        self.assertEqual(product.store, self.store)
        self.assertFalse(product.visibility)
        self.assertEqual(product.sales, 0)
        self.assertFalse(product.sponsored)
        self.assertEqual(list(product.tags.names()), ['audio'])

    def test_invalid_products_rejected(self):
        for invalid in [{'price': '-1'}, {'price': '0'}, {'discount': 61},
                        {'available': -1}, {'category': 'invalid'}, {'title': ''}]:
            with self.subTest(invalid=invalid):
                response = self.client.post(self.products_url, self.product_payload(**invalid), format='json')
                self.assertEqual(response.status_code, 400, response.data)

    def test_cross_store_access_is_denied(self):
        foreign_url = f'/stores/{self.other_store.pk}/'
        for suffix in ['', 'dashboard/', 'orders/', 'profile/', 'pickup-address/', 'onboarding/', 'products/']:
            with self.subTest(suffix=suffix):
                self.assertEqual(self.client.get(foreign_url + suffix).status_code, 404)
        self.assertEqual(self.client.post(foreign_url + 'products/', self.product_payload(), format='json').status_code, 404)
        hidden = self.products_url + f'{self.foreign_product.pk}/'
        self.assertEqual(self.client.patch(hidden, {'price': '1'}, format='json').status_code, 404)
        self.assertEqual(self.client.patch(hidden + 'inventory/', {'available': 1}, format='json').status_code, 404)
        self.assertEqual(self.client.get(hidden + 'images/').status_code, 404)
        self.assertEqual(self.client.get(hidden + 'specifications/').status_code, 404)

    def test_product_list_filters_and_pagination(self):
        self.make_product(self.store, title='Draft phone', visibility=False, category='phones', available=0)
        response = self.client.get(self.products_url, {'search': 'Draft', 'visibility': 'false', 'stock': 'out', 'limit': 1})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Draft phone')
        self.assertEqual(self.client.get(self.products_url, {'visibility': 'bad'}).status_code, 400)
        self.assertEqual(self.client.get(self.products_url, {'stock': 'bad'}).status_code, 400)

    def test_inventory_update_invalidates_cached_cart(self):
        cart = Cart.objects.create(user=self.other)
        CartItem.objects.create(cart=cart, product=self.product)
        self.assertEqual(get_cached_active_cart_data(self.other.pk)['cart_items'][0]['product']['available'], 4)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(self.products_url + f'{self.product.pk}/inventory/', {'available': 12}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(get_cached_active_cart_data(self.other.pk)['cart_items'][0]['product']['available'], 12)
        self.assertEqual(self.client.patch(self.products_url + f'{self.product.pk}/inventory/', {'available': -1}, format='json').status_code, 400)

    def test_unpublish_invalidates_catalog_and_preserves_history(self):
        self.assertEqual(len(get_cached_landing_products()['newest_products']), 2)
        get_cached_product_data(self.product.pk)
        order = self.make_order()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(self.products_url + f'{self.product.pk}/', {'visibility': False}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(get_cached_landing_products()['newest_products']), 1)
        with self.assertRaises(Product.DoesNotExist):
            get_cached_product_data(self.product.pk)
        self.assertEqual(self.client.delete(self.products_url + f'{self.product.pk}/').status_code, 400)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())

    def test_images_upload_and_delete_are_scoped(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            buffer = BytesIO()
            Image.new('RGB', (8, 8), 'red').save(buffer, format='PNG')
            upload = SimpleUploadedFile('photo.png', buffer.getvalue(), content_type='image/png')
            url = self.products_url + f'{self.product.pk}/images/'
            response = self.client.post(url, {'image': upload}, format='multipart')
            self.assertEqual(response.status_code, 201, response.data)
            image_id = response.data['id']
            foreign_image = ProductImg.objects.create(product=self.foreign_product)
            self.assertEqual(self.client.delete(url + f'{foreign_image.pk}/').status_code, 404)
            self.assertEqual(self.client.delete(url + f'{image_id}/').status_code, 204)
            bad = SimpleUploadedFile('fake.png', b'not an image', content_type='image/png')
            self.assertEqual(self.client.post(url, {'image': bad}, format='multipart').status_code, 400)

    def test_specifications_can_be_created_and_updated(self):
        url = self.products_url + f'{self.product.pk}/specifications/'
        payload = {'serial': 'SKU-01', 'attributes': 'Bluetooth', 'height': '1.00',
                   'width': '2.00', 'breadth': '3.00', 'weight': '0.50', 'color': 'Black'}
        self.assertEqual(self.client.put(url, payload, format='json').status_code, 200)
        payload['color'] = 'White'
        self.assertEqual(self.client.put(url, payload, format='json').status_code, 200)
        self.assertEqual(self.client.get(url).data['color'], 'White')

    def test_dashboard_counts_only_merchant_items_and_eligible_orders(self):
        self.make_order(mixed=True)
        self.make_order(status='pending', ordered=False, quantity=7)
        self.make_order(status='cancelled', quantity=5)
        old = self.make_order(quantity=10)
        Order.objects.filter(pk=old.pk).update(created=timezone.now() - timedelta(days=45))
        response = self.client.get(self.url + 'dashboard/', {'days': 7})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['inventory']['total'], 1)
        self.assertEqual(response.data['orders']['total'], 3)
        self.assertEqual(response.data['sales']['units'], 2)
        self.assertEqual(response.data['sales']['estimated_item_value'], '180.00')
        self.assertEqual(len(response.data['orders_by_day']), 7)
        self.assertEqual(sum(day['count'] for day in response.data['orders_by_day']), 3)
        self.assertEqual(response.data['top_products'][0]['product_id'], self.product.pk)

    def test_empty_dashboard_and_invalid_parameters(self):
        empty = Store.objects.create(user=self.owner, name='Empty')
        response = self.client.get(f'/stores/{empty.pk}/dashboard/')
        self.assertEqual(response.data['sales']['estimated_item_value'], '0.00')
        self.assertEqual(response.data['inventory']['units'], 0)
        for days in ['abc', 0, 366]:
            self.assertEqual(self.client.get(self.url + 'dashboard/', {'days': days}).status_code, 400)

    def test_order_list_does_not_expose_other_sellers_items_or_cart_total(self):
        self.make_order(mixed=True)
        response = self.client.get(self.url + 'orders/')
        self.assertEqual(response.data['count'], 1)
        row = response.data['results'][0]
        self.assertEqual(len(row['items']), 1)
        self.assertEqual(row['items'][0]['product'], self.product.pk)
        self.assertNotIn('total', row)
        self.assertNotIn('user', row)
        self.assertEqual(self.client.get(self.url + 'orders/', {'status': 'invalid'}).status_code, 400)

    def test_schedule_ownership_and_validation(self):
        future = (timezone.now() + timedelta(days=1)).isoformat()
        response = self.client.post('/stores/schedules/', {'product': self.product.pk, 'store': self.other_store.pk, 'make_visible_at': future}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Schedule.objects.get(pk=response.data['id']).store, self.store)
        self.assertEqual(self.client.post('/stores/schedules/', {'product': self.foreign_product.pk, 'make_visible_at': future}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/stores/schedules/', {'product': self.product.pk, 'make_visible_at': timezone.now().isoformat()}, format='json').status_code, 400)

    def test_due_schedules_publish_once_and_leave_future_products_hidden(self):
        self.product.visibility = False
        self.product.save()
        future_product = self.make_product(self.store, visibility=False)
        Schedule.objects.create(store=self.store, product=self.product, make_visible_at=timezone.now() - timedelta(minutes=1))
        Schedule.objects.create(store=self.store, product=future_product, make_visible_at=timezone.now() + timedelta(days=1))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(publish_due_products(), 1)
        self.assertEqual(publish_due_products(), 0)
        self.product.refresh_from_db()
        future_product.refresh_from_db()
        self.assertTrue(self.product.visibility)
        self.assertFalse(future_product.visibility)
        self.assertEqual(Schedule.objects.count(), 1)

    def test_shared_cache_revision_refreshes_local_lru(self):
        self.assertEqual(get_cached_product_data(self.product.pk)['title'], 'Speaker')
        Product.objects.filter(pk=self.product.pk).update(title='Changed by another worker')
        invalidate_revision('products')
        self.assertEqual(get_cached_product_data(self.product.pk)['title'], 'Changed by another worker')
        data = get_cached_product_data(self.product.pk)
        data['title'] = 'Caller mutation'
        self.assertEqual(get_cached_product_data(self.product.pk)['title'], 'Changed by another worker')

    def test_order_references_are_generated_for_each_order(self):
        first = self.make_order()
        second = self.make_order()
        self.assertNotEqual(first.orderId, second.orderId)
        self.assertEqual(len(first.orderId), 13)

    def test_jwt_authentication(self):
        from rest_framework_simplejwt.tokens import AccessToken

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.owner)}')
        response = client.get(self.products_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
        self.assertEqual(client.get(self.products_url).status_code, 401)

    def test_merchant_can_onboard_digital_products_and_ebooks(self):
        # Digital product without download URL fails validation
        payload = {
            'title': 'Mastering Python E-Book',
            'description': 'A comprehensive digital guide to Python mastery.',
            'category': 'books',
            'price': '29.99',
            'available': 100,
            'is_digital': True,
        }
        response = self.client.post(self.products_url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('digital_file_url', str(response.data))

        # Digital product with valid download URL succeeds
        payload['digital_file_url'] = 'https://downloads.proace.test/ebooks/python-guide.pdf'
        response = self.client.post(self.products_url, payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data['is_digital'])
        self.assertEqual(response.data['digital_file_url'], 'https://downloads.proace.test/ebooks/python-guide.pdf')
        self.assertEqual(response.data['category'], 'books')
        product_id = response.data['id']

        # Product is stored as digital in DB
        product = Product.objects.get(pk=product_id)
        self.assertTrue(product.is_digital)
        self.assertEqual(product.digital_file_url, 'https://downloads.proace.test/ebooks/python-guide.pdf')

    def test_admin_created_store_is_auto_verified_and_official(self):
        admin_user = User.objects.create_superuser(
            email='admin.store@example.com',
            password='Admin-password-123!',
        )
        admin_client = APIClient()
        admin_client.force_authenticate(admin_user)

        response = admin_client.post('/stores/create/', {'name': 'Proace Official Store'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        store = Store.objects.get(pk=response.data['id'])
        self.assertTrue(store.is_official)
        self.assertEqual(store.status, Store.STATUS_ACTIVE)
        self.assertIsNotNone(store.verified_at)

    def test_official_store_enjoys_zero_platform_fee_in_dashboard_and_payouts(self):
        admin_user = User.objects.create_superuser(
            email='company.admin@example.com',
            password='Admin-password-123!',
        )
        admin_store = Store.objects.create(
            user=admin_user,
            name='Company Flagship Store',
            is_official=True,
            status=Store.STATUS_ACTIVE,
            verified_at=timezone.now(),
        )
        product = self.make_product(admin_store, price='100.00', discount=0)
        order = self.make_order(product=product, quantity=2, status='delivered')

        admin_client = APIClient()
        admin_client.force_authenticate(admin_user)

        resp = admin_client.get(f'/stores/{admin_store.pk}/dashboard/?days=7')
        self.assertEqual(resp.status_code, 200)
        wallet = resp.data['wallet']
        self.assertEqual(wallet['platform_fee_percent'], '0.00')
        self.assertEqual(wallet['platform_fee_deducted'], '0.00')
        self.assertEqual(wallet['gross_sales'], '200.00')
        self.assertEqual(wallet['net_sales'], '200.00')
        self.assertEqual(wallet['in_review'], '200.00')

    def test_multi_store_unified_merchant_wallet_and_ledger(self):
        # The owner creates a second store
        second_store = Store.objects.create(
            user=self.owner,
            name='My Second Shop',
            status=Store.STATUS_ACTIVE,
            verified_at=timezone.now(),
        )
        second_product = self.make_product(second_store, title='Gaming Mouse', price='50.00', discount=0)

        # Generate orders across Store 1 and Store 2
        from store.services import record_order_earnings_for_merchant, settle_pending_merchant_earnings
        order1 = self.make_order(product=self.product, quantity=2, status='confirmed')  # $180 gross
        order2 = self.make_order(product=second_product, quantity=4, status='confirmed')  # $200 gross
        record_order_earnings_for_merchant(order1)
        record_order_earnings_for_merchant(order2)

        # Check unified merchant wallet endpoint
        wallet_resp = self.client.get('/stores/wallet/')
        self.assertEqual(wallet_resp.status_code, 200)
        data = wallet_resp.data
        self.assertEqual(data['stores_count'], 2)
        # Total gross = 180 + 200 = 380; platform fee (4%) = 7.20 + 8.00 = 15.20; net = 364.80
        self.assertEqual(data['total_gross_sales'], '380.00')
        self.assertEqual(data['total_platform_fees'], '15.20')
        self.assertEqual(data['total_net_sales'], '364.80')
        self.assertEqual(data['pending_balance'], '364.80')
        self.assertEqual(data['available_balance'], '0.00')

        # Check ledger entries across stores
        ledger_resp = self.client.get('/stores/wallet/ledger/')
        self.assertEqual(ledger_resp.status_code, 200)
        self.assertEqual(ledger_resp.data['count'], 2)

        # Filter ledger by store
        store1_ledger = self.client.get(f'/stores/wallet/ledger/?store_id={self.store.pk}')
        self.assertEqual(store1_ledger.data['count'], 1)
        self.assertEqual(store1_ledger.data['results'][0]['store_name'], 'My shop')

        store2_ledger = self.client.get(f'/stores/wallet/ledger/?store_id={second_store.pk}')
        self.assertEqual(store2_ledger.data['count'], 1)
        self.assertEqual(store2_ledger.data['results'][0]['store_name'], 'My Second Shop')

        # Backdate both orders past the 7-day refund window and trigger settlement
        Order.objects.filter(pk__in=[order1.pk, order2.pk]).update(created=timezone.now() - timedelta(days=8))
        from store.models import StoreEarningsLedger
        StoreEarningsLedger.objects.filter(order__in=[order1, order2]).update(available_at=timezone.now() - timedelta(days=1))

        settled_count = settle_pending_merchant_earnings()
        self.assertEqual(settled_count, 2)

        # Funds are now available for unified withdrawal
        wallet_resp_after = self.client.get('/stores/wallet/')
        self.assertEqual(wallet_resp_after.data['pending_balance'], '0.00')
        self.assertEqual(wallet_resp_after.data['available_balance'], '364.80')

        # Request a unified payout withdrawing combined earnings from both stores
        payout_resp = self.client.post('/stores/wallet/payouts/', {
            'amount': '300.00',
            'payout_method': 'bank_transfer',
            'account_details': {'bank_name': 'Chase', 'account_number': '987654321'},
            'notes': 'Consolidated multi-store withdrawal',
        }, format='json')
        self.assertEqual(payout_resp.status_code, 201)
        self.assertEqual(payout_resp.data['status'], 'pending')
        self.assertEqual(payout_resp.data['amount'], '300.00')

        # Staff approves the payout
        staff_admin = User.objects.create_superuser(email='staff.admin@proace.test', password='Admin-password-123')
        staff_client = APIClient()
        staff_client.force_authenticate(staff_admin)

        payout_id = payout_resp.data['id']
        staff_resp = staff_client.post(f'/api/v1/admin/staff/payouts/{payout_id}/process/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(staff_resp.status_code, 200)
        self.assertEqual(staff_resp.data['payout']['status'], 'completed')

        # Verify wallet total_withdrawn updated
        final_wallet = self.client.get('/stores/wallet/').data
        self.assertEqual(final_wallet['total_withdrawn'], '300.00')
        self.assertEqual(final_wallet['available_balance'], '64.80')



