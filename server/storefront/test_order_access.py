"""Order visibility errors stay uniform without exposing another buyer's identity."""
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import User
from payment.models import Order


class OrderAccessTests(TestCase):
    def test_missing_and_foreign_orders_share_the_same_safe_response(self) -> None:
        owner = User.objects.create_user(email="order-owner@test.com", password="test")
        other = User.objects.create_user(email="order-other@test.com", password="test")
        order = Order.objects.create(user=owner, buyer_email=owner.email)
        client = APIClient()
        client.force_authenticate(other)
        foreign = client.get(f"/api/v1/orders/{order.pk}/")
        missing = client.get("/api/v1/orders/9999999/")
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(foreign.data, missing.data)
        self.assertIn("isn’t available to your account", str(foreign.data))
        self.assertNotIn(owner.email, str(foreign.data))
        self.assertNotIn("matches the given query", str(foreign.data))
        client.force_authenticate(owner)
        self.assertEqual(client.get(f"/api/v1/orders/{order.pk}/").status_code, 200)
        client.force_authenticate(None)
        self.assertEqual(client.get(f"/api/v1/orders/{order.pk}/").status_code, 401)
