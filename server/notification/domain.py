"""Recipient-scoped business notices shared across request and decision paths."""
from typing import Any

from core.models import Refund, User
from notification.events import operators, store_recipients
from notification.views import create_notification
from store.models import Store


def refund_notice(refund: Refund, actor: User, items: list[dict[str, Any]], *, updated: bool = False, decision: str = "") -> None:
    ids = {int(row["store"]) for row in items if row.get("store")}
    recipients = {user.pk: user for user in operators(admins_only=True)}
    scoped = {user_id: set(ids) for user_id in recipients}
    for store in Store.objects.filter(pk__in=ids).select_related("user"):
        for user in store_recipients(store):
            recipients[user.pk] = user
            scoped.setdefault(user.pk, set()).add(store.pk)
    if not decision and refund.order.user_id:
        recipients[refund.order.user_id] = refund.order.user
        scoped[refund.order.user_id] = ids
    event = f"refund_{decision}" if decision else "refund_updated" if updated else "refund_requested"
    for user in recipients.values():
        if decision and user.pk == refund.order.user_id:
            continue  # The existing decision receipt/inbox is authoritative for the buyer.
        create_notification(
            user, f"Refund {'updated' if updated else decision or 'requested'} for Order #{refund.order.orderId}",
            actor=actor, target=refund,
            description=f"Refund {decision or ('updated' if updated else 'requested')}. Reason: {refund.reason}",
            data={
                "event": event, "refund_id": refund.pk, "order_id": refund.order_id,
                "store_ids": sorted(scoped[user.pk]),
                "email": updated or decision != "" or user.pk != refund.order.user_id,
            },
            event_key=f"refund:{refund.pk}:{event}:{refund.updated}",
        )
