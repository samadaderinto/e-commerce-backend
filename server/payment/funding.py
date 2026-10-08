"""Serialized deposit allowance, unique funding receipts, and Stripe recovery."""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import stripe
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.models import User, UserWalletTransaction
from core.services import credit_user_wallet
from payment.models import WalletFundingAttempt

MAX_TOPUP = Decimal("25000.00")
DAILY_TOPUP = Decimal("50000.00")
MONTHLY_TOPUP = Decimal("100000.00")
logger = logging.getLogger(__name__)


def within_deposit_limits(
    user: User, amount: Decimal, exclude_session: str = ""
) -> bool:
    """Caller holds the user lock; open reservations consume allowance too."""
    now = timezone.now()
    deposits = UserWalletTransaction.objects.filter(
        wallet__user=user,
        source=UserWalletTransaction.SOURCE_DEPOSIT,
        transaction_type=UserWalletTransaction.CREDIT,
    )
    reserved = WalletFundingAttempt.objects.filter(
        user=user, status__in=["reserved", "refund_pending"]
    )
    if exclude_session:
        reserved = reserved.exclude(session_id=exclude_session)
    # Even reservations created on an earlier date consume today's allowance until resolved.
    reserved_total = reserved.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    daily = deposits.filter(created__date=now.date()).aggregate(total=Sum("amount"))[
        "total"
    ] or Decimal("0")
    monthly = deposits.filter(
        created__year=now.year, created__month=now.month
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    return (
        daily + reserved_total + amount <= DAILY_TOPUP
        and monthly + reserved_total + amount <= MONTHLY_TOPUP
    )


@transaction.atomic
def create_funding_session(user: User, amount: Decimal) -> Any:
    User.objects.select_for_update().get(pk=user.pk)
    if not within_deposit_limits(user, amount):
        raise ValidationError(
            {
                "amount": "This deposit exceeds your daily or monthly wallet limit, including pending payments."
            }
        )
    stripe.api_key = settings.STRIPE_SECRET
    expires_at = timezone.now() + timedelta(minutes=30)
    session = stripe.checkout.Session.create(
        idempotency_key=f"funding-{user.pk}-{uuid4()}",
        expires_at=int(expires_at.timestamp()),
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "ProAce Wallet funds"},
                    "unit_amount": int(amount * 100),
                },
                "quantity": 1,
            }
        ],
        client_reference_id=str(user.pk),
        metadata={"wallet_topup": "true", "amount": str(amount)},
        success_url=f"{settings.FRONTEND_URL}/account/wallet?topup_session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}/account/wallet?topup_cancelled=1",
    )
    WalletFundingAttempt.objects.create(
        user=user, session_id=session.id, amount=amount, expires_at=expires_at
    )
    return session


def notify_funding(user: User, amount: Decimal) -> None:
    from core.services import get_or_create_user_wallet
    from notification.views import create_notification
    from utils.functions import send_mail

    try:
        wallet = get_or_create_user_wallet(user)
        send_mail(
            "wallet-funded",
            user.email,
            {"amount": str(amount), "balance": str(wallet.balance)},
        )
        create_notification(
            recipient=user,
            verb=f"Wallet funded: ${amount:.2f}",
            description="Your ProAce Wallet has been credited and is ready to use.",
            data={"category": "wallet", "event": "wallet_topup", "amount": str(amount)},
        )
        if amount >= Decimal("10000.00"):
            create_notification(
                recipient=user,
                verb="Large wallet deposit recorded",
                description="This deposit may receive an additional review.",
                data={
                    "category": "wallet",
                    "event": "wallet_topup_review",
                    "amount": str(amount),
                },
                level="warning",
            )
    except Exception:
        logger.exception("Funding receipt notification failed for user %s", user.pk)


@transaction.atomic
def confirm_funding(user: User, session_id: str, session: Any) -> WalletFundingAttempt:
    """Commit either one credit or a durable refund state before the view responds."""
    User.objects.select_for_update().get(pk=user.pk)
    if (
        session.get("client_reference_id") != str(user.pk)
        or session.get("metadata", {}).get("wallet_topup") != "true"
    ):
        raise ValidationError({"detail": "Invalid wallet top-up session."})
    if session.get("payment_status") != "paid":
        raise ValidationError({"detail": "Wallet payment has not been completed."})
    cents = session.get("amount_total")
    if not isinstance(cents, int) or cents <= 0:
        raise ValidationError({"detail": "Invalid wallet payment amount."})
    amount = Decimal(cents) / 100
    attempt, _ = WalletFundingAttempt.objects.get_or_create(
        session_id=session_id,
        defaults={"user": user, "amount": amount, "expires_at": timezone.now()},
    )
    if attempt.user_id != user.pk:
        raise ValidationError({"detail": "Invalid wallet top-up owner."})
    if attempt.status in {"credited", "refunded"}:
        return attempt
    reference = f"stripe_topup:{session_id}"
    # Recognize receipts issued before the durable funding migration.
    if UserWalletTransaction.objects.filter(
        wallet__user=user, reference=reference
    ).exists():
        attempt.status = "credited"
        attempt.save(update_fields=["status", "updated"])
        return attempt
    valid_payment = (
        session.get("currency") == "usd"
        and amount == attempt.amount
        and Decimal("5.00") <= amount <= MAX_TOPUP
        and within_deposit_limits(user, amount, exclude_session=session_id)
        and attempt.status == "reserved"
    )
    if not valid_payment:
        attempt.failure_reason = (
            "Payment currency, amount, reservation, or deposit allowance is invalid."
        )
        attempt.status = "refund_pending"
        attempt.expires_at = timezone.now()
        try:
            intent = session.get("payment_intent")
            if not intent:
                raise ValueError("Paid session has no payment intent.")
            stripe.api_key = settings.STRIPE_SECRET
            stripe.Refund.create(
                payment_intent=intent, idempotency_key=f"funding-refund-{session_id}"
            )
            attempt.status = "refunded"
        except Exception as exc:
            attempt.failure_reason += f" Refund pending: {type(exc).__name__}."
        attempt.save(
            update_fields=["status", "failure_reason", "expires_at", "updated"]
        )
        return attempt
    credit_user_wallet(
        user,
        amount,
        "Stripe wallet top-up",
        source=UserWalletTransaction.SOURCE_DEPOSIT,
        reference=reference,
        idempotency_key=f"funding-{session_id}",
    )
    attempt.status = "credited"
    attempt.save(update_fields=["status", "updated"])
    transaction.on_commit(lambda: notify_funding(user, amount))
    return attempt


@shared_task(name="payment.recover_wallet_funding")
def recover_wallet_funding() -> int:
    stripe.api_key = settings.STRIPE_SECRET
    count = 0
    attempts = WalletFundingAttempt.objects.filter(
        status__in=["reserved", "refund_pending"],
        expires_at__lte=timezone.now(),
    )
    for candidate in attempts.iterator():
        try:
            session = stripe.checkout.Session.retrieve(candidate.session_id)
            if session.get("payment_status") == "paid":
                result = confirm_funding(candidate.user, candidate.session_id, session)
                count += result.status in {"credited", "refunded"}
            else:
                with transaction.atomic():
                    User.objects.select_for_update().get(pk=candidate.user_id)
                    attempt = WalletFundingAttempt.objects.select_for_update().get(
                        pk=candidate.pk
                    )
                    if attempt.status != "reserved":
                        continue
                    # Expire at Stripe before releasing allowance, avoiding late payment races.
                    if session.get("status") != "expired":
                        stripe.checkout.Session.expire(attempt.session_id)
                    attempt.status = "released"
                    attempt.save(update_fields=["status", "updated"])
                    count += 1
        except Exception as exc:
            logger.warning(
                "Funding %s recovery deferred (%s)", candidate.pk, type(exc).__name__
            )
    return count
