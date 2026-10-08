from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

from core.models import UserWallet, UserWalletTransaction


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
    amount_dec = Decimal(str(amount))
    if not amount_dec.is_finite() or amount_dec <= Decimal("0.00"):
        raise ValidationError({"detail": "Credit amount must be greater than zero."})

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
    amount_dec = Decimal(str(amount))
    if not amount_dec.is_finite() or amount_dec <= Decimal("0.00"):
        raise ValidationError({"detail": "Debit amount must be greater than zero."})

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
