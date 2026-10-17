from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from affiliates.models import Marketer, Referral
from core.models import User


@override_settings(ROOT_URLCONF='storefront.urls')
class ReferralWorkspaceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(email='referral-owner@test.com', password='Password123!')
        self.other = User.objects.create_user(email='other-referral@test.com', password='Password123!')
        self.marketer = Marketer.objects.create(user=self.owner, name='Owner')
        self.other_marketer = Marketer.objects.create(user=self.other, name='Other')
        self.client = APIClient()
        for index in range(5):
            referred = User.objects.create_user(email=f'referred-{index}@test.com', password='Password123!')
            Referral.objects.create(
                marketer=self.marketer, referred_user=referred,
                status='rewarded' if index < 4 else 'pending', reward_amount=Decimal('25.00'),
            )

    def test_workspace_scope_cap_and_filtered_pagination(self) -> None:
        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/v1/affiliates/workspace/?status=rewarded&limit=2')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['credit_earned'], '100.00')
        self.assertEqual(response.data['rewarded_count'], 4)
        self.assertEqual(response.data['count'], 4)
        self.assertEqual(len(response.data['results']), 2)
        self.assertIn('/register?ref=', response.data['invite_url'])
        self.assertNotIn('referred_email', response.data['results'][0])
        self.client.force_authenticate(self.other)
        response = self.client.get('/api/v1/affiliates/workspace/')
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['credit_earned'], '0.00')

    def test_unenrolled_workspace_and_invalid_dates(self) -> None:
        customer = User.objects.create_user(email='unenrolled@test.com', password='Password123!')
        self.client.force_authenticate(customer)
        response = self.client.get('/api/v1/affiliates/workspace/')
        self.assertFalse(response.data['enrolled'])
        self.assertEqual(response.data['invite_url'], '')
        response = self.client.get('/api/v1/affiliates/workspace/?start_date=2026-12-01&end_date=2026-01-01')
        self.assertEqual(response.status_code, 400)

    def test_operator_listing_access_filters_and_totals(self) -> None:
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get('/api/v1/admin/affiliates/').status_code, 403)
        staff = User.objects.create_user(email='affiliate-staff@test.com', password='Password123!', is_staff=True)
        self.client.force_authenticate(staff)
        response = self.client.get('/api/v1/admin/affiliates/?search=referral-owner&is_active=true')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['rewarded_count'], 4)
        self.assertEqual(response.data['results'][0]['credit_earned'], '100.00')
        self.assertEqual(self.client.get('/api/v1/admin/affiliates/?search=absent').data['count'], 0)
        # Check summary KPIs
        self.assertIn('summary', response.data)
        self.assertEqual(response.data['summary']['total_affiliates'], 2)
        self.assertEqual(response.data['summary']['total_referrals'], 5)
        self.assertEqual(response.data['summary']['rewarded_referrals'], 4)
        self.assertEqual(response.data['summary']['pending_referrals'], 1)
        self.assertEqual(response.data['summary']['total_credit_awarded'], '100.00')

        # Check tab=referrals
        ref_response = self.client.get('/api/v1/admin/affiliates/?tab=referrals&status=rewarded')
        self.assertEqual(ref_response.status_code, 200)
        self.assertEqual(ref_response.data['count'], 4)
        first_ref = ref_response.data['results'][0]
        self.assertEqual(first_ref['status'], 'rewarded')
        self.assertEqual(first_ref['reward_amount'], '25.00')
        self.assertEqual(first_ref['marketer']['name'], 'Owner')
        self.assertIn('@test.com', first_ref['referred_user']['email'])

    def test_operator_credit_totals_are_not_multiplied_by_referral_counts(self) -> None:
        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/v1/admin/affiliates/?search=referral-owner')
        self.assertEqual(response.status_code, 403)

        staff = User.objects.create_user(
            email='affiliate-totals-staff@test.com', password='Password123!', is_staff=True,
        )
        self.client.force_authenticate(staff)
        response = self.client.get('/api/v1/admin/affiliates/?search=referral-owner')
        self.assertEqual(response.status_code, 200)
        row = response.data['results'][0]
        self.assertEqual(row['referral_count'], 5)
        self.assertEqual(row['rewarded_count'], 4)
        self.assertEqual(row['credit_earned'], '100.00')

    def test_customer_referral_filter_validation_is_returned_as_400(self) -> None:
        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/v1/affiliates/workspace/?status=unknown')
        self.assertEqual(response.status_code, 400)

    def test_workspace_rejects_backoffice_and_operator_rejects_unknown_tab(self) -> None:
        staff = User.objects.create_user(
            email='affiliate-boundary-staff@test.com', password='Password123!', is_staff=True,
        )
        self.client.force_authenticate(staff)
        self.assertEqual(self.client.get('/api/v1/affiliates/workspace/').status_code, 403)
        self.assertEqual(
            self.client.get('/api/v1/admin/affiliates/?tab=unexpected').status_code,
            400,
        )

