from django.conf import settings
from django.core.cache import cache

from product.models import Product
from product.serializers import ProductSerializer
from utils.cache import invalidate_revision, versioned_lru_cache


PRODUCT_CACHE_TIMEOUT = getattr(settings, "CACHE_TIMEOUT", 300)
PRODUCT_CACHE_MAX_ENTRIES = getattr(settings, "CACHE_MAX_ENTRIES", 256)
LANDING_PRODUCTS_CACHE_KEY = "products:landing"


def product_cache_key(product_id):
    return f"products:detail:{product_id}"


def store_product_cache_key(store_id, product_id):
    return f"stores:{store_id}:products:{product_id}"


def invalidate_product_cache(product):
    invalidate_revision('products')
    cache.delete(LANDING_PRODUCTS_CACHE_KEY)
    cache.delete(product_cache_key(product.id))
    cache.delete(store_product_cache_key(product.store_id, product.id))
    get_cached_product_data.cache_clear()
    get_cached_store_product_data.cache_clear()
    get_cached_landing_products.cache_clear()


@versioned_lru_cache('products')
def get_cached_product_data(product_id):
    product = Product.objects.get(id=product_id, visibility=True, store__status="active")
    return dict(ProductSerializer(product).data)


@versioned_lru_cache('products')
def get_cached_store_product_data(store_id, product_id):
    product = Product.objects.get(
        store=store_id,
        id=product_id,
        visibility=True,
        store__status="active",
    )
    return dict(ProductSerializer(product).data)


@versioned_lru_cache('products')
def get_cached_landing_products():
    products = Product.objects.filter(visibility=True, store__status="active")
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
