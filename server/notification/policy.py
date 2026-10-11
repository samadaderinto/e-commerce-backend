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
            return "/admin/refunds" if category == "refund" else "/admin/orders"
        from payment.models import Order
        if Order.objects.filter(pk=data["order_id"], user=recipient).exists():
            return f"/orders/{data['order_id']}"
        return "/merchant/orders"
    if category == "payout":
        return "/admin/payouts" if recipient.is_staff or recipient.is_business_admin else "/merchant/payments"
    if category == "wallet":
        if (recipient.is_superuser or recipient.is_business_admin) and data.get("user_id"):
            return f"/admin/users/{data['user_id']}"
        return "/account/wallet"
    if category == "store":
        return "/admin/stores" if recipient.is_staff or recipient.is_business_admin else "/merchant"
    if category == "account":
        return "/account/profile"
    return "/notifications"
