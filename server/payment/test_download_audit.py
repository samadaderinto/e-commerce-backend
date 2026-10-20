from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import User
from payment.models import Order
from product.models import Product
from store.models import Store


@override_settings(ROOT_URLCONF='storefront.urls')
class DownloadAuditTests(TestCase):
    def setUp(self) -> None:
        self.buyer = User.objects.create_user(email='download-audit@test.local', password='test')
        store = Store.objects.create(user=self.buyer, name='Download fixture')
        self.product = Product.objects.create(
            store=store, title='Digital fixture', price='10', discount=0,
            available=1, is_digital=True,
            digital_file_url='digital_products/replacement.txt',
        )
        self.order = Order.objects.create(
            user=self.buyer, ordered=True, status='delivered', total='10', paid_total='10',
            items_snapshot=[{
                'product': self.product.pk, 'is_digital': True,
                'download_url': 'digital_products/purchased.txt',
            }],
        )
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)
        self.url = f'/api/v1/orders/{self.order.pk}/downloads/{self.product.pk}/'

    def test_missing_purchased_asset_does_not_substitute_current_product_file(self) -> None:
        with patch('django.core.files.storage.default_storage.exists', side_effect=lambda path: path == self.product.digital_file_url), patch(
            'django.core.files.storage.default_storage.open', return_value=BytesIO(b'WRONG EDITION'),
        ) as opened:
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 404)
            opened.assert_not_called()

    def test_storage_outage_returns_safe_retryable_response(self) -> None:
        with patch('django.core.files.storage.default_storage.exists', side_effect=OSError('SECRET storage endpoint')):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('SECRET', str(response.data))

    def test_recorded_file_still_streams_with_private_cache_headers(self) -> None:
        with patch('django.core.files.storage.default_storage.exists', return_value=True), patch(
            'django.core.files.storage.default_storage.open', return_value=BytesIO(b'PURCHASED'),
        ):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'PURCHASED')
            self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_legacy_purchase_without_recorded_asset_keeps_current_file_fallback(self) -> None:
        self.order.items_snapshot[0].pop('download_url')
        self.order.save(update_fields=['items_snapshot'])
        with patch('django.core.files.storage.default_storage.exists', return_value=True), patch(
            'django.core.files.storage.default_storage.open', return_value=BytesIO(b'LEGACY'),
        ):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'LEGACY')
