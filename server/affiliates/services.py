from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from django.db import transaction

from affiliates.models import (
    AffiliateWallet,
    AffiliateWalletTransaction,
    Marketer,
    Referral,
)
from core.models import UserWalletTransaction
from core.services import credit_user_wallet


REFERRAL_REWARD_AMOUNT = Decimal("25.00")
MAX_REWARDED_REFERRALS = 4  # Capped at $25 for up to 4 users ($100 max promotional store credit)


@transaction.atomic
def record_referral(referral_code: str, referred_user: Any) -> Optional[Referral]:
    """Record an attribution link between a marketer and a newly verified customer.

    The referral starts in 'pending' status. Promotional store credit is NOT awarded
    upon email verification to prevent throwaway account abuse; rewards unlock only
    after the referred user completes a qualifying successful order.
    """
    code = str(referral_code or "").strip()
    if not code or not getattr(referred_user, "pk", None):
        return None

    marketer = (
        Marketer.objects.select_related("user")
        .select_for_update()
        .filter(marketer_id__iexact=code)
        .first()
    )
    if marketer is None or marketer.user_id == referred_user.pk:
        return None

    referral, _ = Referral.objects.select_for_update().get_or_create(
        referred_user=referred_user,
        defaults={
            "marketer": marketer,
            "reward_amount": REFERRAL_REWARD_AMOUNT,
            "status": Referral.PENDING,
        },
    )
    return referral


@transaction.atomic
def process_referral_reward_for_order(order: Any) -> Optional[Referral]:
    """Unlock and credit the promotional referral reward upon a customer's first successful order.

    Guarantees:
    1. Only orders placed and not cancelled/refunded qualify.
    2. Idempotent: once a referral is rewarded, subsequent orders by the customer do not grant rewards.
    3. Serialized per marketer to strictly cap at MAX_REWARDED_REFERRALS (4 rewards = $100 max).
    4. Self-referrals are disallowed.
    """
    if not order or not getattr(order, "user_id", None):
        return None
    if not getattr(order, "ordered", False):
        return None
    if getattr(order, "status", "") in ("cancelled", "refunded"):
        return None

    referral = (
        Referral.objects.select_related("marketer__user")
        .select_for_update()
        .filter(referred_user_id=order.user_id)
        .first()
    )
    if referral is None:
        return None
    if referral.status == Referral.REWARDED:
        return referral

    marketer = (
        Marketer.objects.select_related("user")
        .select_for_update()
        .filter(pk=referral.marketer_id)
        .first()
    )
    if marketer is None or marketer.user_id == order.user_id:
        return None

    rewarded_count = Referral.objects.filter(
        marketer=marketer, status=Referral.REWARDED
    ).count()

    if rewarded_count >= MAX_REWARDED_REFERRALS:
        referral.status = Referral.PENDING
        if hasattr(referral, "order") and not referral.order_id:
            referral.order = order
            referral.save(update_fields=["status", "order", "updated"])
        else:
            referral.save(update_fields=["status", "updated"])
        return referral

    referred_user = getattr(order, "user", None)
    display_name = (
        referred_user.first_name
        if referred_user and getattr(referred_user, "first_name", "")
        else (getattr(referred_user, "email", "") if referred_user else "customer")
    )

    credit_user_wallet(
        user=marketer.user,
        amount=REFERRAL_REWARD_AMOUNT,
        description=f"Referral reward ($25.00) for qualifying order by {display_name} ({rewarded_count + 1}/{MAX_REWARDED_REFERRALS})",
        source=UserWalletTransaction.SOURCE_REFERRAL,
        reference=f"REF-{referral.pk}",
        idempotency_key=f"referral-reward-{referral.pk}",
    )

    wallet, _ = AffiliateWallet.objects.select_for_update().get_or_create(
        user=marketer.user,
    )
    order_ref = getattr(order, "orderId", "") or str(order.pk)
    transaction_record = AffiliateWalletTransaction.objects.create(
        wallet=wallet,
        amount=REFERRAL_REWARD_AMOUNT,
        transaction_type=AffiliateWalletTransaction.CREDIT,
        reason="referral_order",
        metadata={
            "referral": referral.pk,
            "order_id": order.pk,
            "order_reference": order_ref,
            "wallet_credited": True,
            "reward_number": rewarded_count + 1,
            "max_rewards": MAX_REWARDED_REFERRALS,
        },
    )
    wallet.balance += REFERRAL_REWARD_AMOUNT
    wallet.save(update_fields=["balance", "updated"])

    referral.wallet_transaction = transaction_record
    referral.status = Referral.REWARDED
    if hasattr(referral, "order"):
        referral.order = order
        referral.save(update_fields=["wallet_transaction", "status", "order", "updated"])
    else:
        referral.save(update_fields=["wallet_transaction", "status", "updated"])

    from notification.views import create_notification
    create_notification(
        recipient=marketer.user,
        verb=f"Referral Reward Earned: ${REFERRAL_REWARD_AMOUNT}",
        description=f"You earned ${REFERRAL_REWARD_AMOUNT} in ProAce Wallet store credit because {display_name} completed their first successful order! (Reward {rewarded_count + 1}/{MAX_REWARDED_REFERRALS})",
        data={
            "event": "referral_reward",
            "amount": str(REFERRAL_REWARD_AMOUNT),
            "order_id": order.pk,
            "order_reference": order_ref,
            "reward_number": rewarded_count + 1,
            "max_rewards": MAX_REWARDED_REFERRALS,
        },
    )

    return referral


@transaction.atomic
def reward_referral(
    referral_code: str, referred_user: Any, order: Optional[Any] = None
) -> Optional[Referral]:
    """Record referral and optionally unlock reward if an active qualifying order exists."""
    referral = record_referral(referral_code, referred_user)
    if referral is None:
        return None

    if order is not None:
        return process_referral_reward_for_order(order)

    from payment.models import Order
    qualifying_order = (
        Order.objects.filter(user=referred_user, ordered=True)
        .exclude(status__in=["cancelled", "refunded"])
        .order_by("created")
        .first()
    )
    if qualifying_order:
        return process_referral_reward_for_order(qualifying_order)

    return referral
