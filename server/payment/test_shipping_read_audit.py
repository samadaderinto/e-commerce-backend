from __future__ import annotations

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import User
from payment.models import Order


@override_settings(ROOT_URLCONF='storefront.urls')
class ShippingReadAuditTests(TestCase):
    def setUp(self) -> None:
        self.buyer = User.objects.create_user(email='shipping-buyer@test.local', password='test')
        self.order = Order.objects.create(user=self.buyer, status='confirmed', ordered=True)
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)
        self.url = f'/api/v1/orders/{self.order.pk}/tracking/'

    def test_unassigned_carrier_is_not_reported_as_usps(self) -> None:
        Order.objects.filter(pk=self.order.pk).update(carrier='')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['carrier'], '')
        self.assertEqual(response.data['tracking_url'], '')

    def test_business_admin_can_read_tracking_without_redundant_staff_flag(self) -> None:
        admin = User.objects.create_user(
            email='shipping-admin@test.local', password='test',
            is_business_admin=True, is_staff=False,
        )
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_unrelated_buyer_cannot_read_tracking(self) -> None:
        other = User.objects.create_user(email='shipping-other@test.local', password='test')
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
