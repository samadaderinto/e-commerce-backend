from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.response import Response

from core.models import User
from store.models import MerchantWallet, Store
from store.views import StoreViewSet


@override_settings(STRIPE_SECRET='sk_test')
class StripeConnectRecoveryTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email='connect@test.com', password='test-password')
        self.store = Store.objects.create(user=self.user, name='Connect store')
        self.wallet = MerchantWallet.objects.create(user=self.user, stripe_account_id='acct_mock_old')

    def request(self) -> Response:
        request = APIRequestFactory().post('/connect-stripe/', {}, format='json')
        force_authenticate(request, self.user)
        return StoreViewSet.as_view({'post': 'connect_stripe'})(request, pk=str(self.store.pk))

    def status_request(self) -> Response:
        request = APIRequestFactory().get('/stripe-status/')
        force_authenticate(request, self.user)
        return StoreViewSet.as_view({'get': 'stripe_status'})(request, pk=str(self.store.pk))

    @patch('stripe.AccountLink.create')
    @patch('stripe.Account.create')
    @patch('stripe.Account.retrieve')
    def test_seeded_mock_account_is_replaced_without_retrieval(self, retrieve, create, link) -> None:
        create.return_value = SimpleNamespace(id='acct_real_new')
        link.return_value = SimpleNamespace(url='https://connect.stripe.com/test')
        response = self.request()
        self.assertEqual(response.status_code, 200, response.data)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.stripe_account_id, 'acct_real_new')
        self.assertFalse(self.wallet.stripe_details_submitted)
        self.assertFalse(self.wallet.stripe_payouts_enabled)
        retrieve.assert_not_called()
        self.assertEqual(link.call_args.kwargs['account'], 'acct_real_new')
        self.assertTrue(link.call_args.kwargs['return_url'].endswith('?stripe_onboarding=return'))
        self.assertTrue(link.call_args.kwargs['refresh_url'].endswith('?stripe_onboarding=refresh'))

    @patch('stripe.AccountLink.create')
    @patch('stripe.Account.create')
    @patch('stripe.Account.retrieve')
    def test_created_account_survives_link_failure_and_retry_reuses_it(
        self, retrieve, create, link
    ) -> None:
        create.return_value = SimpleNamespace(id='acct_real_saved')
        link.side_effect = [
            RuntimeError('temporary link failure'),
            SimpleNamespace(url='https://connect.stripe.com/retry'),
        ]

        failed_response = self.request()

        self.assertEqual(failed_response.status_code, 400)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.stripe_account_id, 'acct_real_saved')

        retrieve.return_value = {
            'details_submitted': False,
            'payouts_enabled': False,
            'requirements': {'currently_due': ['individual.address.line1']},
        }
        retry_response = self.request()

        self.assertEqual(retry_response.status_code, 200, retry_response.data)
        self.assertEqual(retry_response.data['stripe_account_id'], 'acct_real_saved')
        create.assert_called_once()
        self.assertEqual(link.call_count, 2)

    @patch('stripe.Account.retrieve')
    def test_status_sync_persists_enabled_payout_state(self, retrieve) -> None:
        self.wallet.stripe_account_id = 'acct_real_connected'
        self.wallet.save(update_fields=['stripe_account_id'])
        retrieve.return_value = {
            'details_submitted': True,
            'payouts_enabled': True,
            'requirements': {'currently_due': []},
        }
        response = self.status_request()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {
            'connected': True,
            'details_submitted': True,
            'payouts_enabled': True,
            'currently_due': [],
        })
        self.wallet.refresh_from_db()
        self.assertTrue(self.wallet.stripe_details_submitted)
        self.assertTrue(self.wallet.stripe_payouts_enabled)

    @patch('stripe.Account.retrieve')
    def test_status_sync_keeps_incomplete_account_resumable(self, retrieve) -> None:
        self.wallet.stripe_account_id = 'acct_real_pending'
        self.wallet.save(update_fields=['stripe_account_id'])
        retrieve.return_value = {
            'details_submitted': True,
            'payouts_enabled': False,
            'requirements': {'currently_due': ['individual.address.line1']},
        }
        response = self.status_request()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['connected'])
        self.assertEqual(response.data['currently_due'], ['individual.address.line1'])

    def test_status_sync_does_not_treat_mock_account_as_connected(self) -> None:
        response = self.status_request()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['connected'])

    @patch('stripe.AccountLink.create')
    @patch('stripe.Account.retrieve')
    def test_connected_account_does_not_create_another_onboarding_link(self, retrieve, link) -> None:
        self.wallet.stripe_account_id = 'acct_real_connected'
        self.wallet.save(update_fields=['stripe_account_id'])
        retrieve.return_value = {
            'details_submitted': True,
            'payouts_enabled': True,
        }
        response = self.request()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['connected'])
        self.assertEqual(response.data['url'], '')
        link.assert_not_called()
        self.wallet.refresh_from_db()
        self.assertTrue(self.wallet.stripe_details_submitted)
        self.assertTrue(self.wallet.stripe_payouts_enabled)

    @patch('stripe.AccountLink.create')
    @patch('stripe.Account.retrieve')
    def test_submitted_account_under_review_does_not_create_another_link(self, retrieve, link) -> None:
        self.wallet.stripe_account_id = 'acct_real_pending_review'
        self.wallet.save(update_fields=['stripe_account_id'])
        retrieve.return_value = {
            'details_submitted': True,
            'payouts_enabled': False,
            'requirements': {'currently_due': []},
        }
        response = self.request()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['pending'])
        self.assertEqual(response.data['url'], '')
        link.assert_not_called()

    @patch('stripe.AccountLink.create')
    @patch('stripe.Account.create')
    @patch('stripe.Account.retrieve')
    def test_missing_real_account_is_replaced(self, retrieve, create, link) -> None:
        self.wallet.stripe_account_id = 'acct_real_missing'
        self.wallet.save(update_fields=['stripe_account_id'])
        retrieve.side_effect = stripe.InvalidRequestError('No such account', 'account', code='resource_missing')
        create.return_value = SimpleNamespace(id='acct_real_new')
        link.return_value = SimpleNamespace(url='https://connect.stripe.com/test')
        response = self.request()
        self.assertEqual(response.status_code, 200, response.data)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.stripe_account_id, 'acct_real_new')
        self.assertEqual(link.call_args.kwargs['account'], 'acct_real_new')

    @patch('stripe.Account.create')
    @patch('stripe.Account.retrieve')
    def test_other_provider_failure_is_sanitized_and_preserves_account(self, retrieve, create) -> None:
        self.wallet.stripe_account_id = 'acct_real_existing'
        self.wallet.save(update_fields=['stripe_account_id'])
        retrieve.side_effect = stripe.InvalidRequestError('SECRET provider detail', 'account', code='invalid_api_key')
        response = self.request()
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('SECRET', str(response.data))
        create.assert_not_called()
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.stripe_account_id, 'acct_real_existing')

    @patch('stripe.Account.create')
    @patch('stripe.Account.retrieve')
    def test_real_account_permission_failure_is_not_treated_as_a_mock(self, retrieve, create) -> None:
        self.wallet.stripe_account_id = 'acct_real_existing'
        self.wallet.save(update_fields=['stripe_account_id'])
        retrieve.side_effect = stripe.PermissionError('Account access denied')
        response = self.request()
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('Account access denied', str(response.data))
        create.assert_not_called()
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.stripe_account_id, 'acct_real_existing')
