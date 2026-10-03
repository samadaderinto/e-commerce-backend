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
def reward_referral(referral_code: str, referred_user: Any) -> Optional[Referral]:
    marketer = Marketer.objects.select_related("user").filter(
        marketer_id=referral_code
    ).first()
    if marketer is None or marketer.user_id == referred_user.pk:
        return None

    referral, created = Referral.objects.select_for_update().get_or_create(
        referred_user=referred_user,
        defaults={
            "marketer": marketer,
            "reward_amount": REFERRAL_REWARD_AMOUNT,
        },
    )
    if not created:
        return referral

    rewarded_count = Referral.objects.filter(
        marketer=marketer, status=Referral.REWARDED
    ).count()

    if rewarded_count >= MAX_REWARDED_REFERRALS:
        referral.status = Referral.PENDING
        referral.save(update_fields=["status", "updated"])
        return referral

    # Option A: Credit the user's primary ProAce UserWallet (non-withdrawable promotional store credit)
    credit_user_wallet(
        user=marketer.user,
        amount=REFERRAL_REWARD_AMOUNT,
        description=f"Referral reward ($25.00) for inviting {referred_user.first_name or referred_user.email} ({rewarded_count + 1}/{MAX_REWARDED_REFERRALS})",
        source=UserWalletTransaction.SOURCE_REFERRAL,
        reference=f"REF-{referral.pk}",
    )

    wallet, _ = AffiliateWallet.objects.select_for_update().get_or_create(
        user=marketer.user,
    )
    transaction_record = AffiliateWalletTransaction.objects.create(
        wallet=wallet,
        amount=REFERRAL_REWARD_AMOUNT,
        transaction_type=AffiliateWalletTransaction.CREDIT,
        reason="referral_signup",
        metadata={
            "referral": referral.pk,
            "referred_user": referred_user.pk,
            "referral_code": referral_code,
            "wallet_credited": True,
            "reward_number": rewarded_count + 1,
            "max_rewards": MAX_REWARDED_REFERRALS,
        },
    )
    wallet.balance += REFERRAL_REWARD_AMOUNT
    wallet.save(update_fields=["balance", "updated"])

    referral.wallet_transaction = transaction_record
    referral.status = Referral.REWARDED
    referral.save(update_fields=["wallet_transaction", "status", "updated"])

    from notification.views import create_notification
    create_notification(
        recipient=marketer.user,
        verb=f"Referral Reward Earned: ${REFERRAL_REWARD_AMOUNT}",
        description=f"You earned ${REFERRAL_REWARD_AMOUNT} in ProAce Wallet store credit for referring {referred_user.first_name or referred_user.email}! (Reward {rewarded_count + 1}/{MAX_REWARDED_REFERRALS})",
        data={
            "event": "referral_reward",
            "amount": str(REFERRAL_REWARD_AMOUNT),
            "reward_number": rewarded_count + 1,
            "max_rewards": MAX_REWARDED_REFERRALS,
        },
    )

    return referral
