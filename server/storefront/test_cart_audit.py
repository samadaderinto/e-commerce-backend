from __future__ import annotations

from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from cart.models import Cart, CartItem
from core.models import User
from product.models import Product
from store.models import Store


@override_settings(ROOT_URLCONF='storefront.urls')
class CartAuditTests(TestCase):
    def setUp(self) -> None:
        owner = User.objects.create_user(email='cart-owner@test.local', password='test')
        buyer = User.objects.create_user(email='cart-buyer@test.local', password='test')
        store = Store.objects.create(
            user=owner, name='Cart test', status=Store.STATUS_ACTIVE,
            verified_at=timezone.now(),
        )
        self.product = Product.objects.create(
            store=store, title='Price changed after saving', price=Decimal('10.00'),
            discount=0, available=5,
        )
        self.cart = Cart.objects.create(user=buyer)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        self.client = APIClient()
        self.client.force_authenticate(buyer)

    def test_invalid_current_price_does_not_make_existing_cart_unreadable(self) -> None:
        Product.objects.filter(pk=self.product.pk).update(price=Decimal('0.01'), discount=60)
        response = self.client.get('/api/v1/cart/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['items'][0]['purchasable'])

    def test_other_item_can_be_removed_while_invalid_price_item_remains(self) -> None:
        second = Product.objects.create(
            store=self.product.store, title='Removable', price=Decimal('10.00'),
            discount=0, available=5,
        )
        CartItem.objects.create(cart=self.cart, product=second, quantity=1)
        Product.objects.filter(pk=self.product.pk).update(price=Decimal('0.01'), discount=60)
        response = self.client.delete(f'/api/v1/cart/?product={second.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.cart.cart_items.filter(product=second).exists())

    def test_invalid_price_still_rejects_additions_without_changing_quantity(self) -> None:
        Product.objects.filter(pk=self.product.pk).update(price=Decimal('0.01'), discount=60)
        response = self.client.post('/api/v1/cart/', {
            'product': self.product.pk, 'quantity': 1,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.cart.cart_items.get(product=self.product).quantity, 1)
