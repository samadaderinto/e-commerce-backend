from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone

from core.models import User
from product.cache import get_cached_landing_products
from product.models import Product, ProductImg
from store.models import Store


class CachedProductQueryTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        get_cached_landing_products.cache_clear()
        owner = User.objects.create_user(
            email="catalog-cache-performance@example.com",
            password="test-password",
        )
        store = Store.objects.create(
            user=owner,
            name="Catalog cache performance",
            status=Store.STATUS_ACTIVE,
            verified_at=timezone.now(),
        )
        products = Product.objects.bulk_create([
            Product(
                store=store,
                title=f"Cached product {index}",
                description="A product with related images and tags.",
                category="electronics",
                price=Decimal("10.00"),
                discount=0,
                available=5,
            )
            for index in range(12)
        ])
        ProductImg.objects.bulk_create([
            ProductImg(product=product, image=f"images/catalog-{product.pk}.png")
            for product in products
        ])
        for product in products:
            product.tags.add("cache-query")

    def tearDown(self) -> None:
        cache.clear()
        get_cached_landing_products.cache_clear()

    def test_landing_cache_cold_query_count_is_bounded_by_page_groups(self) -> None:
        with CaptureQueriesContext(connection) as queries:
            response = get_cached_landing_products()

        self.assertEqual(len(response["newest_products"]), 10)
        self.assertLessEqual(len(queries), 10)

        with CaptureQueriesContext(connection) as warm_queries:
            second_response = get_cached_landing_products()

        self.assertEqual(second_response, response)
        self.assertEqual(len(warm_queries), 0)
