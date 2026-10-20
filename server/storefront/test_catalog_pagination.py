from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Lock
import time
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import User
from product.models import Product
from store.models import Store
from storefront.catalog_cache import coalesced_snapshot


@override_settings(ROOT_URLCONF='storefront.urls', PUBLIC_CATALOG_CACHE_SECONDS=0)
class CatalogPaginationTests(TestCase):
    def setUp(self) -> None:
        owner = User.objects.create_user(email='pagination@test.com', password='test')
        self.store = Store.objects.create(user=owner, name='Pagination',
                                         status=Store.STATUS_ACTIVE, verified_at=timezone.now())
        Product.objects.bulk_create([
            Product(store=self.store, title=f'Product {index}', category='electronics',
                    price=Decimal(index + 1), discount=0, available=5)
            for index in range(60)
        ])
        self.client = APIClient()

    def test_extreme_page_is_rejected_instead_of_overflowing_database(self) -> None:
        response = self.client.get('/api/v1/products/?page=999999999999999999999999999999')
        self.assertEqual(response.status_code, 400)

    def test_valid_page_beyond_catalog_returns_empty_without_offset_query(self) -> None:
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/api/v1/products/?page=2147483647')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], [])
        self.assertEqual(response.data['count'], 60)
        self.assertFalse(any('OFFSET' in query['sql'].upper() for query in queries))

    def test_page_ids_are_sorted_before_model_hydration(self) -> None:
        expected = list(Product.objects.order_by('price', '-pk').values_list('pk', flat=True)[24:48])
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/api/v1/products/?page=2&ordering=price')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.data['results']], expected)
        self.assertEqual(response.data['count'], 60)
        self.assertEqual(response.data['pages'], 3)
        self.assertLessEqual(len(queries), 6)
        id_queries = [row['sql'] for row in queries if 'LIMIT 24 OFFSET 24' in row['sql']]
        self.assertEqual(len(id_queries), 1)
        projection = id_queries[0].split(' FROM ')[0]
        self.assertNotIn('description', projection)
        self.assertNotIn('rating_count', projection)

    def test_filters_empty_pages_and_visibility_remain_authoritative(self) -> None:
        Product.objects.filter(price__gte=50).update(visibility=False)
        response = self.client.get('/api/v1/products/?min_price=20&max_price=55&ordering=-price')
        expected = list(Product.objects.filter(visibility=True, price__gte=20, price__lte=55)
                        .order_by('-price', '-pk').values_list('pk', flat=True)[:24])
        self.assertEqual([row['id'] for row in response.data['results']], expected)
        self.assertEqual(response.data['count'], 30)
        self.assertEqual(self.client.get('/api/v1/products/?page=999').data['results'], [])
        Store.objects.filter(pk=self.store.pk).update(status=Store.STATUS_BLOCKED)
        self.assertEqual(self.client.get('/api/v1/products/').data['count'], 0)

    def test_sql_search_keeps_all_terms_and_ranked_order(self) -> None:
        product = Product.objects.first()
        product.tags.add('studio')
        response = self.client.get('/api/v1/products/?search=Product+studio')
        self.assertEqual([row['id'] for row in response.data['results']], [product.pk])


class CatalogCoalescingTests(SimpleTestCase):
    def setUp(self) -> None:
        cache.clear()
        self.addCleanup(cache.clear)

    def test_concurrent_followers_share_one_builder_without_releasing_lease(self) -> None:
        builds = 0
        lock = Lock()
        payload = {'results': [], 'count': 0}

        def request(_: int) -> dict:
            nonlocal builds
            existing = coalesced_snapshot('test:coalesce')
            if existing is not None:
                return existing
            with lock:
                builds += 1
            time.sleep(0.04)
            cache.set('test:coalesce', payload, timeout=2)
            return payload

        with patch('storefront.catalog_cache.read_snapshot', side_effect=cache.get):
            with ThreadPoolExecutor(max_workers=8) as pool:
                responses = list(pool.map(request, range(8)))
        self.assertEqual(builds, 1)
        self.assertEqual(responses, [payload] * 8)
        self.assertTrue(cache.get('test:coalesce:building'))

    def test_wait_is_bounded_and_missing_keys_bypass(self) -> None:
        self.assertIsNone(coalesced_snapshot(None))
        cache.set('test:blocked:building', True, timeout=2)
        with patch('storefront.catalog_cache.time.monotonic', side_effect=[0, 0.3]):
            self.assertIsNone(coalesced_snapshot('test:blocked'))
