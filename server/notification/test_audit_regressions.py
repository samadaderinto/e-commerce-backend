"""Regression coverage for notification visibility, identity and commit safety."""
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Refund, User
from notification.delivery import queue_email_delivery, queue_push_delivery
from notification.domain import refund_notice
from notification.events import order_changed
from notification.models import Notification, NotificationDelivery
from notification.views import create_notification
from payment.models import Order
from product.models import Product
from store.models import Store


@override_settings(ROOT_URLCONF="notification.tests")
class NotificationAuditRegressions(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(email="notification-admin@test.com", password="test")
        self.buyer = User.objects.create_user(email="notification-buyer@test.com", password="test")
        self.owner = User.objects.create_user(email="notification-owner@test.com", password="test")
        self.other = User.objects.create_user(email="notification-other@test.com", password="test")
        self.store = Store.objects.create(user=self.owner, name="Independent")
        self.foreign = Store.objects.create(user=self.other, name="Foreign")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.order = Order.objects.create(
            user=self.buyer, status="confirmed", ordered=True,
            items_snapshot=[{"store": self.store.pk}, {"store": self.foreign.pk}],
        )

    def test_order_store_visibility_and_unique_recipient_identity(self) -> None:
        with patch("notification.delivery._dispatch_delivery"):
            order_changed(Order, self.order, created=True)
        for recipient in [self.admin, self.buyer, self.owner, self.other]:
            self.assertEqual(Notification.objects.filter(recipient=recipient, data__event="order_placed", data__order_id=self.order.pk).count(), 1)
        own = Notification.objects.get(recipient=self.owner, data__event="order_placed")
        self.assertEqual(set(own.stores.values_list("pk", flat=True)), {self.store.pk})
        response = self.client.get("/notifications/", {"store": self.store.pk, "search": self.order.orderId})
        self.assertEqual(response.data["count"], 1)
        self.assertIn(self.store.pk, [row["id"] for row in self.client.get("/notifications/filters/").data["stores"]])

    def test_archived_combines_search_category_store_and_state(self) -> None:
        notification = Notification.objects.get(recipient=self.admin, data__event="order_placed")
        notification.deleted = True
        notification.save()
        for params, count in [
            ({"search": self.order.orderId, "category": "order", "store": self.store.pk, "state": "unread"}, 1),
            ({"search": "not present"}, 0),
            ({"category": "refund"}, 0),
            ({"state": "read"}, 0),
        ]:
            self.assertEqual(self.client.get("/notifications/archived/", params).data["count"], count)

    def test_refund_selected_stores_and_reviewers_and_buyer(self) -> None:
        refund = Refund.objects.create(order=self.order, email=self.buyer.email, reason="Selected return")
        refund_notice(refund, self.buyer, [{"store": self.store.pk}])
        notices = Notification.objects.filter(data__refund_id=refund.pk, data__event="refund_requested")
        self.assertEqual(set(notices.values_list("recipient_id", flat=True)), {self.admin.pk, self.buyer.pk, self.owner.pk})
        self.assertFalse(notices.filter(recipient=self.other).exists())
        self.assertFalse(notices.filter(stores=self.foreign).exists())
        self.assertFalse(NotificationDelivery.objects.filter(notification__in=notices, recipient=self.buyer).exists())

    def test_domain_failure_rolls_back_record_and_partial_notifications(self) -> None:
        before = Notification.objects.count()
        with patch("notification.views._send_external_notification", side_effect=RuntimeError("outbox failed")):
            with self.assertRaises(RuntimeError):
                Order.objects.create(user=self.buyer, status="confirmed", ordered=True)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), before)
        with transaction.atomic():
            create_notification(self.buyer, "Rollback", data={"event": "password_changed"})
            transaction.set_rollback(True)
        self.assertFalse(Notification.objects.filter(verb="Rollback").exists())

    def test_delivery_channel_identity_and_authoritative_links(self) -> None:
        notification = Notification.objects.get(recipient=self.buyer, data__event="order_placed")
        self.assertEqual(notification.data["url"], f"/orders/{self.order.pk}")
        first = queue_email_delivery(self.buyer.email, "First", "Body", notification=notification)
        second = queue_email_delivery(self.buyer.email, "Duplicate", "Body", notification=notification)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(queue_push_delivery(notification).pk, queue_push_delivery(notification).pk)
        from utils.functions import send_mail
        send_mail("order-summary", self.buyer.email, {"orderId": self.order.orderId})
        body = NotificationDelivery.objects.filter(recipient_email=self.buyer.email, is_html=True).latest("pk").body
        self.assertIn(f"/orders/{self.order.pk}", body)
        self.assertNotIn(f"/account/orders/{self.order.orderId}", body)

    def test_wallet_category_is_consistent_in_filters_and_serialization(self) -> None:
        notice = create_notification(self.admin, "Wallet funded", data={"category": "wallet", "event": "wallet_topup"})
        response = self.client.get("/notifications/", {"category": "wallet"})
        self.assertEqual([row["id"] for row in response.data["results"]], [notice.pk])
        categories = self.client.get("/notifications/filters/").data["categories"]
        self.assertEqual(next(row["count"] for row in categories if row["id"] == "wallet"), 1)

    def test_low_inventory_notice_exists_before_commit_and_dispatch_waits(self) -> None:
        with patch("notification.delivery._dispatch_delivery") as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                product = Product.objects.create(store=self.store, title="Low item", price=10, discount=0, available=1)
                self.assertTrue(Notification.objects.filter(data__event="inventory_low", data__product_id=product.pk).exists())
                dispatch.assert_not_called()
            self.assertTrue(dispatch.called)
