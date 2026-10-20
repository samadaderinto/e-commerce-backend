from __future__ import annotations

from decimal import Decimal

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from core.models import User
from core.services import credit_user_wallet


@override_settings(ROOT_URLCONF='storefront.urls')
class ListingPaginationAuditTests(TestCase):
    def setUp(self) -> None:
        user = User.objects.create_user(email='listing-buyer@test.local', password='test')
        credit_user_wallet(user, Decimal('10.00'), 'Test credit')
        self.client = APIClient()
        self.client.force_authenticate(user)

    def test_extreme_offsets_are_rejected_before_database_slicing(self) -> None:
        for endpoint in ('wallet', 'orders'):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(
                    f'/api/v1/{endpoint}/?offset=999999999999999999999999999999',
                )
                self.assertEqual(response.status_code, 400)

    def test_wallet_beyond_end_preserves_balance_and_avoids_offset_query(self) -> None:
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/api/v1/wallet/?offset=2147483647')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['balance'], '10.00')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['transactions'], [])
        self.assertFalse(any('OFFSET' in query['sql'].upper() for query in queries))
