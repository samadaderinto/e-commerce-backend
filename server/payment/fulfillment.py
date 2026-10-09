"""Store-scoped fulfillment and safe aggregate order status."""

from __future__ import annotations

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from payment.models import Order, OrderFulfillment
from store.models import Store

TRANSITIONS: dict[str, set[str]] = {
    "pending": {"pending", "confirmed", "shipped", "delivered", "picked up"},
    "confirmed": {"confirmed", "shipped", "delivered", "picked up"},
    "shipped": {"shipped", "delivered"},
    "delivered": {"delivered"},
    "picked up": {"picked up"},
}


def ensure_fulfillments(order: Order) -> None:
    """Caller holds the order lock; legacy snapshots can fall back to the cart."""
    store_ids = {
        row.get("store")
        for row in order.items_snapshot or []
        if row.get("store") and not row.get("is_digital")
    }
    if not store_ids and order.cart_id:
        store_ids = set(
            order.cart.cart_items.filter(product__is_digital=False).values_list(
                "product__store_id", flat=True
            )
        )
    status = order.status if order.status in TRANSITIONS else "confirmed"
    for store_id in sorted(store_ids):
        OrderFulfillment.objects.get_or_create(
            order=order, store_id=store_id, defaults={"status": status}
        )


def update_fulfillment(
    order: Order,
    store: Store,
    next_status: str | None,
    carrier: str,
    tracking_number: str,
) -> OrderFulfillment:
    """Mutate one store only. Financial states remain in the payment workflow."""
    if order.status in {"cancelled", "refunded"}:
        raise ValidationError(
            {"order": f"Cannot fulfill an order with status {order.status}."}
        )
    ensure_fulfillments(order)
    fulfillment = order.fulfillments.filter(store=store).first()
    if fulfillment is None:
        raise ValidationError({"order": "This store has no physical items to fulfill."})
    target = next_status or (
        "shipped"
        if tracking_number and fulfillment.status in {"pending", "confirmed"}
        else fulfillment.status
    )
    if target not in TRANSITIONS.get(fulfillment.status, set()):
        raise ValidationError(
            {
                "status": "Choose a valid forward fulfillment transition. Financial statuses require support."
            }
        )
    now = timezone.now()
    fulfillment.status = target
    if tracking_number:
        fulfillment.tracking_number = tracking_number
        fulfillment.carrier = carrier
    if target in {"shipped", "delivered"} and not fulfillment.shipped_at:
        fulfillment.shipped_at = now
    if target in {"delivered", "picked up"} and not fulfillment.delivered_at:
        fulfillment.delivered_at = now
    fulfillment.save()
    statuses = list(order.fulfillments.values_list("status", flat=True))
    if all(value in {"delivered", "picked up"} for value in statuses):
        order.status = (
            "picked up"
            if all(value == "picked up" for value in statuses)
            else "delivered"
        )
        order.delivered_at = now
        if not order.shipped_at:
            order.shipped_at = now
    elif any(value in {"shipped", "delivered", "picked up"} for value in statuses):
        order.status = "shipped"
        if not order.shipped_at:
            order.shipped_at = now
    if len(statuses) == 1:
        order.tracking_number = fulfillment.tracking_number
        order.carrier = fulfillment.carrier or carrier
        order.shipped_at = fulfillment.shipped_at
        order.delivered_at = fulfillment.delivered_at
    return fulfillment
