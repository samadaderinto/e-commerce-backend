from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from core.models import User, UserWallet
from core.services import credit_user_wallet, debit_user_wallet
from payment.models import CheckoutAttempt
from payment.checkout_recovery import compensate_checkout


class CheckoutRecoveryTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email='recovery@test.com', password='test-password')
        credit_user_wallet(self.user, Decimal('50'), 'Initial credit')
        debit_user_wallet(self.user, Decimal('20'), 'Reserved checkout')
        self.attempt = CheckoutAttempt.objects.create(user=self.user, checkout_key=uuid4(), session_id='cs_recovery', wallet_amount=20, expires_at=timezone.now() - timedelta(minutes=1))

    @patch('stripe.Refund.create')
    def test_paid_failure_refunds_and_releases_wallet_once(self, refund) -> None:
        refund.return_value = {'id': 're_recovery', 'status': 'succeeded'}
        session = {'payment_status': 'paid', 'payment_intent': 'pi_recovery'}
        self.assertTrue(compensate_checkout(self.attempt, session, 'Price changed'))
        self.assertTrue(compensate_checkout(self.attempt, session, 'Duplicate callback'))
        self.assertEqual(UserWallet.objects.get(user=self.user).balance, Decimal('50'))
        self.assertEqual(refund.call_count, 1)

    @patch('stripe.Refund.create')
    def test_failed_refund_remains_durable_and_retryable(self, refund) -> None:
        refund.return_value = {'id': 're_recovery', 'status': 'succeeded'}
        refund.side_effect = RuntimeError('Stripe unavailable')
        session = {'payment_status': 'paid', 'payment_intent': 'pi_recovery'}
        self.assertFalse(compensate_checkout(self.attempt, session, 'Coupon depleted'))
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, 'refund_pending')
        self.assertEqual(UserWallet.objects.get(user=self.user).balance, Decimal('30'))
        refund.side_effect = None
        self.assertTrue(compensate_checkout(self.attempt, session, 'Retry'))
        self.assertEqual(UserWallet.objects.get(user=self.user).balance, Decimal('50'))

    def test_expired_unpaid_session_releases_only_reserved_credit(self) -> None:
        session = {'payment_status': 'unpaid', 'status': 'expired'}
        self.assertTrue(compensate_checkout(self.attempt, session, 'Abandoned'))
        self.assertEqual(UserWallet.objects.get(user=self.user).balance, Decimal('50'))

    @patch('stripe.checkout.Session.retrieve')
    def test_scheduled_recovery_releases_expired_holds_once(self, retrieve) -> None:
        from payment.checkout_recovery import recover_checkout_attempts
        retrieve.return_value = {'payment_status': 'unpaid', 'status': 'expired'}
        self.assertEqual(recover_checkout_attempts(), 1)
        self.assertEqual(recover_checkout_attempts(), 0)
        self.assertEqual(UserWallet.objects.get(user=self.user).balance, Decimal('50'))
