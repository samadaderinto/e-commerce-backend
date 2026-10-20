from __future__ import annotations

from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import Refund, User
from payment.models import Order


@override_settings(ROOT_URLCONF='storefront.urls')
class RefundEditAuditTests(TestCase):
    def setUp(self) -> None:
        self.buyer = User.objects.create_user(email='refund-edit@test.local', password='test')
        self.order = Order.objects.create(
            user=self.buyer, ordered=True, status='confirmed',
            paid_total=Decimal('20'), total=Decimal('20'),
            items_snapshot=[{'product': 1, 'is_digital': False, 'quantity': 1, 'line_total': '20.00'}],
        )
        self.refund = Refund.objects.create(
            order=self.order, email=self.buyer.email, reason='Item damaged',
            refund_type='original_payment', refund_amount=Decimal('20'),
            selected_items=self.order.items_snapshot, provider_reference='re_fixture_processing',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)
        self.url = f'/api/v1/orders/{self.order.pk}/refund/'

    def test_processing_refund_cannot_be_edited_or_redirected_to_wallet(self) -> None:
        for method in ('patch', 'put'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self.url, {'refund_type': 'store_credit'}, format='json',
                )
                self.assertEqual(response.status_code, 400)
                self.refund.refresh_from_db()
                self.assertEqual(self.refund.refund_type, 'original_payment')
                self.assertEqual(self.refund.provider_reference, 're_fixture_processing')

    def test_ordinary_pending_request_remains_editable(self) -> None:
        Refund.objects.filter(pk=self.refund.pk).update(provider_reference='')
        response = self.client.patch(self.url, {'reason': 'item_missing'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.refund.refresh_from_db()
        self.assertEqual(self.refund.reason, 'Item missing')

    def test_processing_request_is_reported_as_pending_but_not_editable(self) -> None:
        response = self.client.get(self.url)
        self.assertTrue(response.data['is_pending'])
        self.assertFalse(response.data['is_editable'])
        detail = self.client.get(f'/api/v1/orders/{self.order.pk}/')
        self.assertFalse(detail.data['active_refund']['is_editable'])

    def test_another_customer_cannot_edit_processing_refund(self) -> None:
        other = User.objects.create_user(email='refund-edit-other@test.local', password='test')
        self.client.force_authenticate(other)
        self.assertEqual(self.client.patch(self.url, {}, format='json').status_code, 404)
