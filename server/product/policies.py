from __future__ import annotations

from typing import Any
from rest_framework.exceptions import ValidationError


def is_own_store(product: Any, user: Any) -> bool:
    return bool(user and getattr(user, "is_authenticated", False) and getattr(product, "store", None) and product.store.user_id == user.pk)


def validate_purchase(product: Any, user: Any) -> None:
    if is_own_store(product, user):
        raise ValidationError({'detail': 'You cannot buy products from any store you own.'})

