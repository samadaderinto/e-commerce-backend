"""Escrow settlement with nullable order joins and repeat invocations."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from core.models import User
from store.models import MerchantWallet, StoreEarningsLedger
from store.services import settle_pending_merchant_earnings


class SettlementRegressionTests(TestCase):
    def test_nullable_order_settlement_preserves_future_escrow_and_is_idempotent(self) -> None:
        user = User.objects.create_user(email=f'settlement-{uuid4().hex}@test.invalid', password='test-password')
        wallet = MerchantWallet.objects.create(user=user, pending_balance=Decimal('15.00'))
        due = StoreEarningsLedger.objects.create(
            wallet=wallet, order=None, net_amount=Decimal('10.00'),
            available_at=timezone.now() - timedelta(days=1),
        )
        future = StoreEarningsLedger.objects.create(
            wallet=wallet, order=None, net_amount=Decimal('5.00'),
            available_at=timezone.now() + timedelta(days=1),
        )
        settle_pending_merchant_earnings()
        wallet.refresh_from_db()
        due.refresh_from_db()
        future.refresh_from_db()
        self.assertEqual(wallet.available_balance, Decimal('10.00'))
        self.assertEqual(wallet.pending_balance, Decimal('5.00'))
        self.assertEqual(due.status, StoreEarningsLedger.STATUS_AVAILABLE)
        self.assertEqual(future.status, StoreEarningsLedger.STATUS_PENDING)
        settle_pending_merchant_earnings()
        wallet.refresh_from_db()
        self.assertEqual(wallet.available_balance, Decimal('10.00'))
        self.assertEqual(wallet.pending_balance, Decimal('5.00'))
