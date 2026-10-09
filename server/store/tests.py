from datetime import timedelta
from decimal import Decimal
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
from product.models import Product, ProductImg, Specification
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
        StoreAddress.objects.create(store=self.store, address='1 Main St', city='Tampa', state='FL', country='US', zip='33602', is_default=True)
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

    def make_order(self, status: str = 'confirmed', ordered: bool = True, mixed: bool = False, quantity: int = 2, product: Product | None = None) -> Order:
        target_product = product or self.product
        cart = Cart.objects.create(user=self.other, ordered=ordered)
        CartItem.objects.create(cart=cart, product=target_product, quantity=quantity)
        if mixed:
            CartItem.objects.create(cart=cart, product=self.foreign_product, quantity=9)
        address = Address.objects.create(user=self.other, address='1 Test Road',
                                         zip='100001', country='Nigeria', state='Lagos', city='Ikeja')
        delivery = DeliveryInfo.objects.create(user=self.other, address=address,
                                               method='home delivery', delivery_type='standard')
        from storefront.serializers import unit_price
        total = sum((unit_price(item.product) * item.quantity for item in cart.cart_items.select_related('product')), Decimal('0'))
        return Order.objects.create(user=self.other, cart=cart, delivery=delivery,
                                    status=status, ordered=ordered,
                                    total=total,
                                    subtotal=total,
                                    paid_total=total)

    def test_address_required_for_store_creation_and_all_publication(self) -> None:
        response = self.client.post('/stores/', {'name': 'Missing address'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('address', response.data['error']['details'])
        StoreAddress.objects.filter(store=self.store).delete()
        for digital in (False, True):
            response = self.client.post(self.products_url, self.product_payload(
                visibility=True, is_digital=digital,
                digital_file_url='https://example.com/file.pdf' if digital else '',
            ), format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('visibility', response.data['error']['details'])
        response = self.client.post(self.products_url, self.product_payload(visibility=False), format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_incomplete_address_and_scheduled_publication_are_rejected(self) -> None:
        response = self.client.put(self.url + 'pickup-address/', {
            'address': '1 Main St', 'city': 'Tampa', 'state': 'FL', 'country': 'US', 'zip': ' ',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        StoreAddress.objects.filter(store=self.store).delete()
        self.product.visibility = False
        self.product.save()
        Schedule.objects.create(store=self.store, product=self.product, make_visible_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(publish_due_products(), 0)
        self.product.refresh_from_db()
        self.assertFalse(self.product.visibility)

    def test_dashboard_groups_orders_in_requested_local_timezone(self) -> None:
        from datetime import datetime, timezone as utc_timezone
        from unittest.mock import patch
        order = self.make_order()
        instant = datetime(2026, 10, 8, 2, tzinfo=utc_timezone.utc)
        Order.objects.filter(pk=order.pk).update(created=instant)
        with patch('django.utils.timezone.now', return_value=instant):
            response = self.client.get(self.url + 'dashboard/?days=1&time_zone=America/Los_Angeles')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(str(response.data['orders_by_day'][0]['date']), '2026-10-07')
        self.assertEqual(response.data['orders_by_day'][0]['count'], 1)

    def test_refund_debt_survives_financial_recalculation_and_repeat_reversal(self) -> None:
        from store.services import record_order_earnings_for_merchant, process_refund_deduction, calculate_merchant_financials
        from store.models import StoreEarningsLedger, StorePayout
        order = self.make_order(quantity=1)
        entry = record_order_earnings_for_merchant(order)[0]
        entry.status = StoreEarningsLedger.STATUS_AVAILABLE
        entry.available_at = timezone.now() - timedelta(days=1)
        entry.save()
        StorePayout.objects.create(wallet=entry.wallet, store=self.store, amount=entry.net_amount, status=StorePayout.STATUS_COMPLETED, reference='debt-test')
        entry.wallet.available_balance = 0
        entry.wallet.pending_balance = 0
        entry.wallet.save()
        process_refund_deduction(order)
        process_refund_deduction(order)
        entry.wallet.refresh_from_db()
        self.assertEqual(entry.wallet.available_balance, -entry.net_amount)
        result = calculate_merchant_financials(self.owner)
        self.assertEqual(Decimal(result['available_balance']), -entry.net_amount)
        self.assertEqual(StoreEarningsLedger.objects.filter(order=order, entry_type=StoreEarningsLedger.TYPE_REFUND).count(), 1)

    def test_partial_refunds_require_store_attribution_and_do_not_over_reverse(self) -> None:
        from store.services import record_order_earnings_for_merchant, process_refund_deduction
        from store.models import StoreEarningsLedger
        from rest_framework.exceptions import ValidationError
        order = self.make_order(quantity=1, mixed=True)
        entries = record_order_earnings_for_merchant(order)
        own = next(entry for entry in entries if entry.store_id == self.store.pk)
        with self.assertRaises(ValidationError):
            process_refund_deduction(order, Decimal('10'))
        process_refund_deduction(order, Decimal('10'), store=self.store)
        process_refund_deduction(order, store=self.store)
        from django.db.models import Sum
        total = StoreEarningsLedger.objects.filter(order=order, store=self.store, entry_type=StoreEarningsLedger.TYPE_REFUND).aggregate(total=Sum('gross_amount'))['total']
        self.assertEqual(total, -own.gross_amount)
        self.assertFalse(StoreEarningsLedger.objects.filter(order=order, store=self.other_store, entry_type=StoreEarningsLedger.TYPE_REFUND).exists())

    def test_digital_product_accepts_zero_weight_and_updates_without_weight(self) -> None:
        response = self.client.post(self.products_url, self.product_payload(
            is_digital=True, weight='0.00', digital_file_url='https://example.com/book.pdf',
            length=None, width=None, height=None,
        ), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        product = Product.objects.get(pk=response.data['id'])
        self.assertEqual(str(product.weight), '0.00')
        response = self.client.patch(self.products_url + f'{product.pk}/', {'title': 'Updated download'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['weight'], '0.00')

    def test_physical_product_rejects_zero_weight(self) -> None:
        response = self.client.post(self.products_url, self.product_payload(weight='0.00'), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('weight', str(response.data))

    def test_anonymous_is_denied(self):
        self.client.force_authenticate(None)
        for url in ['/stores/', self.url, self.products_url, self.url + 'dashboard/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.post('/stores/', {'name': 'Anonymous'}).status_code, 401)

    @override_settings(ROOT_URLCONF='store.test_urls')
    def test_usps_tracking_update_saves_and_notifies_customer(self):
        from notification.models import Notification
        order = self.make_order()
        response = self.client.post(self.url + f'orders/{order.pk}/tracking/', {
            'carrier': 'USPS', 'tracking_number': '9400100000000000000000', 'status': 'shipped',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        self.assertEqual(order.status, 'shipped')
        self.assertEqual(order.tracking_number, '9400100000000000000000')
        self.assertIsNotNone(order.shipped_at)
        self.assertEqual(len(order.tracking_events), 1)
        self.assertTrue(Notification.objects.filter(
            recipient=self.other, data__event='order_tracking_update', data__order_id=order.pk,
        ).exists())

        # Also verify update works using the order reference string (e.g. ORD002399809)
        ref_response = self.client.post(self.url + f'orders/{order.orderId}/tracking/', {
            'carrier': 'USPS', 'tracking_number': '9400200000000000000000', 'status': 'delivered',
        }, format='json')
        self.assertEqual(ref_response.status_code, 200, ref_response.data)
        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')
        self.assertEqual(order.tracking_number, '9400200000000000000000')

    @override_settings(ROOT_URLCONF='store.test_urls')
    def test_tracking_update_rejects_unsupported_carriers_and_foreign_orders(self):
        order = self.make_order()
        response = self.client.post(self.url + f'orders/{order.pk}/tracking/', {
            'carrier': 'Unsupported', 'tracking_number': '12345', 'status': 'shipped',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, 'confirmed')
        foreign_order = self.make_order(product=self.foreign_product)
        response = self.client.post(self.url + f'orders/{foreign_order.pk}/tracking/', {
            'carrier': 'USPS', 'tracking_number': '12345', 'status': 'shipped',
        }, format='json')
        self.assertEqual(response.status_code, 404)

    def test_store_onboarding_uses_authenticated_owner(self):
        response = self.client.post('/stores/', {
            'name': 'New shop', 'user': self.other.pk,
            'profile': {'email': 'merchant@example.com', 'bio': 'Electronics'},
            'address': {'address': '1 Main Road', 'country': 'Nigeria', 'state': 'Lagos', 'city': 'Ikeja', 'zip': '100001'},
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
        address = {'address': '2 Main Road', 'country': 'Nigeria', 'state': 'Lagos', 'city': 'Ikeja', 'zip': '100001'}
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

    def test_digital_product_rejects_physical_specifications_endpoint(self) -> None:
        digital_product = Product.objects.create(
            store=self.store,
            title='Digital Audio Guide',
            description='Downloadable MP3 audio',
            category='books',
            price=Decimal('15.00'),
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='https://example.com/audio.mp3',
        )
        url = self.products_url + f'{digital_product.pk}/specifications/'
        payload = {
            'serial': 'AUD-01',
            'attributes': 'Audio format',
            'height': '1.00',
            'width': '2.00',
            'breadth': '3.00',
            'weight': '0.50',
            'color': 'Black',
        }
        response = self.client.put(url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('physical specifications', str(response.data))

    def test_digital_product_onboarding_rejects_weight_and_physical_dimensions(self) -> None:
        payload = self.product_payload(
            is_digital=True,
            digital_file_url='https://example.com/guide.pdf',
            weight='2.50',
            height='5.00',
            width='4.00',
            length='8.00',
        )
        response = self.client.post(self.products_url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        details = response.data['error']['details']
        self.assertIn('weight', details)
        self.assertIn('height', details)
        self.assertIn('width', details)
        self.assertIn('length', details)

    def test_converting_physical_product_to_digital_clears_dimensions_and_specifications(self) -> None:
        spec_url = self.products_url + f'{self.product.pk}/specifications/'
        spec_payload = {
            'serial': 'SPK-99',
            'attributes': 'Hi-Fi build',
            'height': '5.00',
            'width': '5.00',
            'breadth': '5.00',
            'weight': '2.00',
            'color': 'Silver',
        }
        self.assertEqual(self.client.put(spec_url, spec_payload, format='json').status_code, 200)
        self.assertTrue(Specification.objects.filter(product=self.product).exists())

        response = self.client.patch(
            self.products_url + f'{self.product.pk}/',
            {
                'is_digital': True,
                'digital_file_url': 'https://example.com/speaker-manual.pdf',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_digital)
        self.assertEqual(self.product.weight, Decimal('0.00'))
        self.assertIsNone(self.product.length)
        self.assertIsNone(self.product.width)
        self.assertIsNone(self.product.height)
        self.assertFalse(Specification.objects.filter(product=self.product).exists())

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
        self.other.phone1 = '+12025550123'
        self.other.save()
        self.make_order(mixed=True)
        response = self.client.get(self.url + 'orders/', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.content)
        self.assertEqual(response.data['count'], 1)
        row = response.data['results'][0]
        self.assertEqual(len(row['items']), 1)
        self.assertEqual(row['items'][0]['product'], self.product.pk)
        self.assertNotIn('total', row)
        self.assertNotIn('user', row)
        self.assertEqual(row['customer']['phone'], '+12025550123')
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

    def test_merchant_can_upload_digital_asset_file_to_storage(self):
        product = Product.objects.create(
            store=self.store,
            title='Sample Digital Guide',
            description='E-book download',
            category='books',
            price='19.99',
            discount=0,
            available=50,
            is_digital=True,
            digital_file_url='https://example.com/old.pdf',
        )
        fake_pdf = SimpleUploadedFile(
            'guidebook.pdf',
            b'%PDF-1.4 Fake PDF Content for Unit Test',
            content_type='application/pdf',
        )
        url = f'{self.products_url}{product.id}/digital-file/'
        response = self.client.post(url, {'file': fake_pdf}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('guidebook.pdf', response.data['file_name'])
        self.assertTrue(response.data['digital_file_url'])

        product.refresh_from_db()
        self.assertTrue(product.is_digital)
        self.assertIn('guidebook.pdf', product.digital_file_url)
        self.assertFalse(product.digital_preview_watermark)

    def test_digital_preview_watermark_only_allowed_for_images(self):
        product = Product.objects.create(
            store=self.store,
            title='E-Book & Software Package',
            description='Comprehensive programming guide in PDF format',
            category='books',
            price='29.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='https://downloads.proace.local/files/guide.pdf',
            digital_preview_watermark=True,
        )
        url = f'{self.products_url}{product.id}/'

        # PDF digital product should coerce watermark to False
        response = self.client.patch(url, {
            'digital_file_url': 'https://downloads.proace.local/files/guide.pdf',
            'digital_preview_watermark': True,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertFalse(product.digital_preview_watermark)

        # Image digital product should allow watermark to be True
        response = self.client.patch(url, {
            'digital_file_url': 'https://downloads.proace.local/files/digital-artwork.png',
            'digital_preview_watermark': True,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertTrue(product.digital_preview_watermark)

    def test_merchant_upload_image_sets_cover_image(self):
        product = Product.objects.create(
            store=self.store,
            title='Sample Canvas Art',
            description='Handmade oil on canvas',
            category='outwear',
            price='45.00',
            discount=0,
            available=10,
        )
        image_bytes = BytesIO()
        Image.new('RGB', (100, 100), color='blue').save(image_bytes, format='PNG')
        fake_img = SimpleUploadedFile('cover.png', image_bytes.getvalue(), content_type='image/png')

        url = f'{self.products_url}{product.id}/images/'
        response = self.client.post(url, {'image': fake_img, 'is_cover': 'true'}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)

        product.refresh_from_db()
        self.assertTrue(product.image_url)
        self.assertIn('cover', product.image_url)

        response = self.client.patch(
            f'{self.products_url}{product.id}/',
            {'image_url': product.image_url, 'title': 'Updated Canvas Art'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertEqual(product.title, 'Updated Canvas Art')

        response = self.client.patch(
            f'{self.products_url}{product.id}/',
            {'image_url': 'not-a-url'}, format='json',
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('image_url', response.data['error']['details'])

    def test_customer_can_create_tenth_store_but_not_eleventh(self):
        for index in range(8):
            Store.objects.create(user=self.owner, name=f'Shop {index}')
        response = self.client.post('/stores/create/', {'name': 'Tenth shop', 'address': {'address': '1 Main St', 'city': 'Tampa', 'state': 'FL', 'country': 'US', 'zip': '33602'}}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        for endpoint in ['/stores/create/', '/stores/']:
            response = self.client.post(endpoint, {'name': 'Eleventh shop', 'address': {'address': '1 Main St', 'city': 'Tampa', 'state': 'FL', 'country': 'US', 'zip': '33602'}}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('10 stores', str(response.data))
        self.assertEqual(Store.objects.filter(user=self.owner).count(), 10)
        self.client.force_authenticate(self.other)
        response = self.client.post('/stores/create/', {'name': 'Other owner shop', 'address': {'address': '1 Main St', 'city': 'Tampa', 'state': 'FL', 'country': 'US', 'zip': '33602'}}, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_admin_created_store_is_auto_verified_and_official(self):
        admin_user = User.objects.create_superuser(
            email='admin.store@example.com',
            password='Admin-password-123!',
        )
        admin_client = APIClient()
        admin_client.force_authenticate(admin_user)

        response = admin_client.post('/stores/create/', {'name': 'Proace Official Store', 'address': {'address': '1 Main St', 'city': 'Tampa', 'state': 'FL', 'country': 'US', 'zip': '33602'}}, format='json')
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

    def test_strict_separation_backoffice_vs_internal_store_access(self):
        admin = User.objects.create_superuser(email='admin.access@proace.test', password='Admin-password-123')
        staff = User.objects.create_staffuser(email='staff.access@proace.test', password='Staff-password-123')
        seller = User.objects.create_user(email='thirdparty.seller@example.com', password='Seller-password-123')

        third_party_store = Store.objects.create(user=seller, name='Independent Store', username='indep-store', is_official=False)
        official_store = Store.objects.create(user=admin, name='Official Proace Store', username='proace-store', is_official=True)

        # 1. Staff and Admin cannot access third-party store in the seller interface
        for backoffice_user in [staff, admin]:
            client = APIClient()
            client.force_authenticate(backoffice_user)

            # Store list in seller interface only returns official store
            listing = client.get('/stores/')
            store_ids = [s['id'] for s in listing.data['results']]
            self.assertIn(official_store.pk, store_ids)
            self.assertNotIn(third_party_store.pk, store_ids)

            # Accessing third-party store detail/dashboard returns 404
            self.assertEqual(client.get(f'/stores/{third_party_store.pk}/').status_code, 404)
            self.assertEqual(client.get(f'/stores/{third_party_store.pk}/dashboard/').status_code, 404)

            # Accessing official store detail/dashboard is allowed
            self.assertEqual(client.get(f'/stores/{official_store.pk}/').status_code, 200)

        # 2. Third-party seller cannot access official store
        seller_client = APIClient()
        seller_client.force_authenticate(seller)
        seller_listing = seller_client.get('/stores/')
        seller_store_ids = [s['id'] for s in seller_listing.data['results']]
        self.assertIn(third_party_store.pk, seller_store_ids)
        self.assertNotIn(official_store.pk, seller_store_ids)
        self.assertEqual(seller_client.get(f'/stores/{official_store.pk}/').status_code, 404)

        # 3. Staff assignment is deprecated
        admin_client = APIClient()
        admin_client.force_authenticate(admin)
        assign_resp = admin_client.put(f'/stores/{official_store.pk}/staff/', {'staff_ids': [staff.pk]}, format='json')
        self.assertEqual(assign_resp.status_code, 200)
        self.assertIn('deprecated', assign_resp.data['detail'])

    def test_official_store_payout_requests_are_rejected(self):
        admin = User.objects.create_superuser(
            email='official.owner@example.com',
            password='Admin-password-123!',
        )
        official_store = Store.objects.create(
            user=admin,
            name='ProAce Direct',
            is_official=True,
            status=Store.STATUS_ACTIVE,
            verified_at=timezone.now(),
        )
        admin_client = APIClient()
        admin_client.force_authenticate(admin)

        # 1. Direct store payouts endpoint
        resp = admin_client.post(f'/stores/{official_store.pk}/payouts/', {
            'amount': '50.00',
            'payout_method': 'bank_transfer',
            'account_details': {'bank_name': 'Chase', 'account_number': '123456789'},
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Platform Treasury', resp.data['error']['message'])

        # 2. Unified merchant wallet payouts endpoint
        wallet_resp = admin_client.post('/stores/wallet/payouts/', {
            'store_id': official_store.pk,
            'amount': '50.00',
            'payout_method': 'bank_transfer',
            'account_details': {'bank_name': 'Chase', 'account_number': '123456789'},
        }, format='json')
        self.assertEqual(wallet_resp.status_code, 400)
        self.assertIn('Platform Treasury', wallet_resp.data['error']['message'])


