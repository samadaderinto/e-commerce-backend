"""Bound order-list query growth without caching private commerce data."""

from __future__ import annotations

import json
from statistics import median
from time import perf_counter

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from cart.models import Cart, CartItem
from core.models import Refund, User
from payment.models import Order, OrderFulfillment
from product.models import Product
from store.models import Store


@override_settings(ROOT_URLCONF="storefront.urls")
class OrderListQueryTests(TestCase):
    def setUp(self) -> None:
        self.buyer = User.objects.create_user(
            email="latency-buyer@test.com", password="test"
        )
        self.seller = User.objects.create_user(
            email="latency-seller@test.com", password="test"
        )
        other = User.objects.create_user(
            email="latency-other@test.com", password="test"
        )
        self.store = Store.objects.create(
            user=self.seller,
            name="Query store",
            status="active",
            verified_at=timezone.now(),
        )
        self.other_store = Store.objects.create(
            user=other,
            name="Other query store",
            status="active",
            verified_at=timezone.now(),
        )
        snapshots = [
            {
                "product": 101,
                "store": self.store.pk,
                "title": "Own",
                "quantity": 1,
                "is_digital": False,
            },
            {
                "product": 102,
                "store": self.other_store.pk,
                "title": "Other",
                "quantity": 1,
                "is_digital": False,
            },
        ]
        orders = Order.objects.bulk_create(
            [
                Order(
                    user=self.buyer,
                    ordered=True,
                    status="confirmed",
                    total="20.00",
                    paid_total="20.00",
                    items_snapshot=snapshots,
                )
                for _ in range(20)
            ]
        )
        OrderFulfillment.objects.bulk_create(
            [
                OrderFulfillment(order=order, store=store, status="confirmed")
                for order in orders
                for store in [self.store, self.other_store]
            ]
        )
        Refund.objects.bulk_create(
            [
                Refund(
                    order=order,
                    email=self.buyer.email,
                    reason="Pending review",
                    status=status,
                    selected_items=[snapshots[0]],
                )
                for order in orders
                for status in ["declined", "pending"]
            ]
        )
        product = Product.objects.create(
            store=self.store, title="Legacy", price="10.00", discount=0, available=100
        )
        for _ in range(20):
            cart = Cart.objects.create(user=self.buyer, ordered=True)
            CartItem.objects.create(cart=cart, product=product, quantity=1)
            Order.objects.create(
                user=self.buyer,
                cart=cart,
                ordered=True,
                status="delivered",
                total="10.00",
                paid_total="10.00",
            )
        self.client = APIClient()

    def profile(self, path: str, status: str, limit: int) -> tuple[int, float]:
        counts: list[int] = []
        elapsed: list[float] = []
        for _ in range(5):
            with CaptureQueriesContext(connection) as queries:
                started = perf_counter()
                response = self.client.get(
                    path, {"paginated": "1", "status": status, "limit": limit}
                )
                elapsed.append((perf_counter() - started) * 1000)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(len(response.data["results"]), limit)
            counts.append(len(queries))
        return max(counts), round(median(elapsed), 2)

    def test_order_lists_have_bounded_query_growth(self) -> None:
        measurements: dict[str, dict[str, tuple[int, float]]] = {}
        for label, user, path, status in [
            ("customer", self.buyer, "/api/v1/orders/", "confirmed"),
            (
                "merchant_snapshot",
                self.seller,
                f"/api/v1/stores/{self.store.pk}/orders/",
                "confirmed",
            ),
            (
                "merchant_legacy",
                self.seller,
                f"/api/v1/stores/{self.store.pk}/orders/",
                "delivered",
            ),
        ]:
            self.client.force_authenticate(user)
            measurements[label] = {
                "one_row": self.profile(path, status, 1),
                "twenty_rows": self.profile(path, status, 20),
            }
        print("ORDER_QUERY_PROFILE " + json.dumps(measurements, sort_keys=True))
        budgets = {"customer": 5, "merchant_snapshot": 6, "merchant_legacy": 7}
        for label, results in measurements.items():
            with self.subTest(endpoint=label):
                self.assertLessEqual(results["twenty_rows"][0], budgets[label])
                self.assertLessEqual(
                    results["twenty_rows"][0], results["one_row"][0] + 1
                )

    def test_customer_refunds_are_fresh_and_owner_scoped(self) -> None:
        self.client.force_authenticate(self.buyer)
        params = {"paginated": "1", "status": "confirmed", "limit": 1}
        first = self.client.get("/api/v1/orders/", params)
        row = first.data["results"][0]
        self.assertEqual(row["active_refund"]["status"], "pending")
        self.assertEqual(row["claimed_product_ids"], [101])
        Refund.objects.filter(order_id=row["id"], status="pending").update(
            status="declined"
        )
        second = self.client.get("/api/v1/orders/", params)
        self.assertEqual(
            second.data["results"][0]["active_refund"]["status"], "declined"
        )
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.get("/api/v1/orders/", params).data["count"], 0)

    def test_snapshot_orders_do_not_load_current_cart_items(self) -> None:
        order = Order.objects.filter(status="confirmed").first()
        cart = Cart.objects.create(user=self.buyer, ordered=True)
        CartItem.objects.create(
            cart=cart, product=Product.objects.get(title="Legacy"), quantity=1
        )
        order.cart = cart
        order.save(update_fields=["cart"])
        self.client.force_authenticate(self.seller)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                f"/api/v1/stores/{self.store.pk}/orders/",
                {"status": "confirmed", "order_id": order.pk},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["items"][0]["title"], "Own")
        cart_selects = [
            query["sql"] for query in queries if 'FROM "cart_cartitem"' in query["sql"]
        ]
        self.assertEqual(cart_selects, [])
