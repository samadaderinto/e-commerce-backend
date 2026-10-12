"""Signed provider callbacks complete real orders without an enclosing test transaction."""

from typing import Any
from unittest.mock import patch
from uuid import uuid4

from django.core.cache import cache
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from cart.models import Cart, CartItem
from core.models import User
from payment.models import Order
from product.models import Product
from store.models import Store, StoreAddress


@override_settings(ROOT_URLCONF='storefront.urls', STRIPE_WEBHOOK_SECRET='whsec_audit')
class SignedWebhookTests(TransactionTestCase):
    def setUp(self) -> None:
        cache.clear()
        self.buyer = User.objects.create_user(email='hook-buyer@test.com', password='test')
        owner = User.objects.create_user(email='hook-owner@test.com', password='test')
        store = Store.objects.create(user=owner, name='Hook store', status='active', verified_at=timezone.now())
        StoreAddress.objects.create(store=store, address='1 Test St', city='Tampa', state='FL', country='US', zip='33602', is_default=True)
        self.product = Product.objects.create(store=store, title='Download', price=10, discount=0, available=1, is_digital=True, digital_file_url='digital_products/test.pdf')
        cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.product)
        self.client = APIClient()

    def tearDown(self) -> None:
        cache.clear()

    @patch('storefront.views.stripe.Webhook.construct_event')
    def test_signed_checkout_callback_commits_once_and_duplicate_is_idempotent(self, verify: Any) -> None:
        verify.return_value = {'type': 'checkout.session.completed', 'data': {'object': {
            'id': 'cs_signed_audit', 'payment_status': 'paid', 'currency': 'usd',
            'amount_total': 1000, 'client_reference_id': str(self.buyer.pk),
            'metadata': {'checkout_key': str(uuid4())},
        }}}
        for _ in range(2):
            response = self.client.post('/api/v1/stripe/webhook/', {}, format='json', HTTP_STRIPE_SIGNATURE='verified-by-mocked-provider')
            self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Order.objects.filter(user=self.buyer, ordered=True).count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.sales, 1)
