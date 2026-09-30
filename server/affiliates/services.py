from decimal import Decimal

from django.db import transaction

from affiliates.models import (
    AffiliateWallet,
    AffiliateWalletTransaction,
    Marketer,
    Referral,
)


REFERRAL_REWARD_AMOUNT = Decimal("25.00")


@transaction.atomic
def reward_referral(referral_code, referred_user):
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
        },
    )
    wallet.balance += REFERRAL_REWARD_AMOUNT
    wallet.save(update_fields=["balance", "updated"])

    referral.wallet_transaction = transaction_record
    referral.status = Referral.REWARDED
    referral.save(update_fields=["wallet_transaction", "status", "updated"])
    return referral
