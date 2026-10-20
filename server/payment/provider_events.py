"""Reconcile signed Stripe adjustments under the order lock, without issuing refunds."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.models import Refund
from notification.views import create_notification
from payment.models import Order, ProviderAdjustment
from store.models import StoreEarningsLedger
from store.services import process_refund_deduction


def resolve_order(data: dict[str, Any]) -> Order | None:
    order_reference = str((data.get("metadata") or {}).get("order_id", ""))
    if order_reference:
        order = Order.objects.filter(orderId=order_reference).first()
        if order:
            return order
    refund_id = str((data.get("metadata") or {}).get("refund_id", ""))
    if refund_id.isdigit():
        local = Refund.objects.select_related("order").filter(pk=refund_id).first()
        if local and local.order_id:
            return local.order
    intent = data.get("payment_intent")
    if isinstance(intent, dict):
        intent = intent.get("id")
    metadata = data.get("metadata") or {}
    key = metadata.get("checkout_key")
    if key:
        try:
            order = Order.objects.filter(checkout_key=UUID(str(key))).first()
        except (ValueError, TypeError):
            order = None
        if order:
            return order
    if intent:
        order = Order.objects.filter(stripe_payment_intent=intent).first()
        if order:
            return order
        # Legacy orders predate the stored PaymentIntent reference.
        import stripe

        stripe.api_key = settings.STRIPE_SECRET
        sessions = stripe.checkout.Session.list(payment_intent=intent, limit=100)
        for session in sessions.get("data", []):
            order = Order.objects.filter(stripe_session_id=session["id"]).first()
            if order:
                Order.objects.filter(pk=order.pk).update(stripe_payment_intent=intent)
                return order
    return None


def adjust_earnings(
    order: Order,
    delta: Decimal,
    allocations: dict[str, str] | None = None,
) -> dict[str, str]:
    """Allocate provider-wide reversals across the remaining store sale amounts."""
    sales = list(StoreEarningsLedger.objects.filter(order=order, entry_type="sale"))
    remaining = []
    for sale in sales:
        refunds = StoreEarningsLedger.objects.filter(
            order=order,
            store=sale.store,
            entry_type="refund",
        ).aggregate(total=Sum("gross_amount"))["total"] or Decimal("0")
        remaining.append((sale, max(Decimal("0"), sale.gross_amount + refunds)))
    total = sum((value for _, value in remaining), Decimal("0"))
    result: dict[str, str] = {}
    if delta > 0:
        remaining_payment = max(Decimal("0"), order.paid_total - order.refunded_total)
        target = (
            min(total, (total * delta / remaining_payment).quantize(Decimal(".01")))
            if remaining_payment
            else Decimal("0")
        )
        from payment.accounting import allocate_amount

        shares = allocate_amount(target, [value for _, value in remaining])
        for (sale, _), share in zip(remaining, shares):
            if share > 0:
                process_refund_deduction(order, share, sale.store)
                result[str(sale.store_id)] = str(share)
    elif delta < 0:
        for sale in sales:
            share = Decimal((allocations or {}).get(str(sale.store_id), "0"))
            if share <= 0:
                continue
            net = (share * sale.net_amount / sale.gross_amount).quantize(Decimal(".01"))
            StoreEarningsLedger.objects.create(
                order=order,
                store=sale.store,
                wallet=sale.wallet,
                entry_type="refund",
                gross_amount=share,
                net_amount=net,
                fee_amount=share - net,
                status="completed",
                description="Provider reversal restored",
            )
            sale.status = (
                "pending"
                if sale.available_at and sale.available_at > timezone.now()
                else "available"
            )
            sale.save(update_fields=["status", "updated"])
    return result


def local_allocations(
    refund: Refund,
    amount: Decimal,
    *,
    cap_remaining: bool = False,
) -> dict[str, str]:
    """Attribute only merchandise earnings, excluding recorded tax/shipping."""
    from payment.accounting import allocate_amount, order_paid_lines

    originals = order_paid_lines(refund.order)
    items = refund.selected_items or originals
    weights: dict[str, Decimal] = {}
    for row in items:
        original = next(
            (
                item
                for item in originals
                if item.get("product") == row.get("product")
                and str(item.get("variant") or "") == str(row.get("variant") or "")
            ),
            None,
        )
        if not original or not original.get("store"):
            continue
        store_id = str(original["store"])
        value = (
            Decimal(str(original.get("net_total", "0")))
            * int(row.get("quantity", 1))
            / max(1, int(original.get("quantity", 1)))
        )
        weights[store_id] = weights.get(store_id, Decimal("0")) + value
    total = sum(weights.values(), Decimal("0"))
    basis = refund.refund_amount or max(
        Decimal("0"), refund.order.paid_total - refund.order.refunded_total
    )
    target = (
        min(total, (total * amount / basis).quantize(Decimal(".01")))
        if basis
        else Decimal("0")
    )
    shares = allocate_amount(target, list(weights.values()))
    result: dict[str, str] = {}
    for store_id, share in zip(weights, shares):
        if cap_remaining:
            ledger = StoreEarningsLedger.objects.filter(
                order=refund.order, store_id=store_id, entry_type__in=["sale", "refund"]
            )
            remaining = ledger.aggregate(total=Sum("gross_amount"))["total"] or Decimal(
                "0"
            )
            share = min(share, max(Decimal("0"), remaining))
        result[store_id] = str(share)
    return result


@transaction.atomic
def reconcile_adjustment(event_type: str, data: dict[str, Any]) -> None:
    order = resolve_order(data)
    if order is None:
        return  # A Stripe account can also contain unrelated payments.
    order = Order.objects.select_for_update().get(pk=order.pk)
    if (
        data.get("currency", "").lower()
        != getattr(settings, "STRIPE_CURRENCY", "usd").lower()
    ):
        raise ValidationError("Payment currency does not match.")
    reference = str(data.get("id") or "")
    if not reference:
        raise ValidationError("Payment adjustment has no reference.")
    amount = Decimal(str(data.get("amount", 0))) / 100
    if amount <= 0 or amount > order.paid_total - order.wallet_paid:
        raise ValidationError("Invalid payment adjustment amount.")
    dispute = event_type.startswith("charge.dispute.")
    state = str(data.get("status") or ("needs_response" if dispute else ""))
    record, _ = ProviderAdjustment.objects.get_or_create(
        reference=reference,
        defaults={"order": order, "kind": "dispute" if dispute else "refund"},
    )
    if record.order_id != order.pk:
        raise ValidationError("Payment adjustment ownership does not match.")
    # Retrieve the current provider state on repeat deliveries to defeat stale events.
    if record.status and record.status != state:
        import stripe

        stripe.api_key = settings.STRIPE_SECRET
        current = (
            stripe.Dispute.retrieve(reference)
            if dispute
            else stripe.Refund.retrieve(reference)
        )
        state = str(current.get("status", state))
    local_refund = Refund.objects.filter(
        order=order, provider_reference=reference
    ).first()
    if (
        local_refund is None
        and str((data.get("metadata") or {}).get("refund_id", "")).isdigit()
    ):
        local_refund = Refund.objects.filter(
            order=order, pk=data["metadata"]["refund_id"]
        ).first()
    if (
        local_refund
        and local_refund.status == Refund.STATUS_APPROVED
        and not record.status
    ):
        record.applied_amount = amount
        record.allocations = local_allocations(local_refund, amount)
    if (
        local_refund
        and state == "succeeded"
        and local_refund.status != Refund.STATUS_APPROVED
    ):
        from payment.services import _process_order_refund

        pending_allocations = local_allocations(
            local_refund, amount, cap_remaining=True
        )
        _process_order_refund(
            local_refund,
            local_refund.processed_by,
            local_refund.processing_reason,
            settled_reference=reference,
        )
        record.applied_amount = amount
        record.allocations = pending_allocations
        order.refresh_from_db()
    target = amount if state == ("lost" if dispute else "succeeded") else Decimal("0")
    delta = target - record.applied_amount
    if delta > order.paid_total - order.refunded_total:
        raise ValidationError("Adjustment exceeds the remaining payment.")
    if delta:
        allocations = adjust_earnings(order, delta, record.allocations)
        if delta > 0:
            record.allocations = allocations
        if not dispute:
            order.card_refunded_total += delta
            order.refunded_total += delta
            if order.refunded_total >= order.paid_total:
                order.status = "refunded"
            elif order.status == "refunded":
                order.status = (
                    "delivered"
                    if order.delivered_at
                    else "shipped"
                    if order.shipped_at
                    else "confirmed"
                )
            if delta > 0:
                from affiliates.services import reverse_referral_reward_for_order

                reverse_referral_reward_for_order(order)
    if local_refund and state in {"failed", "canceled"}:
        local_refund.status = Refund.STATUS_FAILED
        local_refund.failure_reason = (
            "The payment provider could not complete this refund. Contact support."
        )
        local_refund.save(update_fields=["status", "failure_reason", "updated"])
    changed = record.status != state
    record.status, record.amount, record.applied_amount = state, amount, target
    record.save()
    order.payment_disputed = (
        order.provider_adjustments.filter(kind="dispute")
        .exclude(status__in=["won", "lost", "warning_closed"])
        .exists()
    )
    order._notification_managed = True
    order.save(
        update_fields=[
            "status",
            "card_refunded_total",
            "refunded_total",
            "payment_disputed",
            "updated",
        ]
    )
    if changed and not (local_refund and state == "succeeded"):
        from notification.events import operators

        recipients = list(operators(admins_only=True))
        if not dispute and order.user_id:
            recipients.append(order.user)
        for user in {user.pk: user for user in recipients}.values():
            create_notification(
                user,
                "Payment dispute updated" if dispute else "Payment refund updated",
                target=order,
                description=f"Payment provider status: {state.replace('_', ' ')}.",
                data={
                    "event": "payment_dispute_updated"
                    if dispute
                    else "refund_provider_updated",
                    "order_id": order.pk,
                },
                event_key=f"provider:{reference}:{state}",
            )


def reconcile_event(event_type: str, data: dict[str, Any]) -> None:
    if event_type == "charge.refunded":
        refunds = data.get("refunds") or {}
        rows = refunds.get("data", [])
        if refunds.get("has_more") or not rows:
            import stripe

            stripe.api_key = settings.STRIPE_SECRET
            rows = stripe.Refund.list(charge=data["id"], limit=100).auto_paging_iter()
        for refund in rows:
            reconcile_adjustment(
                "refund.updated",
                {
                    **refund,
                    "payment_intent": refund.get("payment_intent")
                    or data.get("payment_intent"),
                },
            )
    else:
        reconcile_adjustment(event_type, data)


def record_local_provider_refund(
    order: Order, reference: str, amount: Decimal, refund: Refund | None
) -> None:
    """Save with local accounting so the later webhook does not deduct twice."""
    attribution = refund or Refund(order=order, selected_items=order.items_snapshot)
    ProviderAdjustment.objects.get_or_create(
        reference=reference,
        defaults={
            "order": order,
            "kind": "refund",
            "status": "succeeded",
            "amount": amount,
            "applied_amount": amount,
            "allocations": local_allocations(attribution, amount, cap_remaining=True),
        },
    )
