from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from core.models import User, UserWallet
from core.services import credit_user_wallet, debit_user_wallet
from payment.checkout_recovery import compensate_checkout
from payment.funding import confirm_funding
from payment.models import CheckoutAttempt, WalletFundingAttempt


class CompensationSettlementAuditTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email='compensation@test.local', password='test')
        credit_user_wallet(self.user, Decimal('50'), 'Fixture funds')

    def test_checkout_keeps_wallet_reserved_until_provider_refund_settles(self) -> None:
        debit_user_wallet(self.user, Decimal('20'), 'Fixture reservation')
        attempt = CheckoutAttempt.objects.create(
            user=self.user, checkout_key=uuid4(), session_id='cs_compensation',
            wallet_amount=20, expires_at=timezone.now() - timedelta(minutes=1),
        )
        session = {'payment_status': 'paid', 'payment_intent': 'pi_compensation'}
        with patch('storefront.views.complete_stripe_checkout', return_value=None), patch('stripe.Refund.create') as refund, patch('stripe.Refund.retrieve') as retrieve:
            retrieve.side_effect = lambda reference: refund.return_value
            refund.return_value = {'id': 're_compensation', 'status': 'pending'}
            self.assertFalse(compensate_checkout(attempt, session, 'Fixture failure'))
            attempt.refresh_from_db()
            self.assertEqual(attempt.status, 'refund_pending')
            self.assertEqual(UserWallet.objects.get(user=self.user).balance, Decimal('30'))
            refund.return_value = {'id': 're_compensation', 'status': 'succeeded'}
            self.assertTrue(compensate_checkout(attempt, session, 'Fixture retry'))
            self.assertTrue(compensate_checkout(attempt, session, 'Duplicate retry'))
            self.assertEqual(UserWallet.objects.get(user=self.user).balance, Decimal('50'))

    def test_funding_compensation_does_not_report_unsettled_refunds_as_refunded(self) -> None:
        attempt = WalletFundingAttempt.objects.create(
            user=self.user, session_id='cs_funding_compensation', amount=5,
            expires_at=timezone.now(),
        )
        session = {
            'client_reference_id': str(self.user.pk), 'metadata': {'wallet_topup': 'true'},
            'payment_status': 'paid', 'currency': 'eur', 'amount_total': 500,
            'payment_intent': 'pi_funding_compensation',
        }
        with patch('stripe.Refund.create') as refund, patch('stripe.Refund.retrieve') as retrieve:
            retrieve.side_effect = lambda reference: refund.return_value
            for status in ('pending', 'requires_action', 'failed', 'canceled', None):
                with self.subTest(status=status):
                    refund.return_value = {'id': 're_funding_compensation', 'status': status}
                    result = confirm_funding(self.user, attempt.session_id, session)
                    self.assertEqual(result.status, 'refund_pending')
            refund.return_value = {'id': 're_funding_compensation', 'status': 'succeeded'}
            self.assertEqual(confirm_funding(self.user, attempt.session_id, session).status, 'refunded')
        self.assertEqual(UserWallet.objects.get(user=self.user).balance, Decimal('50'))

    def test_cached_pending_create_is_checked_against_current_provider_status(self) -> None:
        from payment.compensation import create_settled_compensation_refund

        with patch('stripe.Refund.create', return_value={'id': 're_cached', 'status': 'pending'}), patch(
            'stripe.Refund.retrieve', return_value={'id': 're_cached', 'status': 'succeeded'},
        ) as retrieve:
            self.assertTrue(create_settled_compensation_refund('pi_fixture', 'compensation-fixture'))
            retrieve.assert_called_once_with('re_cached')
