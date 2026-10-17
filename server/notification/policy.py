"""Canonical inbox classification, recipient destinations and channel selection."""
from dataclasses import dataclass
from typing import Any

from django.db.models import Model

CATEGORIES: dict[str, str] = {
    "order": "Orders", "refund": "Refunds", "payout": "Payouts",
    "wallet": "Wallet", "store": "Stores", "affiliates": "Affiliates & Referrals",
    "account": "Account & Security", "general": "General",
}


@dataclass(frozen=True)
class ChannelPolicy:
    email: bool = True
    push: bool = True
    template: str | None = None


POLICIES: dict[str, ChannelPolicy] = {
    "store_created": ChannelPolicy(email=False),
    "shipping_updated": ChannelPolicy(email=False),
    "store_verified": ChannelPolicy(template="store-status"),
    "store_blocked": ChannelPolicy(template="store-status"),
    "store_unblocked": ChannelPolicy(template="store-status"),
    "product_blocked": ChannelPolicy(template="product-status"),
    "product_restored": ChannelPolicy(template="product-status"),
    "account_access_changed": ChannelPolicy(template="account-security"),
    "password_changed": ChannelPolicy(template="account-security"),
    "inventory_low": ChannelPolicy(template="inventory-low"),
    "order_confirmed": ChannelPolicy(template="order-confirm"),
    "order_picked_up": ChannelPolicy(template="order-picked-up"),
    "order_pickup": ChannelPolicy(template="order-picked-up"),
    "wallet_purchase": ChannelPolicy(email=False, push=False),
}


def category_for(data: dict[str, Any], verb: str, target_model: str = "") -> str:
    explicit = str(data.get("category") or "").lower()
    if explicit in CATEGORIES:
        return explicit
    text = f"{data.get('event', '')} {verb} {target_model}".lower()
    for category, keywords in (
        ("affiliates", ("affiliate", "referral")),
        ("refund", ("refund",)),
        ("payout", ("payout", "withdrawal")),
        ("wallet", ("wallet", "deposit")),
        ("order", ("order", "shipping")),
        ("store", ("store", "inventory", "verification_submitted")),
        ("account", ("account", "password", "staff")),
    ):
        if any(word in text for word in keywords):
            return category
    return "general"


def store_ids_for(data: dict[str, Any], target: Model | None = None) -> set[int]:
    raw = list(data.get("store_ids") or [])
    raw.extend([data.get("store_id"), data.get("store")])
    if target is not None and target._meta.model_name == "store":
        raw.append(target.pk)
    ids = {int(value) for value in raw if str(value).isdigit() and int(value) > 0}
    if not ids and target is not None:
        if getattr(target, "store_id", None):
            ids.add(int(target.store_id))
        items = getattr(target, "selected_items", None) or getattr(target, "items_snapshot", None)
        if not items and getattr(target, "order_id", None):
            items = target.order.items_snapshot
        ids.update(int(row["store"]) for row in items or [] if row.get("store"))
    return ids


def destination_for(recipient: Any, category: str, data: dict[str, Any]) -> str:
    if category in {"order", "refund"} and data.get("order_id"):
        if recipient.is_superuser or recipient.is_business_admin or recipient.is_staff:
            if category == "refund" and data.get("refund_id"):
                return f"/admin/refunds?refund={data['refund_id']}"
            return f"/admin/orders?order={data['order_id']}"
        from payment.models import Order
        if Order.objects.filter(pk=data["order_id"], user=recipient).exists():
            return f"/orders/{data['order_id']}"
        from store.models import Store

        raw_store_ids = list(data.get("store_ids") or [])
        raw_store_ids.append(data.get("store_id"))
        store_ids: set[int] = set()
        for value in raw_store_ids:
            try:
                store_id = int(value)
            except (TypeError, ValueError):
                continue
            if store_id > 0:
                store_ids.add(store_id)
        if store_ids:
            store = Store.objects.filter(pk__in=store_ids, user=recipient).order_by("pk").first()
            if store is None:
                store = Store.objects.filter(pk__in=store_ids, assigned_staff=recipient).order_by("pk").first()
            if store is not None:
                if category == "refund" and data.get("refund_id"):
                    return f"/merchant/refunds?store={store.pk}&refund={data['refund_id']}"
                return f"/merchant/orders?store={store.pk}&order={data['order_id']}"
        if category == "refund" and data.get("refund_id"):
            return f"/merchant/refunds?refund={data['refund_id']}"
        return "/merchant/orders"
    if category == "payout":
        payout_id = data.get("payout_id")
        if recipient.is_staff or recipient.is_business_admin or recipient.is_superuser:
            return f"/admin/payouts?payout={payout_id}" if payout_id else "/admin/payouts"
        from store.models import Store, StorePayout
        from django.db.models import Q

        payout = StorePayout.objects.filter(
            Q(store__user=recipient) | Q(wallet__user=recipient), pk=payout_id,
        ).first() if payout_id else None
        if payout:
            store_id = payout.store_id or Store.objects.filter(user=recipient).order_by("pk").values_list("pk", flat=True).first()
            store_query = f"&store={store_id}" if store_id else ""
            return f"/merchant/payments?payout={payout.pk}{store_query}"
        return "/merchant/payments"
    if category == "wallet":
        if (recipient.is_superuser or recipient.is_business_admin) and data.get("user_id"):
            return f"/admin/users/{data['user_id']}"
        return "/account/wallet"
    if category == "store":
        store_id = data.get("store_id")
        product_id = data.get("product_id")
        if recipient.is_staff or recipient.is_business_admin or recipient.is_superuser:
            return f"/admin/stores/{store_id}" if store_id else "/admin/stores"
        if product_id and store_id:
            return f"/merchant/products/{product_id}?store={store_id}"
        return f"/merchant?store={store_id}" if store_id else "/merchant"
    if category == "affiliates":
        return "/admin/affiliates" if recipient.is_staff or recipient.is_business_admin or recipient.is_superuser else "/account/affiliates"
    if category == "account":
        return "/account/profile"
    return "/notifications"


def notification_payload(notification: Any) -> dict[str, Any]:
    """Resolve old saved inbox links through the current recipient routing policy."""
    data = dict(notification.data or {})
    target = notification.target
    if target is not None:
        model = target._meta.model_name
        if model in {"order", "refund", "store", "storepayout"}:
            key = "payout_id" if model == "storepayout" else f"{model}_id"
            data.setdefault(key, target.pk)
        if model == "refund":
            data.setdefault("order_id", target.order_id)
    if notification.category in {"order", "refund"} and not data.get("store_ids"):
        data["store_ids"] = sorted(store_ids_for(data, target))
    identified = (
        notification.category in {"order", "refund"} and bool(data.get("order_id"))
        or notification.category == "payout" and bool(data.get("payout_id"))
        or notification.category == "store" and bool(data.get("store_id"))
        or notification.category in {"wallet", "account", "affiliates"}
    )
    if identified or not data.get("url"):
        data["url"] = destination_for(notification.recipient, notification.category, data)
    return data
