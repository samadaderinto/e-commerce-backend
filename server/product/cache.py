from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, QuerySet

from product.models import Product
from product.serializers import ProductSerializer
from utils.cache import invalidate_revision, versioned_lru_cache


PRODUCT_CACHE_TIMEOUT = getattr(settings, "CACHE_TIMEOUT", 300)
PRODUCT_CACHE_MAX_ENTRIES = getattr(settings, "CACHE_MAX_ENTRIES", 256)
LANDING_PRODUCTS_CACHE_KEY = "products:landing"


def product_cache_key(product_id: int | str) -> str:
    return f"products:detail:{product_id}"


def store_product_cache_key(store_id: int | str, product_id: int | str) -> str:
    return f"stores:{store_id}:products:{product_id}"


def public_product_queryset() -> QuerySet[Product]:
    return Product.objects.filter(
        visibility=True, is_blocked=False,
        store__status="active",
        store__verified_at__isnull=False,
    ).annotate(
        likes_count=Count("wishlist", distinct=True)
    ).prefetch_related("images", "tags")


def invalidate_product_cache(product: Any) -> None:
    from storefront.catalog_cache import invalidate_catalog_snapshot

    invalidate_catalog_snapshot()
    invalidate_product_payload_cache(product.id, product.store_id)


def invalidate_product_payload_cache(product_id: int, store_id: int) -> None:
    """Invalidate serialized product responses without touching catalog snapshots."""
    invalidate_product_payload_caches(((product_id, store_id),))


def invalidate_product_payload_caches(products: tuple[tuple[int, int], ...]) -> None:
    if not products:
        return
    invalidate_revision('products')
    keys = [LANDING_PRODUCTS_CACHE_KEY]
    for product_id, store_id in products:
        keys.extend((product_cache_key(product_id), store_product_cache_key(store_id, product_id)))
    cache.delete_many(keys)
    get_cached_product_data.cache_clear()
    get_cached_store_product_data.cache_clear()
    get_cached_landing_products.cache_clear()


def invalidate_store_product_payload_cache(store_id: int) -> None:
    products = tuple(
        (product_id, store_id)
        for product_id in Product.objects.filter(store_id=store_id).values_list('pk', flat=True)
    )
    invalidate_product_payload_caches(products)


@versioned_lru_cache('products')
def get_cached_product_data(product_id: int) -> dict[str, Any]:
    product = public_product_queryset().get(id=product_id)
    return dict(ProductSerializer(product).data)


@versioned_lru_cache('products')
def get_cached_store_product_data(store_id: int, product_id: int) -> dict[str, Any]:
    product = public_product_queryset().get(store=store_id, id=product_id)
    return dict(ProductSerializer(product).data)


@versioned_lru_cache('products')
def get_cached_landing_products() -> dict[str, Any]:
    products = public_product_queryset()
    newest_products = products.order_by('-created', '-pk')[:10]
    highest_rated_products = products.order_by('-average_rating', '-pk')[:10]
    best_selling_products = products.order_by('-sales', '-pk')[:10]

    return {
        'newest_products': ProductSerializer(newest_products, many=True).data,
        'highest_rated_products': ProductSerializer(
            highest_rated_products, many=True
        ).data,
        'best_selling_products': ProductSerializer(
            best_selling_products, many=True
        ).data,
    }

