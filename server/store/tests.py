from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from cart.cache import get_cached_active_cart_data, get_cached_cart_data
from cart.models import Cart, CartItem
from core.models import Address, User
from payment.models import DeliveryInfo, Order
from product.cache import get_cached_landing_products, get_cached_product_data, get_cached_store_product_data
from product.models import Product, ProductImg, Specification
from store.models import (
    MerchantWallet,
    Schedule,
    Store,
    StoreAddress,
    StoreEarningsLedger,
    StoreInfo,
    StorePayout,
)
from store.services import publish_due_products, request_merchant_payout
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
    def test_repeated_tracking_save_does_not_repeat_notices_or_emails(self) -> None:
        from notification.models import Notification, NotificationDelivery
        order = self.make_order()
        payload = {"carrier": "USPS", "tracking_number": "9400100000000000000000", "status": "shipped"}
        url = self.url + f"orders/{order.pk}/tracking/"
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 200)
        notices = Notification.objects.count()
        deliveries = NotificationDelivery.objects.count()
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 200)
        self.assertEqual(Notification.objects.count(), notices)
        self.assertEqual(NotificationDelivery.objects.count(), deliveries)

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
        self.assertTrue(MerchantWallet.objects.filter(user=self.owner).exists())

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

    def test_digital_categories_accept_creation_and_catalog_filtering(self) -> None:
        categories: list[str] = ["software", "courses", "templates", "design_assets", "photo_video", "music_audio", "business", "digital_tools"]
        for category in categories:
            with self.subTest(category=category):
                response = self.client.post(
                    self.products_url,
                    self.product_payload(
                        category=category, is_digital=True,
                        digital_file_url="https://example.com/test-download.zip",
                    ),
                    format="json",
                )
                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(response.data["category"], category)
                listing = self.client.get(self.products_url, {"category": category})
                self.assertEqual(listing.status_code, 200, listing.data)
                self.assertEqual(listing.data["count"], 1)
                self.assertEqual(listing.data["results"][0]["id"], response.data["id"])

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

    def test_order_list_search_and_filters(self):
        order1 = self.make_order(status='confirmed')
        order2 = self.make_order(status='picked up')
        order2.orderId = 'ORD-PICKUP-99'
        order2.buyer_email = 'pickup_buyer@example.com'
        order2.save()

        # Search by orderId
        res = self.client.get(self.url + 'orders/', {'search': 'PICKUP'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'], 1)
        self.assertEqual(res.data['results'][0]['reference'], 'ORD-PICKUP-99')

        # Notification deep links can request one store-scoped order directly.
        res = self.client.get(self.url + 'orders/', {'order_id': order1.pk})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'], 1)
        self.assertEqual(res.data['results'][0]['id'], order1.pk)

        foreign_order = self.make_order(product=self.foreign_product)
        res = self.client.get(self.url + 'orders/', {'order_id': foreign_order.pk})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'], 0)
        self.assertEqual(self.client.get(self.url + 'orders/', {'order_id': 'invalid'}).status_code, 400)

        # Search by buyer_email
        res = self.client.get(self.url + 'orders/', {'search': 'pickup_buyer'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'], 1)

        # Filter by status 'picked up'
        res = self.client.get(self.url + 'orders/', {'status': 'picked up'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'], 1)
        self.assertEqual(res.data['results'][0]['status'], 'picked up')

        # Filter by days
        res = self.client.get(self.url + 'orders/', {'days': '30'})
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(res.data['count'], 2)

        # Ordering
        res = self.client.get(self.url + 'orders/', {'ordering': 'created'})
        self.assertEqual(res.status_code, 200)

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

    def test_merchant_upload_digital_image_auto_sets_cover_and_watermark(self):
        product = Product.objects.create(
            store=self.store,
            title='Digital Landscape Artwork',
            description='Original digital illustration',
            category='books',
            price='35.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='',
        )
        image_bytes = BytesIO()
        Image.new('RGB', (100, 100), color='purple').save(image_bytes, format='PNG')
        fake_img = SimpleUploadedFile('artwork.png', image_bytes.getvalue(), content_type='image/png')
        url = f'{self.products_url}{product.id}/digital-file/'
        response = self.client.post(url, {'file': fake_img}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['image_url'])
        self.assertTrue(response.data['digital_preview_watermark'])

        product.refresh_from_db()
        self.assertTrue(product.digital_preview_watermark)
        self.assertTrue(product.image_url)
        self.assertIn('artwork.png', product.digital_file_url)

    def test_digital_image_gallery_upload_stores_only_a_watermarked_preview(self):
        product = Product.objects.create(
            store=self.store,
            title='Protected Artwork Gallery',
            description='Original digital illustration',
            category='design_assets',
            price='35.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/artwork.png',
            digital_preview_watermark=True,
        )
        image_bytes = BytesIO()
        Image.new('RGB', (100, 100), color='purple').save(image_bytes, format='PNG')
        gallery_image = SimpleUploadedFile(
            'gallery-original.png',
            image_bytes.getvalue(),
            content_type='image/png',
        )

        response = self.client.post(
            f'{self.products_url}{product.id}/images/',
            {'image': gallery_image, 'is_cover': 'true'},
            format='multipart',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn('digital-previews', response.data['image'])
        product.refresh_from_db()
        self.assertIn('digital-previews', product.image_url)
        stored_image = ProductImg.objects.get(product=product)
        self.assertIn('digital-previews', stored_image.image.name)
        self.assertNotIn('gallery-original.png', stored_image.image.name)

    def test_merchant_can_upload_a_watermarked_digital_variant_preview(self):
        product = Product.objects.create(
            store=self.store,
            title='Digital Variant Artwork',
            description='Original digital illustration',
            category='design_assets',
            price='35.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/artwork.png',
            digital_preview_watermark=True,
        )
        image_bytes = BytesIO()
        Image.new('RGB', (100, 100), color='orange').save(image_bytes, format='PNG')
        image = SimpleUploadedFile('variant.png', image_bytes.getvalue(), content_type='image/png')

        response = self.client.post(
            f'{self.products_url}{product.id}/variant-image/',
            {'image': image},
            format='multipart',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn('digital-previews', response.data['image_url'])

    def test_image_variant_asset_returns_a_watermarked_carousel_image(self):
        product = Product.objects.create(
            store=self.store,
            title='Digital Artwork Editions',
            description='Original digital illustration',
            category='design_assets',
            price='35.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/artwork.png',
            digital_preview_watermark=True,
            variants=[{'name': 'Phone', 'price_delta': '0.00'}],
        )
        image_bytes = BytesIO()
        Image.new('RGB', (100, 100), color='orange').save(image_bytes, format='PNG')
        image = SimpleUploadedFile('phone-wallpaper.png', image_bytes.getvalue(), content_type='image/png')

        asset_response = self.client.post(
            f'{self.products_url}{product.id}/variant-file/',
            {'file': image, 'asset_type': 'image'},
            format='multipart',
        )

        self.assertEqual(asset_response.status_code, 201, asset_response.data)
        self.assertIn('digital-previews', asset_response.data['image_url'])
        self.assertNotIn('digital_products', asset_response.data['image_url'])
        response = self.client.patch(
            f'{self.products_url}{product.id}/',
            {'variants': [{
                'name': 'Phone',
                'price_delta': '0.00',
                'digital_file_type': 'image',
                'digital_file_url': asset_response.data['digital_file_url'],
                'image_url': asset_response.data['image_url'],
            }]},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['variants'][0]['image_url'], asset_response.data['image_url'])

    def test_merchant_can_upload_an_unwatermarked_variant_image_for_other_digital_files(self):
        product = Product.objects.create(
            store=self.store,
            title='Digital Audio Variant',
            description='Original audio download',
            category='music_audio',
            price='12.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/audio.mp3',
            digital_preview_watermark=False,
        )
        image_bytes = BytesIO()
        Image.new('RGB', (100, 100), color='blue').save(image_bytes, format='PNG')
        image = SimpleUploadedFile('album-art.png', image_bytes.getvalue(), content_type='image/png')

        response = self.client.post(
            f'{self.products_url}{product.id}/variant-image/',
            {'image': image},
            format='multipart',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn('digital-previews', response.data['image_url'])
        self.assertTrue(ProductImg.objects.filter(product=product).exists())

    def test_audio_variant_upload_is_not_watermarked_when_an_old_flag_remains(self):
        product = Product.objects.create(
            store=self.store,
            title='Edited Audio Product',
            description='Audio download that replaced an artwork download',
            category='music_audio',
            price='12.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/audio.mp3',
            digital_preview_watermark=True,
        )
        image_bytes = BytesIO()
        Image.new('RGB', (100, 100), color='green').save(image_bytes, format='PNG')
        image = SimpleUploadedFile('audio-cover.png', image_bytes.getvalue(), content_type='image/png')

        response = self.client.post(
            f'{self.products_url}{product.id}/variant-image/',
            {'image': image},
            format='multipart',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn('digital-previews', response.data['image_url'])

    def test_replacing_an_image_download_with_audio_clears_protected_variant_images(self):
        product = Product.objects.create(
            store=self.store,
            title='Artwork Turned Audio Download',
            description='An audio release that replaced a previous artwork download',
            category='music_audio',
            price='12.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/previous-artwork.png',
            digital_preview_watermark=True,
            variants=[{
                'name': 'Album edition',
                'price_delta': '0.00',
                'image_url': 'http://testserver/media/images/digital-previews/1/1/old_preview.jpg',
            }],
        )
        audio = SimpleUploadedFile('new-release.mp3', b'fake audio content', content_type='audio/mpeg')

        response = self.client.post(
            f'{self.products_url}{product.id}/digital-file/',
            {'file': audio},
            format='multipart',
        )

        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertFalse(product.digital_preview_watermark)
        self.assertEqual(product.variants[0]['image_url'], '')

    def test_merchant_can_upload_an_audio_file_for_a_digital_variant(self):
        product = Product.objects.create(
            store=self.store,
            title='Audio Editions',
            description='Audio download with multiple editions',
            category='music_audio',
            price='12.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/album.mp3',
        )
        audio = SimpleUploadedFile('extended.mp3', b'extended audio', content_type='audio/mpeg')

        response = self.client.post(
            f'{self.products_url}{product.id}/variant-file/',
            {'file': audio, 'asset_type': 'audio'},
            format='multipart',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn('/variants/', response.data['digital_file_url'])
        self.assertNotIn('image_url', response.data)

    def test_variant_download_must_belong_to_the_current_product(self) -> None:
        product = Product.objects.create(
            store=self.store,
            title='Scoped variant files',
            description='A private digital download',
            category='books',
            price='12.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/book.pdf',
        )
        other_product = Product.objects.create(
            store=self.store,
            title='Another private download',
            description='Must stay private',
            category='books',
            price='12.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/other.pdf',
        )
        url = f'{self.products_url}{product.pk}/'

        response = self.client.patch(url, {
            'variants': [{
                'name': 'Premium',
                'digital_file_type': 'document',
                'digital_file_url': f'digital_products/{other_product.store_id}/{other_product.pk}/variants/private.pdf',
            }],
        }, format='json')

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('variants', response.data['error']['details'])

    def test_variant_download_accepts_current_product_upload_path(self) -> None:
        product = Product.objects.create(
            store=self.store,
            title='Own variant file',
            description='A private digital download',
            category='books',
            price='12.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/book.pdf',
        )
        response = self.client.patch(f'{self.products_url}{product.pk}/', {
            'variants': [{
                'name': 'Premium',
                'digital_file_type': 'document',
                'digital_file_url': f'digital_products/{product.store_id}/{product.pk}/variants/premium.pdf',
            }],
        }, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('/variants/premium.pdf', response.data['variants'][0]['digital_file_url'])

    def test_failed_variant_original_storage_removes_generated_preview(self) -> None:
        product = Product.objects.create(
            store=self.store,
            title='Preview rollback',
            description='A digital image with protected preview',
            category='design_assets',
            price='12.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/original.png',
            digital_preview_watermark=True,
        )
        image_bytes = BytesIO()
        Image.new('RGB', (100, 100), color='purple').save(image_bytes, format='PNG')
        image = SimpleUploadedFile('variant.png', image_bytes.getvalue(), content_type='image/png')

        with (
            patch('utils.digital_previews.create_digital_preview', return_value='images/digital-previews/1/1/preview.jpg'),
            patch('django.core.files.storage.default_storage.save', side_effect=OSError('storage unavailable')),
            patch('django.core.files.storage.default_storage.delete') as delete,
        ):
            response = self.client.post(
                f'{self.products_url}{product.pk}/variant-file/',
                {'file': image, 'asset_type': 'image'},
                format='multipart',
            )

        self.assertEqual(response.status_code, 400, response.data)
        delete.assert_called_once_with('images/digital-previews/1/1/preview.jpg')

    def test_variant_file_must_match_its_declared_media_type(self):
        product = Product.objects.create(
            store=self.store,
            title='Audio-only Editions',
            description='Audio download with multiple editions',
            category='music_audio',
            price='12.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/album.mp3',
        )
        image_bytes = BytesIO()
        Image.new('RGB', (100, 100), color='red').save(image_bytes, format='PNG')
        image = SimpleUploadedFile('cover.png', image_bytes.getvalue(), content_type='image/png')

        response = self.client.post(
            f'{self.products_url}{product.id}/variant-file/',
            {'file': image, 'asset_type': 'audio'},
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('audio file', str(response.data))

    def test_audio_product_can_have_a_video_variant_when_declared_as_video(self):
        product = Product.objects.create(
            store=self.store,
            title='Concert Editions',
            description='Audio album with a concert-film edition',
            category='music_audio',
            price='12.00',
            discount=0,
            available=0,
            is_digital=True,
            digital_file_url='digital_products/1/1/album.mp3',
        )
        video = SimpleUploadedFile('concert.mp4', b'video content', content_type='video/mp4')

        response = self.client.post(
            f'{self.products_url}{product.id}/variant-file/',
            {'file': video, 'asset_type': 'video'},
            format='multipart',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn('/variants/', response.data['digital_file_url'])

    def test_digital_product_with_variants_preserves_options_and_validates_prices(self):
        payload = {
            'title': '4K Wallpaper Pack',
            'description': 'High-resolution digital desktop backgrounds',
            'category': 'books',
            'price': '10.00',
            'discount': 0,
            'is_digital': True,
            'digital_file_url': 'https://downloads.proace.local/art/wallpaper.png',
            'variants': [
                {'name': '4K Ultra HD', 'price_delta': '5.00'},
                {'name': 'Standard 1080p', 'price_delta': '0.00'},
            ],
        }
        response = self.client.post(self.products_url, payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data['variants']), 2)
        self.assertEqual(response.data['variants'][0]['name'], '4K Ultra HD')

        product = Product.objects.get(pk=response.data['id'])
        self.assertTrue(product.is_digital)
        self.assertEqual(len(product.variants), 2)

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
        payout_ledger = StoreEarningsLedger.objects.filter(
            reference=payout_resp.data['reference'],
            entry_type=StoreEarningsLedger.TYPE_PAYOUT,
        )
        self.assertEqual(payout_ledger.count(), 2)
        self.assertEqual(
            sum((-entry.net_amount for entry in payout_ledger), Decimal('0.00')),
            Decimal('300.00'),
        )
        store_balances = {
            summary['store_id']: summary['available_balance']
            for summary in final_wallet['stores']
        }
        self.assertEqual(store_balances[self.store.pk], '0.00')
        self.assertEqual(store_balances[second_store.pk], '64.80')

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
        official_wallet = MerchantWallet.objects.create(user=admin)
        StoreEarningsLedger.objects.create(
            wallet=official_wallet,
            store=official_store,
            entry_type=StoreEarningsLedger.TYPE_SALE,
            gross_amount=Decimal('100.00'),
            fee_amount=Decimal('0.00'),
            net_amount=Decimal('100.00'),
            status=StoreEarningsLedger.STATUS_AVAILABLE,
            available_at=timezone.now() - timedelta(days=1),
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

        # An unscoped combined request also cannot withdraw official-store proceeds.
        unscoped = admin_client.post('/stores/wallet/payouts/', {
            'amount': '50.00',
            'payout_method': 'bank_transfer',
            'account_details': {'bank_name': 'Chase', 'account_number': '123456789'},
        }, format='json')
        self.assertEqual(unscoped.status_code, 400)
        self.assertIn('merchant-store funds', unscoped.data['error']['message'])

    def test_store_scoped_payout_cannot_spend_another_stores_balance(self):
        second_store = Store.objects.create(
            user=self.owner,
            name='Second merchant store',
            status=Store.STATUS_ACTIVE,
            verified_at=timezone.now(),
        )
        wallet = MerchantWallet.objects.create(
            user=self.owner,
            available_balance=Decimal('200.00'),
        )
        available_at = timezone.now() - timedelta(days=1)
        for store in (self.store, second_store):
            StoreEarningsLedger.objects.create(
                wallet=wallet,
                store=store,
                entry_type=StoreEarningsLedger.TYPE_SALE,
                gross_amount=Decimal('100.00'),
                fee_amount=Decimal('0.00'),
                net_amount=Decimal('100.00'),
                status=StoreEarningsLedger.STATUS_AVAILABLE,
                available_at=available_at,
            )

        with self.assertRaises(ValidationError):
            request_merchant_payout(
                user=self.owner,
                amount=Decimal('150.00'),
                payout_method=StorePayout.METHOD_BANK_TRANSFER,
                account_details={},
                store=self.store,
            )

        wallet.refresh_from_db()
        self.assertEqual(wallet.available_balance, Decimal('200.00'))
        self.assertFalse(StorePayout.objects.filter(wallet=wallet).exists())



    def test_unified_payout_filters_run_before_pagination(self) -> None:
        from store.models import StorePayout
        matching = StorePayout.objects.create(
            store=self.store, amount=Decimal('50.00'), payout_method='bank_transfer',
            reference='PO-AUDIT-MATCH', status=StorePayout.STATUS_PENDING,
        )
        StorePayout.objects.create(
            store=self.store, amount=Decimal('5.00'), payout_method='bank_transfer',
            reference='PO-AUDIT-SMALL', status=StorePayout.STATUS_COMPLETED,
        )
        response = self.client.get('/stores/wallet/payouts/', {
            'search': 'AUDIT', 'status': 'pending', 'min_amount': '25.00',
            'payout_method': 'bank_transfer',
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], matching.pk)
        invalid = self.client.get('/stores/wallet/payouts/', {'min_amount': 'invalid'})
        self.assertEqual(invalid.status_code, 400)

    def test_bank_payout_requests_require_a_destination_before_reserving_funds(self) -> None:
        from store.models import StorePayout
        before = StorePayout.objects.count()
        for path in ('/stores/wallet/payouts/', f'/stores/{self.store.pk}/payouts/'):
            response = self.client.post(path, {'amount': '5.00', 'payout_method': 'bank_transfer'}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(StorePayout.objects.count(), before)

    def test_dashboard_caps_withdrawals_by_unified_wallet_after_legacy_payouts(self) -> None:
        from store.models import StorePayout
        wallet = MerchantWallet.objects.create(user=self.owner)
        StoreEarningsLedger.objects.create(wallet=wallet, store=self.store, net_amount=Decimal('100.00'), status=StoreEarningsLedger.STATUS_AVAILABLE)
        StorePayout.objects.create(wallet=wallet, amount=Decimal('120.00'), status=StorePayout.STATUS_COMPLETED, reference='LEGACY-UNSCOPED')
        response = self.client.get(f'/stores/{self.store.pk}/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['wallet']['available_balance'], '100.00')
        self.assertEqual(response.data['wallet']['withdrawable_balance'], '0.00')

    def test_repeat_financial_seeding_preserves_existing_payout_debits(self) -> None:
        from io import StringIO
        from core.management.commands.populate_fake_data import Command
        from store.models import StorePayout
        wallet = MerchantWallet.objects.create(user=self.owner)
        StoreEarningsLedger.objects.create(wallet=wallet, store=self.store, net_amount=Decimal('10000.00'), status=StoreEarningsLedger.STATUS_AVAILABLE)
        command = Command(stdout=StringIO())
        command.seed_financial_ledgers([], [])
        command.seed_financial_ledgers([], [])
        wallet.refresh_from_db()
        self.assertEqual(StorePayout.objects.filter(wallet=wallet).count(), 1)
        self.assertEqual(wallet.total_withdrawn, Decimal('6000.00'))
        self.assertEqual(wallet.available_balance, Decimal('4000.00'))
