from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping, Optional, Sequence

from django.db import IntegrityError
from rest_framework.exceptions import ValidationError

from .models import Coupon, CouponRedemption


def calculate_coupon_discount(
    coupon: Optional[Coupon],
    user: Any,
    lines: Sequence[Mapping[str, Any]],
    subtotal: Decimal,
    reserve: bool = True,
) -> Decimal:
    """Return the discount for cart lines and reserve one user redemption."""
    if not coupon or not coupon.can_use():
        raise ValidationError({'coupon': 'This coupon is invalid or has expired.'})
    if CouponRedemption.objects.filter(coupon=coupon, user=user).exists():
        raise ValidationError({'coupon': 'You have already used this coupon.'})

    matching_total = Decimal('0')
    matching_quantity = 0
    for line in lines:
        product = line['product']
        quantity = line['quantity']
        matches = (
            coupon.type == Coupon.ORDER_TOTAL
            or (coupon.type in (Coupon.PRODUCT, Coupon.PRODUCT_QUANTITY) and coupon.product_id == product.pk)
            or (coupon.type == Coupon.CATEGORY and coupon.category.casefold() == product.category.casefold())
        )
        if matches:
            matching_total += line['unit_price'] * quantity
            matching_quantity += quantity

    if coupon.type == Coupon.PRODUCT_QUANTITY and matching_quantity < coupon.minimum_quantity:
        raise ValidationError({'coupon': f'Buy at least {coupon.minimum_quantity} units of the qualifying product to use this coupon.'})
    if coupon.type != Coupon.ORDER_TOTAL and not matching_total:
        raise ValidationError({'coupon': 'This coupon does not apply to anything in your cart.'})

    base = subtotal if coupon.type == Coupon.ORDER_TOTAL else matching_total
    discount = (base * Decimal(coupon.discount) / Decimal('100')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    if reserve:
        try:
            CouponRedemption.objects.create(coupon=coupon, user=user)
        except IntegrityError:
            raise ValidationError({'coupon': 'You have already used this coupon.'})
    return discount

