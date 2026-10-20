from __future__ import annotations

from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.apps import apps
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from rest_framework.exceptions import ValidationError

from core.models import User, UserWallet, UserWalletTransaction
from core.services import credit_user_wallet, debit_user_wallet


class WalletIntegrityAuditTests(TestCase):
    def test_invalid_money_never_changes_balance_or_writes_a_receipt(self) -> None:
        user = User.objects.create_user(email='money-integrity@test.local', password='test')
        credit_user_wallet(user, Decimal('50'), 'Fixture funds')
        for operation in (credit_user_wallet, debit_user_wallet):
            for amount in ('0.001', '5.005', '10000000000.00', 'invalid', 'NaN', 'Infinity', True):
                with self.subTest(operation=operation.__name__, amount=amount):
                    with self.assertRaises(ValidationError):
                        operation(user, amount, 'Invalid amount fixture')
                    self.assertEqual(UserWallet.objects.get(user=user).balance, Decimal('50'))
                    self.assertEqual(UserWalletTransaction.objects.filter(wallet__user=user).count(), 1)

    def test_exact_cents_replay_and_balance_capacity(self) -> None:
        user = User.objects.create_user(email='money-capacity@test.local', password='test')
        first = credit_user_wallet(user, '5.00', 'Fixture', idempotency_key='cent-fixture')
        replay = credit_user_wallet(user, '5.000', 'Fixture replay', idempotency_key='cent-fixture')
        self.assertEqual(first.pk, replay.pk)
        UserWallet.objects.filter(user=user).update(balance=Decimal('9999999999.99'))
        with self.assertRaises(ValidationError):
            credit_user_wallet(user, '0.01', 'Overflow fixture')
        self.assertEqual(UserWalletTransaction.objects.filter(wallet__user=user).count(), 1)


@skipUnless(connection.vendor == 'postgresql', 'Row-lock contention requires PostgreSQL.')
class WalletConcurrencyAuditTests(TransactionTestCase):
    available_apps = [config.name for config in apps.get_app_configs()]

    def test_parallel_credits_serialize_and_duplicate_receipts_apply_once(self) -> None:
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                user = User.objects.create_user(email=f'parallel-{duplicate}@test.local', password='test')
                barrier = Barrier(8)

                def credit(index: int) -> None:
                    close_old_connections()
                    try:
                        buyer = User.objects.get(pk=user.pk)
                        barrier.wait(timeout=20)
                        credit_user_wallet(
                            buyer, '10.00', 'Concurrent fixture',
                            idempotency_key=f'parallel-{duplicate}-{0 if duplicate else index}',
                        )
                    finally:
                        connection.close()

                with ThreadPoolExecutor(max_workers=8) as pool:
                    list(pool.map(credit, range(8)))
                self.assertEqual(UserWallet.objects.get(user=user).balance, Decimal('10' if duplicate else '80'))
                self.assertEqual(UserWalletTransaction.objects.filter(wallet__user=user).count(), 1 if duplicate else 8)
