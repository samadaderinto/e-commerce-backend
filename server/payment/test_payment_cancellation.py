"""Cancellation must not release wallet funds while Stripe can still collect payment."""

from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import User, UserWallet, UserWalletTransaction
from core.services import credit_user_wallet, debit_user_wallet
from payment.models import CheckoutAttempt, WalletFundingAttempt


@override_settings(ROOT_URLCONF="storefront.urls", STRIPE_SECRET="sk_test_cancel")
class PaymentCancellationTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="payment-cancel@test.com", password="test-password"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        credit_user_wallet(self.user, Decimal("100.00"), "Test balance")

    def create_checkout_attempt(self, session_id: str, amount: str = "20.00") -> CheckoutAttempt:
        debit_user_wallet(
            self.user,
            Decimal(amount),
            "Reserved checkout",
            reference=f"reserve-{session_id}",
        )
        return CheckoutAttempt.objects.create(
            user=self.user,
            checkout_key=uuid4(),
            session_id=session_id,
            wallet_amount=Decimal(amount),
            expires_at=timezone.now(),
        )

    def create_funding_attempt(self, session_id: str) -> WalletFundingAttempt:
        return WalletFundingAttempt.objects.create(
            user=self.user,
            session_id=session_id,
            amount=Decimal("25.00"),
            expires_at=timezone.now(),
        )

    @patch("storefront.views.stripe.checkout.Session.expire")
    @patch("storefront.views.stripe.checkout.Session.retrieve")
    def test_checkout_lookup_failure_keeps_wallet_reservation(
        self, retrieve: Mock, expire: Mock
    ) -> None:
        attempt = self.create_checkout_attempt("cs_lookup_failure")
        retrieve.side_effect = RuntimeError("Stripe unavailable")

        response = self.client.post(
            "/api/v1/checkout/wallet-cancel/",
            {"checkout_key": str(attempt.checkout_key)},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "reserved")
        self.assertEqual(UserWallet.objects.get(user=self.user).balance, Decimal("80.00"))
        expire.assert_not_called()

    @patch("storefront.views.stripe.checkout.Session.expire")
    @patch(
        "storefront.views.stripe.checkout.Session.retrieve",
        return_value={"status": "open", "payment_status": "unpaid"},
    )
    def test_checkout_expiry_failure_keeps_reservation(
        self, retrieve: Mock, expire: Mock
    ) -> None:
        attempt = self.create_checkout_attempt("cs_expiry_failure")
        expire.side_effect = RuntimeError("Stripe unavailable")

        response = self.client.post(
            "/api/v1/checkout/wallet-cancel/",
            {"checkout_key": str(attempt.checkout_key)},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "reserved")
        self.assertEqual(UserWallet.objects.get(user=self.user).balance, Decimal("80.00"))
        expire.assert_called_once_with(attempt.session_id)

    @patch(
        "storefront.views.stripe.checkout.Session.expire",
        return_value={"status": "expired", "payment_status": "unpaid"},
    )
    @patch(
        "storefront.views.stripe.checkout.Session.retrieve",
        return_value={"status": "open", "payment_status": "unpaid"},
    )
    def test_checkout_releases_only_the_referenced_expired_attempt(
        self, retrieve: Mock, expire: Mock
    ) -> None:
        target = self.create_checkout_attempt("cs_target")
        other = self.create_checkout_attempt("cs_other")

        response = self.client.post(
            "/api/v1/checkout/wallet-cancel/",
            {"checkout_key": str(target.checkout_key)},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        target.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(target.status, "released")
        self.assertEqual(other.status, "reserved")
        self.assertEqual(UserWallet.objects.get(user=self.user).balance, Decimal("80.00"))
        self.assertEqual(
            UserWalletTransaction.objects.filter(
                idempotency_key=f"compensate-{target.checkout_key}-wallet"
            ).count(),
            1,
        )
        expire.assert_called_once_with(target.session_id)

    def test_checkout_cancel_requires_a_specific_reference(self) -> None:
        self.create_checkout_attempt("cs_ambiguous")

        response = self.client.post(
            "/api/v1/checkout/wallet-cancel/", {}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            CheckoutAttempt.objects.get(session_id="cs_ambiguous").status,
            "reserved",
        )

    @patch("storefront.views.stripe.checkout.Session.retrieve")
    def test_topup_lookup_failure_keeps_reservation(self, retrieve: Mock) -> None:
        attempt = self.create_funding_attempt("cs_topup_lookup_failure")
        retrieve.side_effect = RuntimeError("Stripe unavailable")

        response = self.client.post("/api/v1/wallet/topup-cancel/", {}, format="json")

        self.assertEqual(response.status_code, 503)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "reserved")

    @patch("storefront.views.stripe.checkout.Session.expire")
    @patch(
        "storefront.views.stripe.checkout.Session.retrieve",
        return_value={"status": "open", "payment_status": "unpaid"},
    )
    def test_topup_expiry_failure_keeps_reservation(
        self, retrieve: Mock, expire: Mock
    ) -> None:
        attempt = self.create_funding_attempt("cs_topup_expiry_failure")
        expire.side_effect = RuntimeError("Stripe unavailable")

        response = self.client.post("/api/v1/wallet/topup-cancel/", {}, format="json")

        self.assertEqual(response.status_code, 503)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "reserved")
        expire.assert_called_once_with(attempt.session_id)

    @patch(
        "storefront.views.stripe.checkout.Session.expire",
        return_value={"status": "expired", "payment_status": "unpaid"},
    )
    @patch(
        "storefront.views.stripe.checkout.Session.retrieve",
        return_value={"status": "open", "payment_status": "unpaid"},
    )
    def test_topup_releases_only_after_stripe_expiry_confirmation(
        self, retrieve: Mock, expire: Mock
    ) -> None:
        attempt = self.create_funding_attempt("cs_topup_expired")

        response = self.client.post("/api/v1/wallet/topup-cancel/", {}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["released"])
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "released")
        expire.assert_called_once_with(attempt.session_id)

    @patch("storefront.views.stripe.checkout.Session.retrieve")
    def test_paid_topup_cannot_be_marked_released(self, retrieve: Mock) -> None:
        attempt = self.create_funding_attempt("cs_topup_paid")
        retrieve.return_value = {"status": "complete", "payment_status": "paid"}

        response = self.client.post("/api/v1/wallet/topup-cancel/", {}, format="json")

        self.assertEqual(response.status_code, 409)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "reserved")

    def test_ambiguous_topup_cancel_keeps_all_reservations(self) -> None:
        first = self.create_funding_attempt("cs_topup_one")
        second = self.create_funding_attempt("cs_topup_two")

        response = self.client.post("/api/v1/wallet/topup-cancel/", {}, format="json")

        self.assertEqual(response.status_code, 409)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, "reserved")
        self.assertEqual(second.status, "reserved")

