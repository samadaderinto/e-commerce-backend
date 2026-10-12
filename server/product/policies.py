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
    if not product.variants:
        if name:
            raise ValidationError({'variant': 'This product has no variant options.'})
        return None
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
