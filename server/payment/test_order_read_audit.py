from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import patch

from django.db.models import QuerySet
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import User
from payment.models import Order


@override_settings(ROOT_URLCONF='storefront.urls')
class OrderReadAuditTests(TestCase):
    def setUp(self) -> None:
        self.buyer = User.objects.create_user(email='order-read-buyer@test.local', password='test')
        self.order = Order.objects.create(
            user=self.buyer, status='confirmed', ordered=True,
            total=Decimal('10.00'), paid_total=Decimal('10.00'),
            items_snapshot=[{'title': 'Archived Handbook', 'is_digital': True, 'quantity': 1}],
        )
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)

    def test_order_read_does_not_overwrite_a_concurrent_refund(self) -> None:
        original_first = QuerySet.first
        interleaved: bool = False

        def first_after_refund(records: QuerySet[Any]) -> Any:
            nonlocal interleaved
            result = original_first(records)
            if records.model is Order and isinstance(result, Order) and not interleaved:
                interleaved = True
                Order.objects.filter(pk=self.order.pk).update(status='refunded')
            return result

        with patch('django.db.models.query.QuerySet.first', new=first_after_refund):
            response = self.client.get(f'/api/v1/orders/{self.order.pk}/')
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'refunded')
        self.assertEqual(response.data['status'], 'refunded')

    def test_search_uses_recorded_item_titles_without_live_cart_rows(self) -> None:
        for title in ('Archived Handbook', 'Café Workbook'):
            with self.subTest(title=title):
                Order.objects.filter(pk=self.order.pk).update(
                    items_snapshot=[{'title': title, 'is_digital': True}],
                )
                response = self.client.get('/api/v1/orders/', {
                    'paginated': '1', 'search': title,
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['count'], 1)

    def test_unrelated_customer_cannot_read_order(self) -> None:
        other = User.objects.create_user(email='order-other-buyer@test.local', password='test')
        self.client.force_authenticate(other)
        response = self.client.get(f'/api/v1/orders/{self.order.pk}/')
        self.assertEqual(response.status_code, 404)

    def test_business_admin_order_access_does_not_require_redundant_staff_flag(self) -> None:
        admin = User.objects.create_user(
            email='order-business-admin@test.local', password='test',
            is_business_admin=True, is_staff=False,
        )
        self.client.force_authenticate(admin)
        response = self.client.get(f'/api/v1/orders/{self.order.pk}/')
        self.assertEqual(response.status_code, 200)
