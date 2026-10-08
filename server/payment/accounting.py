"""Cent-exact allocation of immutable amounts paid for order lines."""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Any, Sequence

from payment.models import Coupon, Order

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def allocate_amount(amount: Decimal, weights: Sequence[Decimal]) -> list[Decimal]:
    """Distribute cents by largest remainder, preserving the exact total."""
    total = sum(weights, ZERO)
    if not weights or total <= 0:
        return [ZERO for _ in weights]
    cents = int(amount.quantize(CENT, rounding=ROUND_HALF_UP) * 100)
    shares = [Decimal(cents) * weight / total for weight in weights]
    whole = [int(share.to_integral_value(rounding=ROUND_DOWN)) for share in shares]
    remainder = cents - sum(whole)
    indices = sorted(
        range(len(weights)), key=lambda i: (shares[i] - whole[i], -i), reverse=True
    )
    for index in indices[:remainder]:
        whole[index] += 1
    return [Decimal(value) / 100 for value in whole]


def coupon_matches(coupon: Coupon, product: Any) -> bool:
    return (
        coupon.type == Coupon.ORDER_TOTAL
        or (
            coupon.type in (Coupon.PRODUCT, Coupon.PRODUCT_QUANTITY)
            and coupon.product_id == product.pk
        )
        or (
            coupon.type == Coupon.CATEGORY
            and coupon.category.casefold() == product.category.casefold()
        )
    )


def allocate_checkout_lines(
    snapshots: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    coupon: Coupon | None,
    discount: Decimal,
) -> list[dict[str, Any]]:
    gross = [Decimal(row["unit_price"]) * int(row["quantity"]) for row in snapshots]
    weights = [
        amount
        if coupon is not None and coupon_matches(coupon, line["product"])
        else ZERO
        for amount, line in zip(gross, lines)
    ]
    discounts = allocate_amount(discount, weights)
    return [
        {
            **row,
            "line_subtotal": str(amount),
            "discount_amount": str(reduction),
            "net_total": str(amount - reduction),
        }
        for row, amount, reduction in zip(snapshots, gross, discounts)
    ]


def allocate_line_taxes(
    snapshots: list[dict[str, Any]], taxes: list[Decimal]
) -> list[dict[str, Any]]:
    return [
        {
            **row,
            "tax_amount": str(tax),
            "line_total": str(Decimal(row["net_total"]) + tax),
        }
        for row, tax in zip(snapshots, taxes)
    ]


def order_paid_lines(order: Order) -> list[dict[str, Any]]:
    """Read final amounts, conservatively reconstructing pre-allocation orders."""
    rows = list(order.items_snapshot or [])
    if not rows or all("net_total" in row and "line_total" in row for row in rows):
        return rows
    gross = [
        Decimal(str(row.get("unit_price", "0"))) * int(row.get("quantity", 1))
        for row in rows
    ]
    shipping = Decimal(
        str(
            (order.shipping_snapshot or {}).get(
                "amount", order.delivery.total if order.delivery else "0"
            )
        )
    )
    net = min(sum(gross, ZERO), max(ZERO, order.total - shipping - order.tax))
    allocated = allocate_amount(net, gross)
    shipping_tax = Decimal(str((order.tax_snapshot or {}).get("shipping_tax", "0")))
    tax_weights = [
        amount if not row.get("is_digital") else ZERO
        for amount, row in zip(allocated, rows)
    ]
    if sum(tax_weights, ZERO) == 0:
        tax_weights = allocated
    taxes = allocate_amount(max(ZERO, order.tax - shipping_tax), tax_weights)
    return [
        {
            **row,
            "net_total": str(amount),
            "tax_amount": str(tax),
            "line_total": str(amount + tax),
        }
        for row, amount, tax in zip(rows, allocated, taxes)
    ]
