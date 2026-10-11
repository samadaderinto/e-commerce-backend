"""Exercise public snapshots outside TestCase's implicit transaction."""

from decimal import Decimal
from typing import Any
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection, transaction
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import User
from product.models import Product, Specification
from store.models import Store
from storefront.catalog_cache import REVISION_KEY


@override_settings(ROOT_URLCONF="storefront.urls", PUBLIC_CATALOG_CACHE_SECONDS=15)
class CatalogSnapshotTests(TransactionTestCase):
    def setUp(self) -> None:
        cache.clear()
        self.owner = User.objects.create_user(
            email="snapshot@test.com", password="test"
        )
        self.store = Store.objects.create(
            user=self.owner,
            name="Snapshot",
            status=Store.STATUS_ACTIVE,
            verified_at=timezone.now(),
        )
        self.product = Product.objects.create(
            store=self.store,
            title="Snapshot product",
            price=Decimal("10.00"),
            discount=0,
            available=5,
        )
        self.client = APIClient()

    def tearDown(self) -> None:
        cache.clear()

    def warm(self) -> dict[str, Any]:
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Catalog-Cache"], "MISS")
        return response.data

    def test_warm_snapshot_checks_authoritative_rows_in_two_queries(self) -> None:
        expected = self.warm()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/api/v1/products/")
        self.assertEqual(response["X-Catalog-Cache"], "HIT")
        self.assertEqual(response.data, expected)
        self.assertLessEqual(len(queries), 2)

    def test_bulk_price_stock_and_variant_changes_are_never_served_from_snapshot(
        self,
    ) -> None:
        for changes in (
            {"price": Decimal("12.00")},
            {"available": 1},
            {"discount": 10},
            {"variants": [{"name": "Blue", "stock": 1}]},
        ):
            self.client.get("/api/v1/products/")
            Product.objects.filter(pk=self.product.pk).update(**changes)
            response = self.client.get("/api/v1/products/")
            self.assertEqual(response["X-Catalog-Cache"], "MISS")
            for field, value in changes.items():
                actual = response.data["results"][0][field]
                self.assertEqual(actual, str(value) if field == "price" else value)

    def test_bulk_visibility_and_store_moderation_cannot_leak_cached_listing(
        self,
    ) -> None:
        self.warm()
        Store.objects.filter(pk=self.store.pk).update(status=Store.STATUS_BLOCKED)
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response["X-Catalog-Cache"], "MISS")
        Store.objects.filter(pk=self.store.pk).update(status=Store.STATUS_ACTIVE)
        self.client.get("/api/v1/products/")
        Product.objects.filter(pk=self.product.pk).update(visibility=False)
        self.assertEqual(self.client.get("/api/v1/products/").data["results"], [])

    def test_auth_search_and_atomic_requests_bypass_shared_snapshots(self) -> None:
        self.warm()
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.get("/api/v1/products/")["X-Catalog-Cache"], "BYPASS"
        )
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.get("/api/v1/products/?search=Snapshot")["X-Catalog-Cache"],
            "BYPASS",
        )
        with transaction.atomic():
            self.assertEqual(
                self.client.get("/api/v1/products/")["X-Catalog-Cache"], "BYPASS"
            )

    def test_related_specification_and_tag_changes_invalidate(self) -> None:
        self.warm()
        spec = Specification.objects.create(
            product=self.product,
            serial="real",
            attributes="Dimensions",
            height=1,
            width=2,
            breadth=3,
            weight=4,
            color="Blue",
        )
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response["X-Catalog-Cache"], "MISS")
        self.assertEqual(
            response.data["results"][0]["specifications"]["serial"], "real"
        )
        spec.delete()
        self.assertIsNone(
            self.client.get("/api/v1/products/").data["results"][0]["specifications"]
        )
        self.product.tags.add("real tag")
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response["X-Catalog-Cache"], "MISS")
        self.assertIn("real tag", response.data["results"][0]["tags"])
        self.product.tags.clear()
        self.assertEqual(
            self.client.get("/api/v1/products/").data["results"][0]["tags"], []
        )

    def test_rollback_cannot_publish_or_invalidate_uncommitted_snapshot(self) -> None:
        expected = self.warm()
        revision = cache.get(REVISION_KEY)
        try:
            with transaction.atomic():
                self.product.title = "Uncommitted title"
                self.product.save()
                self.assertEqual(cache.get(REVISION_KEY), revision)
                response = self.client.get("/api/v1/products/")
                self.assertEqual(response["X-Catalog-Cache"], "BYPASS")
                raise ValueError("rollback")
        except ValueError:
            pass
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response["X-Catalog-Cache"], "HIT")
        self.assertEqual(response.data, expected)

    def test_cache_failure_falls_back_to_live_catalog(self) -> None:
        self.warm()
        with patch(
            "storefront.catalog_cache.cache.get_or_set", side_effect=ConnectionError
        ):
            response = self.client.get("/api/v1/products/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Catalog-Cache"], "BYPASS")
        self.assertEqual(response.data["results"][0]["id"], self.product.pk)

    def test_missed_redis_invalidation_still_changes_transactional_version(
        self,
    ) -> None:
        self.warm()
        with patch("storefront.catalog_cache.cache.set", side_effect=ConnectionError):
            self.product.title = "Committed new title"
            self.product.save()
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response["X-Catalog-Cache"], "MISS")
        self.assertEqual(response.data["results"][0]["title"], "Committed new title")

    @override_settings(PUBLIC_CATALOG_CACHE_SECONDS=0)
    def test_configuration_can_disable_snapshots(self) -> None:
        self.assertEqual(
            self.client.get("/api/v1/products/")["X-Catalog-Cache"], "BYPASS"
        )

    def test_image_review_and_earnings_changes_invalidate(self) -> None:
        from core.models import Review
        from product.models import ProductImg
        from store.models import StoreEarningsLedger
        from store.services import get_or_create_merchant_wallet

        self.warm()
        image = ProductImg.objects.create(
            product=self.product, image="images/fixture.png"
        )
        self.assertEqual(
            self.client.get("/api/v1/products/")["X-Catalog-Cache"], "MISS"
        )
        image.delete()
        self.assertEqual(
            self.client.get("/api/v1/products/")["X-Catalog-Cache"], "MISS"
        )
        review = Review.objects.create(
            user=self.owner, product=self.product, label="Real", comment="Review"
        )
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response["X-Catalog-Cache"], "MISS")
        self.assertEqual(response.data["results"][0]["rating_count"], 1)
        review.delete()
        self.assertEqual(
            self.client.get("/api/v1/products/").data["results"][0]["rating_count"], 0
        )
        ledger = StoreEarningsLedger.objects.create(
            wallet=get_or_create_merchant_wallet(self.owner),
            store=self.store,
            gross_amount=Decimal("6000"),
            entry_type=StoreEarningsLedger.TYPE_SALE,
        )
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response["X-Catalog-Cache"], "MISS")
        self.assertEqual(response.data["results"][0]["seller_tier"]["tier"], "booster")
        ledger.status = StoreEarningsLedger.STATUS_REVERSED
        ledger.save()
        self.assertEqual(
            self.client.get("/api/v1/products/").data["results"][0]["seller_tier"][
                "current_sales"
            ],
            0,
        )

    def test_tag_rename_and_delete_invalidate(self) -> None:
        self.product.tags.add("original")
        self.warm()
        tag = self.product.tags.get(name="original")
        tag.name = "renamed"
        tag.save()
        self.assertEqual(
            self.client.get("/api/v1/products/").data["results"][0]["tags"], ["renamed"]
        )
        tag.delete()
        self.assertEqual(
            self.client.get("/api/v1/products/").data["results"][0]["tags"], []
        )

    def test_query_variants_and_empty_pages_do_not_share_snapshots(self) -> None:
        self.warm()
        filtered = self.client.get("/api/v1/products/?min_price=11")
        self.assertEqual(filtered.data["results"], [])
        self.assertEqual(filtered["X-Catalog-Cache"], "MISS")
        again = self.client.get("/api/v1/products/?min_price=11")
        self.assertEqual(again["X-Catalog-Cache"], "MISS")
        self.assertEqual(self.client.get("/api/v1/products/")["X-Catalog-Cache"], "HIT")
        invalid = self.client.get("/api/v1/products/?page=0")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.client.get("/api/v1/products/?page=0").status_code, 400)

    def test_owner_flag_never_reuses_anonymous_response(self) -> None:
        self.warm()
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/products/")
        self.assertTrue(response.data["results"][0]["is_own_store"])
        self.assertEqual(response["X-Catalog-Cache"], "BYPASS")
        self.client.force_authenticate(None)
        response = self.client.get("/api/v1/products/")
        self.assertFalse(response.data["results"][0]["is_own_store"])
        self.assertEqual(response["X-Catalog-Cache"], "HIT")

    def test_reader_during_tag_clear_cannot_poison_final_snapshot(self) -> None:
        from django.db.models.signals import m2m_changed
        from taggit.models import TaggedItem

        self.product.tags.add("before clear")
        self.warm()

        def concurrent_read(sender: type, action: str, **kwargs: Any) -> None:
            if action == "pre_clear":
                self.assertEqual(
                    self.client.get("/api/v1/products/").data["results"][0]["tags"],
                    ["before clear"],
                )

        m2m_changed.connect(concurrent_read, sender=TaggedItem, weak=False)
        try:
            self.product.tags.clear()
        finally:
            m2m_changed.disconnect(concurrent_read, sender=TaggedItem)
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response.data["results"][0]["tags"], [])
        self.assertEqual(response["X-Catalog-Cache"], "MISS")

    def test_earnings_revision_writes_happen_after_financial_commit(self) -> None:
        from store.models import StoreEarningsLedger
        from store.services import get_or_create_merchant_wallet

        wallet = get_or_create_merchant_wallet(self.owner)
        self.warm()
        original_stamp = Store.objects.get(pk=self.store.pk).updated
        original_revision = cache.get(REVISION_KEY)
        with transaction.atomic():
            StoreEarningsLedger.objects.create(
                wallet=wallet,
                store=self.store,
                gross_amount=Decimal("6000"),
                entry_type=StoreEarningsLedger.TYPE_SALE,
            )
            self.assertEqual(
                Store.objects.get(pk=self.store.pk).updated, original_stamp
            )
            self.assertEqual(cache.get(REVISION_KEY), original_revision)
        self.assertGreater(Store.objects.get(pk=self.store.pk).updated, original_stamp)
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response["X-Catalog-Cache"], "MISS")
        self.assertEqual(
            response.data["results"][0]["seller_tier"]["current_sales"], 6000
        )
