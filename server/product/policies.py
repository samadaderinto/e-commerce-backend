from __future__ import annotations

from typing import Any
from rest_framework.exceptions import ValidationError


def is_own_store(product: Any, user: Any) -> bool:
    store = getattr(product, "store", None)
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and store
        and not getattr(store, "is_official", False)
        and store.user_id == user.pk
    )


def validate_purchase(product: Any, user: Any) -> None:
    if product.is_blocked:
        raise ValidationError({'detail': 'This product is blocked and cannot be purchased.'})
    from django.utils import timezone
    if getattr(product, 'drop_at', None) and product.drop_at > timezone.now():
        raise ValidationError({
            'detail': f'This item is an upcoming drop and cannot be added to cart until {product.drop_at.isoformat()}.'
        })
    if product.product_type == 'affiliate_clickbank':
        raise ValidationError({
            'detail': 'This partner listing uses the vendor checkout. Open its official partner link.'
        })
    from core.access import is_backoffice
    if is_backoffice(user):
        raise ValidationError({"detail": "Administrative accounts cannot purchase products."})
    if is_own_store(product, user):
        raise ValidationError({'detail': 'You cannot buy products from any store you own.'})

    from store.services import has_store_address
    if not has_store_address(product.store):
        raise ValidationError({'store_address': 'This store must add a complete business address before its products can be purchased.'})


def selected_variant(product: Any, name: str = '') -> dict[str, Any] | None:
    if not name:
        # The main listing is always purchasable. Variants are opt-in
        # alternatives rather than a required replacement for the product.
        return None
    if not product.variants:
        raise ValidationError({'variant': 'This product has no variant options.'})
    variant = next((row for row in product.variants if row.get('name') == name), None)
    if variant is None:
        raise ValidationError({'variant': 'Select an available product option.'})
    return variant


def restock_variant(product: Any, name: str, quantity: int) -> None:
    if name:
        for row in product.variants:
            if row.get('name') == name and row.get('available') is not None:
                row['available'] += quantity
                break


def check_drop_bot_protection(product: Any, request: Any) -> None:
    """Anti-bot rate limiting for scheduled product drops to mitigate rapid sniper scripts."""
    if not getattr(product, 'drop_at', None) or not request:
        return
    from django.core.cache import cache
    meta = getattr(request, 'META', {})
    forwarded = meta.get('HTTP_X_FORWARDED_FOR')
    ip = forwarded.split(',')[0].strip() if forwarded else meta.get('REMOTE_ADDR', '127.0.0.1')
    user = getattr(request, 'user', None)
    identifier = user.pk if user and user.is_authenticated else ip
    key = f'drop_bot_guard:{product.pk}:{identifier}'
    current_count = cache.get(key, 0)
    if current_count >= 10:
        raise ValidationError({'detail': 'Anti-bot protection active. High-frequency requests detected on scheduled drop. Please wait a moment.'})
    cache.set(key, current_count + 1, timeout=10)
