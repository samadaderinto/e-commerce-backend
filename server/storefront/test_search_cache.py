"""Search caching must never replace authoritative product hydration."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.db import transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import User
from product.models import Product
from store.models import Store


@override_settings(ROOT_URLCONF="storefront.urls")
class SearchCacheSafetyTests(TransactionTestCase):
    def setUp(self) -> None:
        cache.clear()
        self.owner = User.objects.create_user(email="search-cache@test.com", password="test")
        self.store = Store.objects.create(
            user=self.owner, name="Search", status=Store.STATUS_ACTIVE,
            verified_at=timezone.now(),
        )
        self.product = Product.objects.create(
            store=self.store, title="Headphones", price=Decimal("20.00"),
            available=5, discount=0,
        )
        self.client = APIClient()
        self.search = patch("storefront.views.search_product_ids", return_value={
            "ids": [self.product.pk], "count": 1,
        }).start()
        self.addCleanup(patch.stopall)
        self.addCleanup(cache.clear)

    def test_only_anonymous_nontransactional_reads_opt_in(self) -> None:
        self.assertEqual(self.client.get("/api/v1/products/?search=headphones").status_code, 200)
        self.assertTrue(self.search.call_args.kwargs["use_request_cache"])
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/products/?search=headphones")
        self.assertFalse(self.search.call_args.kwargs["use_request_cache"])
        self.assertTrue(response.data["results"][0]["is_own_store"])
        self.client.force_authenticate(None)
        with transaction.atomic():
            self.client.get("/api/v1/products/?search=headphones")
            self.assertFalse(self.search.call_args.kwargs["use_request_cache"])

    def test_reused_ids_still_read_price_stock_and_variants_from_database(self) -> None:
        self.client.get("/api/v1/products/?search=headphones")
        Product.objects.filter(pk=self.product.pk).update(
            price=Decimal("25.00"), available=2, variants=[{"name": "Blue", "stock": 2}],
        )
        response = self.client.get("/api/v1/products/?search=headphones")
        row = response.data["results"][0]
        self.assertEqual(row["price"], "25.00")
        self.assertEqual(row["available"], 2)
        self.assertEqual(row["variants"], [{"name": "Blue", "stock": 2}])

    def test_stale_ids_cannot_expose_blocked_or_hidden_products(self) -> None:
        Store.objects.filter(pk=self.store.pk).update(status=Store.STATUS_BLOCKED)
        self.assertEqual(self.client.get("/api/v1/products/?search=headphones").data["results"], [])
        Store.objects.filter(pk=self.store.pk).update(status=Store.STATUS_ACTIVE)
        Product.objects.filter(pk=self.product.pk).update(visibility=False)
        self.assertEqual(self.client.get("/api/v1/products/?search=headphones").data["results"], [])

    def test_stale_ids_still_obey_current_price_and_category_filters(self) -> None:
        response = self.client.get("/api/v1/products/?search=headphones&max_price=10")
        self.assertEqual(response.data["results"], [])
        response = self.client.get("/api/v1/products/?search=headphones&category=other")
        self.assertEqual(response.data["results"], [])
