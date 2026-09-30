from django.conf import settings
from django.core.cache import cache

from cart.models import Cart
from cart.seralizers import CartSerializer
from utils.cache import invalidate_revision, versioned_lru_cache


CART_CACHE_TIMEOUT = getattr(settings, "CACHE_TIMEOUT", 300)
CART_CACHE_MAX_ENTRIES = getattr(settings, "CACHE_MAX_ENTRIES", 256)


def active_cart_cache_key(user_id):
    return f"users:{user_id}:cart:active"


def cart_cache_key(cart_id):
    return f"carts:{cart_id}:detail"


def invalidate_cart_cache(cart):
    invalidate_revision('carts')
    cache.delete(cart_cache_key(cart.id))
    cache.delete(active_cart_cache_key(cart.user_id))
    get_cached_cart_data.cache_clear()
    get_cached_active_cart_data.cache_clear()


@versioned_lru_cache('carts')
def get_cached_cart_data(cart_id):
    cart = (
        Cart.objects
        .prefetch_related("cart_items__product")
        .get(id=cart_id)
    )
    return dict(CartSerializer(cart).data)


@versioned_lru_cache('carts')
def get_cached_active_cart_data(user_id):
    cart = (
        Cart.objects
        .prefetch_related("cart_items__product")
        .get(user=user_id, ordered=False)
    )
    return dict(CartSerializer(cart).data)
