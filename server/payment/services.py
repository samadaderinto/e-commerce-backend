from __future__ import annotations

from decimal import Decimal
from datetime import timedelta
import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.models import Refund, UserWalletTransaction
from core.services import credit_user_wallet
from notification.views import create_notification
from payment.models import Order
from payment.refund_messages import REFUND_FAILURE_MESSAGE
from payment.accounting import order_paid_lines
from store.models import Store
from store.services import process_refund_deduction
from utils.functions import send_mail

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
logger = logging.getLogger(__name__)


class RefundProviderError(ValidationError):
    default_code = "refund_provider_failed"


def validate_return_window(order: Order, items: list[dict[str, Any]]) -> None:
    """A physical line's return clock starts at its recorded store delivery."""
    days = getattr(settings, 'REFUND_WINDOW_DAYS', 7)
    deliveries = dict(order.fulfillments.values_list('store_id', 'delivered_at'))
    for item in items:
        if item.get('is_digital'):
            continue
        delivered = deliveries.get(item.get('store')) or order.delivered_at
        if delivered and timezone.now() > delivered + timedelta(days=days):
            raise ValidationError({'detail': f'The {days}-day return window for a selected item has expired.'})


def is_digital_only_order(order: Order) -> bool:
    """Return True if an order contains strictly digital products and no physical delivery."""
    if order.items_snapshot:
        return all(bool(row.get("is_digital", False)) for row in order.items_snapshot)
    if order.cart_id and order.cart.cart_items.exists():
        return not order.cart.cart_items.filter(product__is_digital=False).exists()
    if order.delivery and getattr(order.delivery, "method", "") == "digital":
        return True
    return False


def call_stripe_refund(
    order: Order,
    refund: Refund | None = None,
    reason: str = "requested_by_customer",
    amount: Decimal | None = None,
) -> str:
    stripe_key = getattr(settings, "STRIPE_SECRET", "")
    idempotency_key = f"refund_{refund.pk if refund else 'order'}_{order.orderId}"

    if stripe is None or not stripe_key:
        raise ValidationError(
            {"detail": "Payment provider refunds are not configured."}
        )

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
        raise ValidationError(
            {"detail": "This payment has no refundable provider reference."}
        )

    refund_amount = Decimal(str(amount if amount is not None else order.paid_total))
    if not refund_amount.is_finite() or refund_amount <= 0:
        raise ValidationError(
            {"detail": "A provider refund must have a positive amount."}
        )
    refund_kwargs["amount"] = int(refund_amount * 100)

    result = stripe.Refund.create(**refund_kwargs)
    return getattr(result, "id", str(result))


def split_wallet_paid(order: Order) -> Decimal:
    if order.payment_type != "split_tender":
        return Decimal("0")
    if order.wallet_paid > 0:
        return order.wallet_paid
    from payment.models import CheckoutAttempt

    attempt = CheckoutAttempt.objects.filter(session_id=order.stripe_session_id).first()
    if attempt and attempt.wallet_amount > 0:
        return attempt.wallet_amount
    from django.db.models import Sum

    return UserWalletTransaction.objects.filter(
        wallet__user=order.user,
        transaction_type=UserWalletTransaction.DEBIT,
        reference=order.orderId,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")


def refund_parts(order: Order, amount: Decimal) -> tuple[Decimal, Decimal]:
    """Consume remaining original tender amounts, including cent rounding."""
    wallet_remaining = max(
        Decimal("0"), order.wallet_paid - order.wallet_refunded_total
    )
    card_remaining = max(
        Decimal("0"), order.paid_total - order.wallet_paid - order.card_refunded_total
    )
    remaining = wallet_remaining + card_remaining
    if amount <= 0 or amount > remaining:
        raise ValidationError(
            {"detail": "Refund exceeds the remaining settled payment."}
        )
    if amount == remaining:
        return wallet_remaining, card_remaining
    wallet_part = min(
        wallet_remaining,
        (amount * order.wallet_paid / order.paid_total).quantize(Decimal(".01")),
    )
    card_part = amount - wallet_part
    if card_part > card_remaining:
        card_part = card_remaining
        wallet_part = amount - card_part
    return wallet_part, card_part


def remaining_inventory(order: Order) -> list[dict[str, Any]]:
    quantities: dict[tuple[Any, str], int] = {}
    for prior in Refund.objects.filter(order=order, status=Refund.STATUS_APPROVED):
        for row in prior.selected_items or order.items_snapshot or []:
            key = (row.get("product"), str(row.get("variant") or ""))
            quantities[key] = quantities.get(key, 0) + int(row.get("quantity", 1))
    rows: list[dict[str, Any]] = []
    for row in order_paid_lines(order):
        key = (row.get("product"), str(row.get("variant") or ""))
        quantity = max(0, int(row.get("quantity", 1)) - quantities.get(key, 0))
        if quantity:
            rows.append({**row, "quantity": quantity})
    return rows


def process_order_refund(refund: Refund, actor: Any, reason: str = "") -> Refund:
    try:
        return _process_order_refund(refund, actor, reason)
    except RefundProviderError:
        with transaction.atomic():
            # Follow the order/refund lock ordering used by approval and decline.
            Order.objects.select_for_update().filter(pk=refund.order_id).first()
            current = Refund.objects.select_for_update().get(pk=refund.pk)
            if current.status not in (Refund.STATUS_PENDING, Refund.STATUS_FAILED):
                raise
            Refund.objects.filter(pk=refund.pk).update(
                status=Refund.STATUS_FAILED,
                failure_reason=REFUND_FAILURE_MESSAGE,
                processed_by=actor,
                processed_at=timezone.now(),
                processing_reason=reason,
                updated=timezone.now(),
            )
            refund.refresh_from_db()
            if refund.order_id:
                with transaction.atomic():
                    from notification.domain import refund_notice
                    refund_notice(refund, actor, refund.selected_items or refund.order.items_snapshot, decision="failed")
                    if refund.order.user_id:
                        create_notification(
                            refund.order.user, f"Refund delayed for Order #{refund.order.orderId}", target=refund,
                            description="The payment provider could not complete your refund. Support will review it.",
                            data={"event": "refund_failed", "order_id": refund.order_id, "refund_id": refund.pk},
                        )
        raise


@transaction.atomic
def _process_order_refund(refund: Refund, actor: Any, reason: str = "") -> Refund:
    order = Order.objects.select_for_update().filter(pk=refund.order_id).first()
    refund = Refund.objects.select_for_update().get(pk=refund.pk)
    if not order:
        raise ValidationError({"detail": "Refund has no associated order."})

    if refund.status == Refund.STATUS_APPROVED:
        raise ValidationError({"detail": "This refund was already approved."})
    if refund.status == Refund.STATUS_DECLINED:
        raise ValidationError({"detail": "This refund was already declined."})

    if (
        order.status in {"cancelled", "refunded"}
        or not order.ordered
        or order.paid_total <= 0
    ):
        raise ValidationError(
            {"detail": "This order has no remaining refundable payment."}
        )
    available_items = remaining_inventory(order)
    selected_items: list[dict[str, Any]] = []
    if refund.selected_items:
        amount = Decimal("0")
        seen: set[tuple[Any, str]] = set()
        for selected in refund.selected_items:
            key = (selected.get("product"), str(selected.get("variant") or ""))
            row = next(
                (
                    item
                    for item in available_items
                    if (item.get("product"), str(item.get("variant") or "")) == key
                ),
                None,
            )
            quantity = int(selected.get("quantity", 1))
            if (
                key in seen
                or row is None
                or quantity <= 0
                or quantity > row["quantity"]
                or row.get("is_digital")
            ):
                raise ValidationError(
                    {"detail": "Selected items are unavailable for refund."}
                )
            original = next(
                item
                for item in order_paid_lines(order)
                if (item.get("product"), str(item.get("variant") or "")) == key
            )
            amount += (
                Decimal(original["line_total"]) * quantity / int(original["quantity"])
            ).quantize(Decimal(".01"))
            selected_items.append({**original, "quantity": quantity})
            seen.add(key)
    else:
        amount = refund.refund_amount or order.paid_total - order.refunded_total
        if amount != order.paid_total - order.refunded_total:
            raise ValidationError(
                {"detail": "Partial refunds require selected order items."}
            )
        selected_items = available_items
    wallet_part, card_part = refund_parts(order, amount)
    provider_reference = ""
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
                        idempotency_key=f"refund-{refund.pk}-wallet",
                    )
                    provider_reference = f"WALLET-TX-{tx.pk}"
                else:
                    provider_reference = f"WALLET-REF-{order.orderId}"
            elif order.payment_type == "split_tender":
                provider_reference = (
                    call_stripe_refund(order, refund, amount=card_part)
                    if card_part > 0
                    else "WALLET-ONLY"
                )
                if wallet_part > 0 and order.user:
                    credit_user_wallet(
                        order.user,
                        wallet_part,
                        f"Split-tender refund for #{order.orderId}",
                        reference=f"SPLIT-REF-{order.orderId}",
                        idempotency_key=f"refund-{refund.pk}-wallet",
                    )
            elif (
                order.payment_type in ("stripe_wallet", "card")
                or order.stripe_session_id
            ):
                provider_reference = call_stripe_refund(order, refund, amount=amount)
            elif order.payment_type == "cash_on_delivery":
                provider_reference = f"COD-REVERSAL-{order.orderId}"
            else:
                provider_reference = (
                    f"ORIGINAL-PAYMENT-{order.payment_type}-{order.orderId}"
                )
        else:
            if order.user:
                tx = credit_user_wallet(
                    user=order.user,
                    amount=amount,
                    description=f"Refund store credit for Order #{order.orderId}",
                    source=UserWalletTransaction.SOURCE_REFUND,
                    reference=f"STORE-CREDIT-{order.orderId}",
                    idempotency_key=f"refund-{refund.pk}-wallet",
                )
                provider_reference = f"WALLET-TX-{tx.pk}"
            else:
                provider_reference = f"STORE-CREDIT-{order.orderId}"
    except Exception as exc:
        refund.status = Refund.STATUS_FAILED
        logger.exception('Refund provider operation failed for refund %s', refund.pk)
        refund.failure_reason = REFUND_FAILURE_MESSAGE
        refund.save(update_fields=["status", "failure_reason", "updated"])
        raise RefundProviderError({'detail': 'Payment provider refund failed. Please try again or contact support.'}) from exc

    with transaction.atomic():
        refund = Refund.objects.select_for_update().get(pk=refund.pk)
        order = Order.objects.select_for_update().get(pk=order.pk)

        refund.refund_amount = amount
        refund.selected_items = selected_items
        refund.accepted = True
        refund.status = Refund.STATUS_APPROVED
        refund.provider_reference = provider_reference
        refund.failure_reason = ""
        refund.processed_by = actor
        refund.processed_at = timezone.now()
        refund.processing_reason = reason
        refund.save(
            update_fields=[
                "refund_amount",
                "selected_items",
                "accepted",
                "status",
                "provider_reference",
                "failure_reason",
                "processed_by",
                "processed_at",
                "processing_reason",
                "updated",
            ]
        )

        order.refunded_total += amount
        order.wallet_refunded_total += wallet_part
        order.card_refunded_total += card_part
        if order.refunded_total >= order.paid_total:
            order.status = "refunded"
        order.refunded_at = timezone.now()
        events = list(order.tracking_events or [])
        events.append(
            {
                "status": "refunded",
                "description": f"Refund approved by {getattr(actor, 'email', 'staff')} ({refund.get_refund_type_display()}). Ref: {provider_reference}",
                "timestamp": timezone.now().isoformat(),
                "actor_id": getattr(actor, "pk", None),
            }
        )
        order.tracking_events = events
        order.save(
            update_fields=[
                "status",
                "tracking_events",
                "refunded_at",
                "refunded_total",
                "wallet_refunded_total",
                "card_refunded_total",
                "updated",
            ]
        )

        # Reverse merchant earnings and adjust merchant wallet
        if selected_items:
            from store.models import Store

            shares: dict[int, Decimal] = {}
            paid_lines = order_paid_lines(order)
            for selected in refund.selected_items:
                snapshot = next(
                    (
                        row
                        for row in paid_lines
                        if row.get("product") == selected.get("product")
                        and row.get("variant", "") == selected.get("variant", "")
                    ),
                    None,
                )
                if snapshot and snapshot.get("store"):
                    store_id = int(snapshot["store"])
                    share = (
                        Decimal(snapshot["net_total"])
                        * int(selected.get("quantity", 1))
                        / int(snapshot.get("quantity", 1))
                    ).quantize(Decimal(".01"))
                    shares[store_id] = shares.get(store_id, Decimal("0")) + share
            for store_id, share in shares.items():
                store_obj = Store.objects.filter(pk=store_id).first()
                process_refund_deduction(order, refund_amount=share, store=store_obj)
        else:
            process_refund_deduction(order)
        from product.models import Product
        from store.views import invalidate_catalog

        for row in refund.selected_items:
            product = (
                Product.objects.select_for_update()
                .filter(pk=row.get("product"), is_digital=False)
                .first()
            )
            if product:
                quantity = int(row.get("quantity", 1))
                product.available += quantity
                from product.policies import restock_variant

                restock_variant(product, str(row.get("variant") or ""), quantity)
                product.sales = max(0, product.sales - quantity)
                product.save(
                    update_fields=["available", "variants", "sales", "updated"]
                )
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
                data={
                    "order_id": order.pk,
                    "refund_id": refund.pk,
                    "event": "refund_approved",
                    "email": False,
                },
            )

        recipient_email = order.buyer_email or (order.user.email if order.user else None)
        if recipient_email:
            send_mail(
                "refund-response",
                recipient_email,
                {
                    "firstname": (order.user.first_name if order.user else ""),
                    "orderId": order.orderId,
                    "status": "Approved",
                    "refund_amount": str(amount),
                    "refund_destination": (
                        "ProAce Wallet"
                        if refund.refund_type == Refund.REFUND_TYPE_STORE_CREDIT
                        else "Original Payment Method"
                    ),
                    "message": (
                        "Store credit has been added to your ProAce Wallet."
                        if refund.refund_type == Refund.REFUND_TYPE_STORE_CREDIT
                        else "Payment has been returned to your original payment method."
                    ),
                    "subject": f"Refund Update for Order #{order.orderId}",
                },
            )

    from notification.domain import refund_notice
    refund_notice(refund, actor, refund.selected_items or order.items_snapshot, decision="approved")
    return refund


def decline_order_refund(refund: Refund, actor: Any, reason: str = "") -> Refund:
    if refund.status not in (Refund.STATUS_PENDING, Refund.STATUS_FAILED):
        raise ValidationError({"detail": f"This refund was already {refund.status}."})

    with transaction.atomic():
        if refund.order_id:
            Order.objects.select_for_update().get(pk=refund.order_id)
        refund = Refund.objects.select_for_update().get(pk=refund.pk)
        if refund.status not in (Refund.STATUS_PENDING, Refund.STATUS_FAILED):
            raise ValidationError(
                {"detail": f"This refund was already {refund.status}."}
            )
        refund.accepted = False
        refund.status = Refund.STATUS_DECLINED
        refund.failure_reason = reason or "Refund request declined by moderation."
        refund.processing_reason = reason
        refund.processed_by = actor
        refund.processed_at = timezone.now()
        refund.save(
            update_fields=[
                "accepted",
                "status",
                "failure_reason",
                "processed_by",
                "processed_at",
                "processing_reason",
                "updated",
            ]
        )

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
                    data={
                        "order_id": order.pk,
                        "refund_id": refund.pk,
                        "event": "refund_declined",
                        "email": False,
                    },
                )

            recipient_email = (
                order.buyer_email or (order.user.email if order.user else None)
                if refund.order
                else refund.email
            )
            if recipient_email:
                first_name = (
                    order.user.first_name
                    if refund.order and order.user
                    else ""
                )
                order_id = order.orderId if refund.order else ""
                send_mail(
                    "refund-response",
                    recipient_email,
                    {
                        "firstname": first_name,
                        "orderId": order_id,
                        "status": "Declined",
                        "refund_amount": str(refund.refund_amount),
                        "refund_destination": "",
                        "message": f"Your refund request was declined. Reason: {refund.failure_reason}",
                        "subject": f"Refund Update for Order #{order_id}",
                    },
                )

        if refund.order_id:
            from notification.domain import refund_notice
            refund_notice(refund, actor, refund.selected_items or order.items_snapshot, decision="declined")
    return refund


def restore_order_inventory(
    order: Order, items: list[dict[str, Any]] | None = None
) -> None:
    from product.models import Product
    from store.views import invalidate_catalog

    snapshots = items if items is not None else order.items_snapshot or []
    if snapshots:
        for item in snapshots:
            product_id = item.get("product")
            qty = int(item.get("quantity", 1))
            is_digital = item.get("is_digital", False)
            if product_id:
                product = (
                    Product.objects.select_for_update().filter(pk=product_id).first()
                )
                if product:
                    if not is_digital and not product.is_digital:
                        product.available += qty
                        from product.policies import restock_variant

                        restock_variant(product, str(item.get("variant") or ""), qty)
                    product.sales = max(0, product.sales - qty)
                    product.save(
                        update_fields=["available", "variants", "sales", "updated"]
                    )
                    transaction.on_commit(lambda p=product: invalidate_catalog(p))
    elif order.cart and items is None:
        for item in order.cart.cart_items.select_related("product").all():
            product = (
                Product.objects.select_for_update().filter(pk=item.product_id).first()
            )
            if product:
                if not product.is_digital:
                    product.available += item.quantity
                    from product.policies import restock_variant

                    restock_variant(product, item.variant, item.quantity)
                product.sales = max(0, product.sales - item.quantity)
                product.save(
                    update_fields=["available", "variants", "sales", "updated"]
                )
                transaction.on_commit(lambda p=product: invalidate_catalog(p))


@transaction.atomic
def execute_order_status_transition(
    order: Order,
    next_status: str,
    actor: Any,
    reason: str,
) -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
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
        raise ValidationError(
            {
                "detail": f"Cannot transition order from '{previous}' to '{next_status}'. Allowed transitions: {sorted(list(allowed_targets))}"
            }
        )

    is_digital = is_digital_only_order(order)
    if next_status == "cancelled":
        if is_digital:
            raise ValidationError(
                {
                    "detail": "Digital orders are fulfilled immediately and cannot be cancelled through the order status workflow."
                }
            )
        from payment.fulfillment import ensure_fulfillments

        ensure_fulfillments(order)
        if previous in {"shipped", "delivered", "picked up"} or order.fulfillments.filter(
            status__in=["shipped", "delivered", "picked up"]
        ).exists():
            raise ValidationError(
                {
                    "detail": "A physically fulfilled order cannot be cancelled. Use the refund workflow instead."
                }
            )

    if is_digital:
        if next_status in ("shipped", "picked up"):
            raise ValidationError(
                {
                    "detail": "Digital orders have instant electronic fulfillment and cannot be transitioned to physical delivery statuses."
                }
            )
        if previous == "delivered":
            raise ValidationError(
                {
                    "detail": "Digital orders are fulfilled instantly upon purchase and cannot be reverted from delivered."
                }
            )

    inventory = remaining_inventory(order)
    cancel_wallet_refund = Decimal("0.00")
    cancel_card_refund = Decimal("0.00")
    cancel_total_refund = Decimal("0.00")
    if next_status == "cancelled":
        remaining = order.paid_total - order.refunded_total
        if remaining > 0:
            wallet_part, card_part = refund_parts(order, remaining)
            cancel_wallet_refund = wallet_part
            cancel_card_refund = card_part
            cancel_total_refund = remaining
            try:
                if card_part > 0:
                    call_stripe_refund(
                        order, reason="order_cancelled", amount=card_part
                    )
                if wallet_part > 0 and order.user:
                    credit_user_wallet(
                        order.user,
                        wallet_part,
                        f"Refund for cancelled Order #{order.orderId}",
                        source=UserWalletTransaction.SOURCE_REFUND,
                        reference=f"CANCEL-{order.orderId}",
                        idempotency_key=f"cancel-{order.pk}-wallet",
                    )
            except Exception as exc:
                logger.exception('Cancellation payment refund failed for order %s', order.pk)
                raise ValidationError(
                    {
                        "detail": "Cannot cancel order: payment refund failed. Please try again or contact support."
                    }
                ) from exc
            order.refunded_total += remaining
            order.wallet_refunded_total += wallet_part
            order.card_refunded_total += card_part
            order.save(
                update_fields=[
                    "refunded_total",
                    "wallet_refunded_total",
                    "card_refunded_total",
                    "updated",
                ]
            )
        Refund.objects.filter(
            order=order, status__in=[Refund.STATUS_PENDING, Refund.STATUS_FAILED]
        ).update(
            status=Refund.STATUS_DECLINED,
            failure_reason="Order cancelled.",
            processing_reason=reason,
            processed_by=actor,
            processed_at=timezone.now(),
            updated=timezone.now(),
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
            if not is_digital and not order.shipped_at:
                order.shipped_at = now
            elif is_digital:
                order.shipped_at = None
            if not order.delivered_at:
                order.delivered_at = now
        elif next_status == "picked up":
            if not order.delivered_at:
                order.delivered_at = now
        elif next_status in ("pending", "confirmed"):
            order.shipped_at = None
            order.delivered_at = None

        if next_status in {"pending", "confirmed", "shipped", "delivered", "picked up"}:
            order.fulfillments.update(
                status="confirmed" if next_status == "pending" else next_status,
                shipped_at=order.shipped_at,
                delivered_at=order.delivered_at,
                updated=now,
            )
        if next_status in {"confirmed", "shipped", "delivered", "picked up"}:
            from affiliates.services import process_referral_reward_for_order
            process_referral_reward_for_order(order)
        if next_status == "cancelled":
            restore_order_inventory(order, inventory if order.items_snapshot else None)
            process_refund_deduction(order)

        events = list(order.tracking_events or [])
        events.append(
            {
                "status": next_status,
                "description": f"Back-office status transition by {getattr(actor, 'email', 'staff')}: {reason}",
                "timestamp": now.isoformat(),
                "previous_status": previous,
                "actor_id": getattr(actor, "pk", None),
            }
        )
        order.tracking_events = events
        order.save(
            update_fields=[
                "status",
                "shipped_at",
                "delivered_at",
                "tracking_events",
                "updated",
            ]
        )

        if order.user:
            create_notification(
                recipient=order.user,
                actor=actor,
                target=order,
                verb=f"Order #{order.orderId} updated to {next_status}",
                description=f"Your order #{order.orderId} status was updated to {next_status}. Reason: {reason}",
                data={
                    "order_id": order.pk,
                    "status": next_status,
                    "event": "order_status_override",
                    "email": next_status not in {"cancelled", "shipped", "delivered", "picked up", "confirmed"},
                },
            )

        if next_status == "cancelled":
            store_ids = set()
            for row in order.items_snapshot or []:
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
                        data={
                            "order_id": order.pk,
                            "status": "cancelled",
                            "store_id": sid,
                            "event": "order_cancelled",
                        },
                    )

        recipient_email = order.buyer_email or (order.user.email if order.user else None)
        if recipient_email:
            firstname = (order.user.first_name if order.user else "")
            if next_status == "cancelled":
                send_mail(
                    "order-cancelled",
                    recipient_email,
                    {
                        "firstname": firstname,
                        "orderId": order.orderId,
                        "refund_amount": str(cancel_total_refund),
                        "wallet_refund": str(cancel_wallet_refund),
                        "card_refund": str(cancel_card_refund),
                        "reason": reason,
                        "subject": f"Order #{order.orderId} Cancelled",
                    },
                )
            elif next_status == "shipped":
                send_mail(
                    "order-shipped",
                    recipient_email,
                    {
                        "firstname": firstname,
                        "orderId": order.orderId,
                        "carrier": order.carrier,
                        "tracking_number": order.tracking_number or "",
                        "tracking_url": order.tracking_url or "",
                        "subject": f"Order #{order.orderId} Has Shipped",
                    },
                )
            elif next_status == "delivered":
                send_mail(
                    "delivery-confirmation",
                    recipient_email,
                    {
                        "firstname": firstname,
                        "orderId": order.orderId,
                        "carrier": "" if is_digital else order.carrier,
                        "tracking_number": "" if is_digital else (order.tracking_number or ""),
                        "subject": f"Order #{order.orderId} Delivered",
                    },
                )
            elif next_status == "picked up":
                send_mail(
                    "order-picked-up",
                    recipient_email,
                    {
                        "firstname": firstname,
                        "orderId": order.orderId,
                        "subject": f"Order #{order.orderId} Picked Up",
                    },
                )
            elif next_status == "confirmed":
                send_mail(
                    "order-confirm",
                    recipient_email,
                    {
                        "firstname": firstname,
                        "orderId": order.orderId,
                        "subject": f"Order #{order.orderId} Confirmed",
                    },
                )

    return order
