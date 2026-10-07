from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.models import Refund, UserWalletTransaction
from core.services import credit_user_wallet
from notification.views import create_notification
from payment.models import Order
from store.models import Store
from store.services import process_refund_deduction

try:
    import stripe
except ImportError:
    stripe = None


ALLOWED_ORDER_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"pending", "shipped", "picked up", "cancelled"},
    "shipped": {"confirmed", "delivered", "cancelled"},
    "delivered": {"shipped"},
    "picked up": {"confirmed"},
    "cancelled": set(),
    "refunded": set(),
}


def call_stripe_refund(order: Order, refund: Refund | None = None, reason: str = "requested_by_customer", amount: Decimal | None = None) -> str:
    stripe_key = getattr(settings, "STRIPE_SECRET", "")
    idempotency_key = f"refund_{refund.pk if refund else 'order'}_{order.orderId}"

    if stripe is None or not stripe_key:
        return f"STRIPE-MOCK-{order.orderId}"

    stripe.api_key = stripe_key
    session_id = order.stripe_session_id
    payment_intent_id = None
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            payment_intent_id = session.get("payment_intent")
        except Exception:
            pass

    refund_kwargs: dict[str, Any] = {
        "reason": "requested_by_customer",
        "metadata": {
            "order_id": order.orderId,
            "refund_id": str(refund.pk) if refund else "",
        },
        "idempotency_key": idempotency_key,
    }
    if payment_intent_id:
        refund_kwargs["payment_intent"] = payment_intent_id
    elif getattr(order, "stripe_charge_id", None):
        refund_kwargs["charge"] = order.stripe_charge_id
    elif session_id and not session_id.startswith("cs_"):
        refund_kwargs["payment_intent"] = session_id
    else:
        return f"STRIPE-UNLINKED-{order.orderId}"

    try:
        cents = int(Decimal(str(amount if amount is not None else order.total)) * 100)
        if cents > 0:
            refund_kwargs["amount"] = cents
    except Exception:
        pass

    result = stripe.Refund.create(**refund_kwargs)
    return getattr(result, "id", str(result))


def process_order_refund(refund: Refund, actor: Any, reason: str = '') -> Refund:
    order = refund.order
    if not order:
        raise ValidationError({"detail": "Refund has no associated order."})

    if refund.status == Refund.STATUS_APPROVED:
        raise ValidationError({"detail": "This refund was already approved."})
    if refund.status == Refund.STATUS_DECLINED:
        raise ValidationError({"detail": "This refund was already declined."})

    provider_reference = ""
    amount = refund.refund_amount or order.total
    try:
        if refund.refund_type == Refund.REFUND_TYPE_ORIGINAL_PAYMENT:
            if order.payment_type in ("user_wallet", "wallet"):
                if order.user:
                    tx = credit_user_wallet(
                        user=order.user,
                        amount=amount,
                        description=f"Refund to original payment (ProAce Wallet) for Order #{order.orderId}",
                        source=UserWalletTransaction.SOURCE_REFUND,
                        reference=f"REF-{order.orderId}",
                    )
                    provider_reference = f"WALLET-TX-{tx.pk}"
                else:
                    provider_reference = f"WALLET-REF-{order.orderId}"
            elif order.payment_type in ("stripe_wallet", "card") or order.stripe_session_id:
                provider_reference = call_stripe_refund(order, refund, amount=amount)
            elif order.payment_type == "cash_on_delivery":
                provider_reference = f"COD-REVERSAL-{order.orderId}"
            else:
                provider_reference = f"ORIGINAL-PAYMENT-{order.payment_type}-{order.orderId}"
        else:
            if order.user:
                tx = credit_user_wallet(
                    user=order.user,
                    amount=amount,
                    description=f"Refund store credit for Order #{order.orderId}",
                    source=UserWalletTransaction.SOURCE_REFUND,
                    reference=f"STORE-CREDIT-{order.orderId}",
                )
                provider_reference = f"WALLET-TX-{tx.pk}"
            else:
                provider_reference = f"STORE-CREDIT-{order.orderId}"
    except Exception as exc:
        refund.status = Refund.STATUS_FAILED
        refund.failure_reason = str(exc)
        refund.save(update_fields=["status", "failure_reason", "updated"])
        raise ValidationError({"detail": f"Payment provider refund failed: {str(exc)}"})

    with transaction.atomic():
        refund = Refund.objects.select_for_update().get(pk=refund.pk)
        order = Order.objects.select_for_update().get(pk=order.pk)

        refund.accepted = True
        refund.status = Refund.STATUS_APPROVED
        refund.provider_reference = provider_reference
        refund.failure_reason = ""
        refund.processed_by = actor
        refund.processed_at = timezone.now()
        refund.processing_reason = reason
        refund.save(update_fields=["accepted", "status", "provider_reference", "failure_reason", "processed_by", "processed_at", "processing_reason", "updated"])

        refundable_ids = {row.get('product') for row in (order.items_snapshot or []) if not row.get('is_digital')}
        approved_ids = set()
        for prior in Refund.objects.filter(order=order, status=Refund.STATUS_APPROVED):
            approved_ids.update(row.get('product') for row in prior.selected_items)
        approved_ids.update(row.get('product') for row in refund.selected_items)
        is_fully_refunded = (
            not refund.selected_items
            or not refundable_ids
            or refundable_ids.issubset(approved_ids)
            or (refund.refund_amount and refund.refund_amount >= order.total)
        )
        if is_fully_refunded:
            order.status = "refunded"
        events = list(order.tracking_events or [])
        events.append({
            "status": "refunded",
            "description": f"Refund approved by {getattr(actor, 'email', 'staff')} ({refund.get_refund_type_display()}). Ref: {provider_reference}",
            "timestamp": timezone.now().isoformat(),
            "actor_id": getattr(actor, "pk", None),
        })
        order.tracking_events = events
        order.save(update_fields=["status", "tracking_events", "updated"])

        # Reverse merchant earnings and adjust merchant wallet
        process_refund_deduction(order, refund_amount=amount)
        from product.models import Product
        from store.views import invalidate_catalog
        for row in refund.selected_items:
            product = Product.objects.select_for_update().filter(pk=row.get('product'), is_digital=False).first()
            if product:
                quantity = int(row.get('quantity', 1))
                product.available += quantity
                product.sales = max(0, product.sales - quantity)
                product.save(update_fields=['available', 'sales', 'updated'])
                transaction.on_commit(lambda p=product: invalidate_catalog(p))

        if order.user:
            create_notification(
                recipient=order.user,
                actor=actor,
                target=order,
                verb=f"Refund Approved for Order #{order.orderId}",
                description=(
                    f"Your refund request for Order #{order.orderId} of ${amount} has been approved."
                    + (
                        " Store credit has been added to your ProAce Wallet."
                        if refund.refund_type == Refund.REFUND_TYPE_STORE_CREDIT
                        else " Payment has been returned to your original payment method."
                    )
                ),
                data={"order_id": order.pk, "refund_id": refund.pk, "event": "refund_approved"},
            )

    return refund


def decline_order_refund(refund: Refund, actor: Any, reason: str = "") -> Refund:
    if refund.status not in (Refund.STATUS_PENDING, Refund.STATUS_FAILED):
        raise ValidationError({"detail": f"This refund was already {refund.status}."})

    with transaction.atomic():
        refund = Refund.objects.select_for_update().get(pk=refund.pk)
        refund.accepted = False
        refund.status = Refund.STATUS_DECLINED
        refund.failure_reason = reason or "Refund request declined by moderation."
        refund.processing_reason = reason
        refund.processed_by = actor
        refund.processed_at = timezone.now()
        refund.save(update_fields=["accepted", "status", "failure_reason", "processed_by", "processed_at", "processing_reason", "updated"])

        if refund.order:
            order = Order.objects.select_for_update().get(pk=refund.order.pk)
            if order.status == "refund_requested":
                order.status = "confirmed"
                order.save(update_fields=["status", "updated"])

            if order.user:
                create_notification(
                    recipient=order.user,
                    actor=actor,
                    target=order,
                    verb=f"Refund Request Update for Order #{order.orderId}",
                    description=f"Your refund request for Order #{order.orderId} was declined. Reason: {refund.failure_reason}",
                    data={"order_id": order.pk, "refund_id": refund.pk, "event": "refund_declined"},
                )

    return refund


def restore_order_inventory(order: Order) -> None:
    from product.models import Product
    from store.views import invalidate_catalog

    snapshots = order.items_snapshot or []
    if snapshots:
        for item in snapshots:
            product_id = item.get("product")
            qty = int(item.get("quantity", 1))
            is_digital = item.get("is_digital", False)
            if product_id:
                product = Product.objects.select_for_update().filter(pk=product_id).first()
                if product:
                    if not is_digital and not product.is_digital:
                        product.available += qty
                    product.sales = max(0, product.sales - qty)
                    product.save(update_fields=["available", "sales", "updated"])
                    transaction.on_commit(lambda p=product: invalidate_catalog(p))
    elif order.cart:
        for item in order.cart.cart_items.select_related("product").all():
            product = Product.objects.select_for_update().filter(pk=item.product_id).first()
            if product:
                if not product.is_digital:
                    product.available += item.quantity
                product.sales = max(0, product.sales - item.quantity)
                product.save(update_fields=["available", "sales", "updated"])
                transaction.on_commit(lambda p=product: invalidate_catalog(p))


def execute_order_status_transition(
    order: Order,
    next_status: str,
    actor: Any,
    reason: str,
) -> Order:
    if next_status == "refunded":
        raise ValidationError({"detail": "Use the refund workflow to refund an order."})

    previous = order.status
    if previous == "refunded":
        raise ValidationError({"detail": "Refunded orders must remain refunded."})
    if previous == "cancelled":
        raise ValidationError({"detail": "Cancelled orders cannot be modified."})
    if previous == next_status:
        raise ValidationError({"detail": f"Order is already {next_status}."})

    allowed_targets = ALLOWED_ORDER_TRANSITIONS.get(previous, set())
    if next_status not in allowed_targets:
        raise ValidationError({
            "detail": f"Cannot transition order from '{previous}' to '{next_status}'. Allowed transitions: {sorted(list(allowed_targets))}"
        })

    # If cancelling, perform cancellation payment reversal first if external
    if next_status == "cancelled" and order.ordered:
        if order.payment_type in ("stripe_wallet", "card") or order.stripe_session_id:
            try:
                call_stripe_refund(order, reason="order_cancelled_by_staff")
            except Exception as exc:
                raise ValidationError({"detail": f"Cannot cancel order: payment refund failed: {str(exc)}"})
        elif order.payment_type == "user_wallet" and order.user:
            credit_user_wallet(
                user=order.user,
                amount=order.total,
                description=f"Refund for cancelled Order #{order.orderId}",
                source=UserWalletTransaction.SOURCE_REFUND,
                reference=f"CANCEL-{order.orderId}",
            )

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        order.status = next_status

        now = timezone.now()
        if next_status == "shipped":
            if not order.shipped_at:
                order.shipped_at = now
            order.delivered_at = None
        elif next_status == "delivered":
            if not order.shipped_at:
                order.shipped_at = now
            if not order.delivered_at:
                order.delivered_at = now
        elif next_status == "picked up":
            if not order.delivered_at:
                order.delivered_at = now
        elif next_status in ("pending", "confirmed"):
            order.shipped_at = None
            order.delivered_at = None

        if next_status == "cancelled":
            restore_order_inventory(order)
            process_refund_deduction(order)

        events = list(order.tracking_events or [])
        events.append({
            "status": next_status,
            "description": f"Back-office status transition by {getattr(actor, 'email', 'staff')}: {reason}",
            "timestamp": now.isoformat(),
            "previous_status": previous,
            "actor_id": getattr(actor, "pk", None),
        })
        order.tracking_events = events
        order.save(update_fields=["status", "shipped_at", "delivered_at", "tracking_events", "updated"])

        if order.user:
            create_notification(
                recipient=order.user,
                actor=actor,
                target=order,
                verb=f"Order #{order.orderId} updated to {next_status}",
                description=f"Your order #{order.orderId} status was updated to {next_status}. Reason: {reason}",
                data={"order_id": order.pk, "status": next_status, "event": "order_status_override"},
            )

        if next_status == "cancelled":
            store_ids = set()
            for row in (order.items_snapshot or []):
                if row.get("store"):
                    store_ids.add(row["store"])
            for sid in store_ids:
                store = Store.objects.filter(pk=sid).first()
                if store and store.user:
                    create_notification(
                        recipient=store.user,
                        actor=actor,
                        target=order,
                        verb=f"Order #{order.orderId} was cancelled",
                        description=f"Order #{order.orderId} was cancelled by support. Restored stock and reversed earnings.",
                        data={"order_id": order.pk, "status": "cancelled", "store_id": sid, "event": "order_cancelled"},
                    )

    return order
