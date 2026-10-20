from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

from core.models import UserWallet, UserWalletTransaction

MAX_WALLET_AMOUNT = Decimal('9999999999.99')


def _wallet_amount(amount: Decimal | str | float) -> Decimal:
    message = (
        'Enter a positive wallet amount with at most two decimal places '
        'within the supported limit.'
    )
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError({'detail': message}) from None
    if (
        not value.is_finite()
        or not Decimal('0') < value <= MAX_WALLET_AMOUNT
        or value != value.quantize(Decimal('0.01'))
    ):
        raise ValidationError({'detail': message})
    return value


def get_or_create_user_wallet(user: Any) -> UserWallet:
    wallet, _ = UserWallet.objects.get_or_create(user=user)
    return wallet


@transaction.atomic
def credit_user_wallet(
    user: Any,
    amount: Decimal | str | float,
    description: str,
    source: str = UserWalletTransaction.SOURCE_REFUND,
    reference: str = "",
    idempotency_key: str | None = None,
) -> UserWalletTransaction:
    amount_dec = _wallet_amount(amount)

    wallet, _ = UserWallet.objects.select_for_update().get_or_create(user=user)
    if idempotency_key:
        existing = UserWalletTransaction.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        if existing:
            if (
                existing.wallet_id != wallet.pk
                or existing.amount != amount_dec
                or existing.transaction_type != UserWalletTransaction.CREDIT
            ):
                raise ValidationError(
                    {"detail": "Conflicting wallet credit reference."}
                )
            return existing
    if wallet.balance + amount_dec > MAX_WALLET_AMOUNT:
        raise ValidationError({
            'detail': 'This credit would exceed the supported wallet balance limit.'
        })
    wallet.balance += amount_dec
    wallet.save(update_fields=["balance", "updated"])

    tx = UserWalletTransaction.objects.create(
        wallet=wallet,
        transaction_type=UserWalletTransaction.CREDIT,
        amount=amount_dec,
        source=source,
        description=description,
        reference=reference,
        idempotency_key=idempotency_key,
    )
    return tx


@transaction.atomic
def debit_user_wallet(
    user: Any,
    amount: Decimal | str | float,
    description: str,
    source: str = UserWalletTransaction.SOURCE_PURCHASE,
    reference: str = "",
) -> UserWalletTransaction:
    amount_dec = _wallet_amount(amount)

    wallet, _ = UserWallet.objects.select_for_update().get_or_create(user=user)
    if wallet.balance < amount_dec:
        raise ValidationError({"detail": "Insufficient wallet balance."})

    wallet.balance -= amount_dec
    wallet.save(update_fields=["balance", "updated"])

    tx = UserWalletTransaction.objects.create(
        wallet=wallet,
        transaction_type=UserWalletTransaction.DEBIT,
        amount=amount_dec,
        source=source,
        description=description,
        reference=reference,
    )
    return tx
