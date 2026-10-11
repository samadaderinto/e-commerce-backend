"""Real checkout contention against an isolated PostgreSQL test database."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4

from django.apps import apps
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from cart.models import Cart, CartItem
from core.models import Address, User
from payment.models import Order
from product.models import Product
from store.models import Store, StoreAddress


@skipUnless(
    connection.vendor == "postgresql", "Row-lock contention requires PostgreSQL."
)
@override_settings(ROOT_URLCONF="storefront.urls", SHIPPING_RATE_MODE="demo")
class InventoryCheckoutConcurrencyTests(TransactionTestCase):
    available_apps = [config.name for config in apps.get_app_configs()]

    def test_twenty_buyers_cannot_purchase_more_than_five_units(self) -> None:
        seller = User.objects.create_user(
            email="inventory-seller@test.com", password="test-password"
        )
        store = Store.objects.create(
            user=seller,
            name="Inventory test store",
            status=Store.STATUS_ACTIVE,
            verified_at=timezone.now(),
        )
        location = {
            "address": "1 Test Street",
            "city": "Tampa",
            "state": "FL",
            "country": "US",
            "zip": "33602",
        }
        StoreAddress.objects.create(store=store, is_default=True, **location)
        product = Product.objects.create(
            store=store,
            title="Limited inventory",
            price="10.00",
            available=5,
            discount=0,
        )
        buyers: list[tuple[int, int]] = []
        for index in range(20):
            buyer = User.objects.create_user(
                email=f"inventory-buyer-{index}@test.com",
                password="test-password",
            )
            address = Address.objects.create(user=buyer, **location)
            cart = Cart.objects.create(user=buyer)
            CartItem.objects.create(cart=cart, product=product, quantity=1)
            buyers.append((buyer.pk, address.pk))
        barrier = Barrier(20)

        def checkout(fixture: tuple[int, int]) -> int:
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=fixture[0]))
                barrier.wait(timeout=30)
                response = client.post(
                    "/api/v1/checkout/",
                    {
                        "checkout_key": str(uuid4()),
                        "address": fixture[1],
                        "payment_type": "cash_on_delivery",
                    },
                    format="json",
                )
                return response.status_code
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=20) as pool:
            statuses = list(pool.map(checkout, buyers))
        self.assertEqual(statuses.count(201), 5, statuses)
        self.assertEqual(statuses.count(400), 15, statuses)
        product.refresh_from_db()
        self.assertEqual(product.available, 0)
        self.assertEqual(product.sales, 5)
        self.assertEqual(Order.objects.count(), 5)
