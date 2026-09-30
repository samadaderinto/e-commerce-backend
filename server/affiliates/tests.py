from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from affiliates.models import AffiliateWallet, Marketer, Referral
from affiliates.services import reward_referral
from core.models import User
from storefront.views import AuthView


class AffiliateReferralTests(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(
            email="referrer@test.com",
            password="Strong-test-password-123",
            first_name="Ref",
            last_name="Errer",
            gender="male",
            phone1="+2348012345678",
        )
        self.marketer = Marketer.objects.create(user=self.referrer, name="Referrer")

    def test_reward_referral_adds_25_to_referrer_wallet(self):
        referred = User.objects.create_user(
            email="referred@test.com",
            password="Strong-test-password-123",
            first_name="New",
            last_name="User",
            gender="female",
            phone1="+2348012345679",
        )

        referral = reward_referral(self.marketer.marketer_id, referred)

        wallet = AffiliateWallet.objects.get(user=self.referrer)
        self.assertIsNotNone(referral)
        self.assertEqual(wallet.balance, Decimal("25.00"))
        self.assertEqual(wallet.transactions.count(), 1)
        self.assertEqual(referral.status, Referral.REWARDED)
        self.assertEqual(referral.reward_amount, Decimal("25.00"))

    def test_reward_referral_is_idempotent_for_same_referred_user(self):
        referred = User.objects.create_user(
            email="duplicate@test.com",
            password="Strong-test-password-123",
            first_name="Dupe",
            last_name="User",
            gender="female",
            phone1="+2348012345680",
        )

        first = reward_referral(self.marketer.marketer_id, referred)
        second = reward_referral(self.marketer.marketer_id, referred)

        wallet = AffiliateWallet.objects.get(user=self.referrer)
        self.assertEqual(first, second)
        self.assertEqual(wallet.balance, Decimal("25.00"))
        self.assertEqual(wallet.transactions.count(), 1)

    def test_user_cannot_reward_their_own_referral_code(self):
        referral = reward_referral(self.marketer.marketer_id, self.referrer)

        self.assertIsNone(referral)
        self.assertFalse(AffiliateWallet.objects.filter(user=self.referrer).exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AffiliateRegistrationTests(TestCase):
    def test_registration_with_referral_code_rewards_referrer(self):
        referrer = User.objects.create_user(
            email="owner@test.com",
            password="Strong-test-password-123",
            first_name="Owner",
            last_name="Account",
            gender="male",
            phone1="+2348012345681",
        )
        marketer = Marketer.objects.create(user=referrer, name="Owner")
        factory = APIRequestFactory()

        request = factory.post(
            "/api/v1/auth/register/",
            {
                "email": "new-referred@test.com",
                "first_name": "New",
                "last_name": "Customer",
                "phone1": "+2348012345682",
                "password": "Strong-new-password-123",
                "referral_code": marketer.marketer_id,
            },
            format="json",
        )
        response = AuthView.as_view()(request, action="register")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(AffiliateWallet.objects.get(user=referrer).balance, Decimal("25.00"))
        self.assertEqual(Referral.objects.count(), 1)
