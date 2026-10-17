from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.models import Address, Refund, User, UserWallet
from core.services import credit_user_wallet, get_or_create_user_wallet
from payment.models import DeliveryInfo, Order, OrderFulfillment
from payment.services import (
    decline_order_refund,
    execute_order_status_transition,
    process_order_refund,
)
from product.models import Product
from store.models import MerchantWallet, Store, StoreEarningsLedger
from store.services import get_or_create_merchant_wallet


class PaymentRefundAndTransitionServiceTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_staffuser(
            email="staff.tester@example.com",
            password="Password123!",
        )
        self.merchant_user = User.objects.create_user(
            email="merchant.tester@example.com",
            password="Password123!",
        )
        self.customer = User.objects.create_user(
            email="customer.tester@example.com",
            password="Password123!",
        )
        self.store = Store.objects.create(
            user=self.merchant_user,
            name="Test Gadgets",
            username="test-gadgets",
            status=Store.STATUS_ACTIVE,
            verified_at=timezone.now(),
        )
        self.product = Product.objects.create(
            store=self.store,
            title="Mechanical Keyboard",
            price=Decimal("100.00"),
            discount=0,
            available=5,
            sales=2,
            is_digital=False,
            visibility=True,
        )
        self.digital_product = Product.objects.create(
            store=self.store,
            title="Typing Master Guide",
            price=Decimal("20.00"),
            discount=0,
            available=0,
            sales=10,
            is_digital=True,
            visibility=True,
        )
        self.address = Address.objects.create(
            user=self.customer,
            address="123 Commerce St",
            city="New York",
            state="NY",
            zip="10001",
            country="US",
        )
        self.delivery = DeliveryInfo.objects.create(
            user=self.customer,
            address=self.address,
            method="home delivery",
            delivery_type="standard",
            total=Decimal("10.00"),
        )
        self.merchant_wallet = get_or_create_merchant_wallet(self.merchant_user)

    def _create_order(self, payment_type="user_wallet", stripe_session_id=None, status="confirmed"):
        order = Order.objects.create(
            user=self.customer,
            delivery=self.delivery,
            status=status,
            ordered=True,
            payment_type=payment_type,
            stripe_session_id=stripe_session_id,
            total=Decimal("110.00"),
            paid_total=Decimal('110.00'),
            wallet_paid=Decimal('110.00') if payment_type in {'user_wallet', 'wallet'} else Decimal('0'),
            subtotal=Decimal("100.00"),
            items_snapshot=[
                {
                    "product": self.product.pk,
                    "store": self.store.pk,
                    "title": self.product.title,
                    "quantity": 1,
                    "unit_price": "100.00",
                    "is_digital": False,
                }
            ],
        )
        StoreEarningsLedger.objects.create(
            wallet=self.merchant_wallet,
            store=self.store,
            order=order,
            entry_type=StoreEarningsLedger.TYPE_SALE,
            gross_amount=Decimal("100.00"),
            fee_amount=Decimal("4.00"),
            net_amount=Decimal("96.00"),
            status=StoreEarningsLedger.STATUS_AVAILABLE,
            description=f"Order {order.orderId} sales",
            reference=f"SALE-{order.orderId}",
        )
        self.merchant_wallet.available_balance += Decimal("96.00")
        self.merchant_wallet.save()
        return order

    @patch('payment.services.call_stripe_refund', return_value='re_split')
    def test_split_tender_refund_restores_original_wallet_and_card_portions(self, stripe_refund) -> None:
        from payment.models import CheckoutAttempt
        from uuid import uuid4
        order = self._create_order(payment_type='split_tender', stripe_session_id='cs_split_refund')
        order.wallet_paid = Decimal('30')
        order.save(update_fields=['wallet_paid'])
        CheckoutAttempt.objects.create(user=self.customer, checkout_key=uuid4(), session_id=order.stripe_session_id, wallet_amount=30, status='completed', expires_at=timezone.now())
        refund = Refund.objects.create(email=self.customer.email, order=order, reason='Return', refund_type=Refund.REFUND_TYPE_ORIGINAL_PAYMENT)
        process_order_refund(refund, self.staff)
        self.assertEqual(stripe_refund.call_args.kwargs['amount'], Decimal('80'))
        self.assertEqual(UserWallet.objects.get(user=self.customer).balance, Decimal('30'))

    def test_original_payment_refund_for_user_wallet_credits_wallet_and_reverses_ledger(self):
        order = self._create_order(payment_type="user_wallet")
        refund = Refund.objects.create(
            email=self.customer.email,
            order=order,
            reason="Item defective",
            refund_type=Refund.REFUND_TYPE_ORIGINAL_PAYMENT,
        )

        customer_wallet = get_or_create_user_wallet(self.customer)
        initial_balance = customer_wallet.balance

        processed = process_order_refund(refund, self.staff)

        self.assertEqual(processed.status, Refund.STATUS_APPROVED)
        self.assertTrue(processed.accepted)
        self.assertTrue(processed.provider_reference.startswith("WALLET-TX-"))

        order.refresh_from_db()
        self.assertEqual(order.status, "refunded")

        # Customer wallet received credit
        customer_wallet.refresh_from_db()
        self.assertEqual(customer_wallet.balance, initial_balance + Decimal("110.00"))

        # Merchant ledger is reversed and merchant balance deducted
        self.merchant_wallet.refresh_from_db()
        self.assertEqual(self.merchant_wallet.available_balance, Decimal("0.00"))
        ledger_entry = StoreEarningsLedger.objects.get(order=order, entry_type=StoreEarningsLedger.TYPE_SALE)
        self.assertEqual(ledger_entry.status, StoreEarningsLedger.STATUS_REVERSED)

    def test_store_credit_refund_credits_wallet_and_reverses_ledger(self):
        order = self._create_order(payment_type="card")
        refund = Refund.objects.create(
            email=self.customer.email,
            order=order,
            reason="Customer changed mind",
            refund_type=Refund.REFUND_TYPE_STORE_CREDIT,
        )

        customer_wallet = get_or_create_user_wallet(self.customer)
        initial_balance = customer_wallet.balance

        processed = process_order_refund(refund, self.staff)

        self.assertEqual(processed.status, Refund.STATUS_APPROVED)
        self.assertTrue(processed.provider_reference.startswith("WALLET-TX-"))

        customer_wallet.refresh_from_db()
        self.assertEqual(customer_wallet.balance, initial_balance + Decimal("110.00"))

        order.refresh_from_db()
        self.assertEqual(order.status, "refunded")

        self.merchant_wallet.refresh_from_db()
        self.assertEqual(self.merchant_wallet.available_balance, Decimal("0.00"))

    @patch("payment.services.call_stripe_refund")
    def test_original_payment_refund_stripe_success(self, mock_stripe):
        mock_stripe.return_value = "re_test_12345"
        order = self._create_order(payment_type="stripe_wallet", stripe_session_id="cs_test_999")
        refund = Refund.objects.create(
            email=self.customer.email,
            order=order,
            reason="Did not arrive",
            refund_type=Refund.REFUND_TYPE_ORIGINAL_PAYMENT,
        )

        processed = process_order_refund(refund, self.staff)

        self.assertEqual(processed.status, Refund.STATUS_APPROVED)
        self.assertEqual(processed.provider_reference, "re_test_12345")
        mock_stripe.assert_called_once()

        order.refresh_from_db()
        self.assertEqual(order.status, "refunded")

        self.merchant_wallet.refresh_from_db()
        self.assertEqual(self.merchant_wallet.available_balance, Decimal("0.00"))

    @patch("payment.services.call_stripe_refund")
    def test_original_payment_refund_stripe_failure_marks_failed_and_preserves_order_and_ledger(self, mock_stripe):
        mock_stripe.side_effect = Exception("Stripe card error: Charge already refunded")
        order = self._create_order(payment_type="stripe_wallet", stripe_session_id="cs_test_999")
        refund = Refund.objects.create(
            email=self.customer.email,
            order=order,
            reason="Did not arrive",
            refund_type=Refund.REFUND_TYPE_ORIGINAL_PAYMENT,
        )

        with self.assertRaises(ValidationError) as ctx:
            process_order_refund(refund, self.staff)

        self.assertIn("Payment provider refund failed", str(ctx.exception))

        refund.refresh_from_db()
        self.assertEqual(refund.status, Refund.STATUS_FAILED)
        self.assertNotIn("Stripe card error", refund.failure_reason)
        self.assertNotIn("Stripe card error", str(ctx.exception))

        order.refresh_from_db()
        self.assertEqual(order.status, "confirmed")  # order NOT refunded!

        # Merchant ledger NOT reversed!
        self.merchant_wallet.refresh_from_db()
        self.assertEqual(self.merchant_wallet.available_balance, Decimal("96.00"))
        ledger_entry = StoreEarningsLedger.objects.get(order=order)
        self.assertEqual(ledger_entry.status, StoreEarningsLedger.STATUS_AVAILABLE)

    def test_decline_order_refund_restores_order_status_if_refund_requested(self):
        order = self._create_order(status="refund_requested")
        refund = Refund.objects.create(
            email=self.customer.email,
            order=order,
            reason="Frivolous return",
        )

        declined = decline_order_refund(refund, self.staff, reason="Item is digital and already consumed.")

        self.assertEqual(declined.status, Refund.STATUS_DECLINED)
        self.assertFalse(declined.accepted)

        order.refresh_from_db()
        self.assertEqual(order.status, "confirmed")

    def test_order_status_override_cancel_restores_physical_inventory_and_reverses_ledger(self):
        order = self._create_order(payment_type="user_wallet")
        initial_available = self.product.available
        initial_sales = self.product.sales

        customer_wallet = get_or_create_user_wallet(self.customer)
        initial_balance = customer_wallet.balance

        updated = execute_order_status_transition(
            order=order,
            next_status="cancelled",
            actor=self.staff,
            reason="Customer cancelled before dispatch by phone request.",
        )

        self.assertEqual(updated.status, "cancelled")

        # Inventory is restored!
        self.product.refresh_from_db()
        self.assertEqual(self.product.available, initial_available + 1)
        self.assertEqual(self.product.sales, initial_sales - 1)

        # Merchant ledger is reversed!
        self.merchant_wallet.refresh_from_db()
        self.assertEqual(self.merchant_wallet.available_balance, Decimal("0.00"))

        # Customer wallet is refunded!
        customer_wallet.refresh_from_db()
        self.assertEqual(customer_wallet.balance, initial_balance + Decimal("110.00"))

    def test_order_status_override_cannot_cancel_after_physical_fulfillment(self):
        order = self._create_order(payment_type="user_wallet", status="shipped")
        order.shipped_at = timezone.now()
        order.save(update_fields=["shipped_at"])
        fulfillment = OrderFulfillment.objects.create(
            order=order,
            store=self.store,
            status="shipped",
            shipped_at=order.shipped_at,
        )
        initial_available = self.product.available
        initial_balance = get_or_create_user_wallet(self.customer).balance

        with self.assertRaises(ValidationError):
            execute_order_status_transition(
                order=order,
                next_status="cancelled",
                actor=self.staff,
                reason="Attempted cancellation after dispatch.",
            )

        order.refresh_from_db()
        fulfillment.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, "shipped")
        self.assertEqual(fulfillment.status, "shipped")
        self.assertEqual(self.product.available, initial_available)
        self.assertEqual(get_or_create_user_wallet(self.customer).balance, initial_balance)

    def test_order_status_override_cannot_cancel_instant_digital_order(self):
        digital_product = Product.objects.create(
            store=self.store,
            title="Digital order",
            price=Decimal("100.00"),
            discount=0,
            available=0,
            is_digital=True,
        )
        order = self._create_order(payment_type="user_wallet")
        order.items_snapshot = [
            {
                "product": digital_product.pk,
                "store": self.store.pk,
                "title": digital_product.title,
                "quantity": 1,
                "unit_price": "100.00",
                "is_digital": True,
            }
        ]
        order.status = "delivered"
        order.save(update_fields=["items_snapshot", "status"])
        initial_balance = get_or_create_user_wallet(self.customer).balance

        with self.assertRaises(ValidationError):
            execute_order_status_transition(
                order=order,
                next_status="cancelled",
                actor=self.staff,
                reason="Attempted cancellation after digital delivery.",
            )

        order.refresh_from_db()
        self.assertEqual(order.status, "delivered")
        self.assertEqual(get_or_create_user_wallet(self.customer).balance, initial_balance)

    def test_order_status_override_backward_clears_timestamps(self):
        order = self._create_order(status="shipped")
        now = timezone.now()
        order.shipped_at = now
        order.delivered_at = now
        order.status = "delivered"
        order.save()

        # Step 1: Rollback delivered -> shipped
        updated = execute_order_status_transition(
            order=order,
            next_status="shipped",
            actor=self.staff,
            reason="Courier reported delivery mistake, package still in transit.",
        )
        self.assertEqual(updated.status, "shipped")
        self.assertIsNone(updated.delivered_at)
        self.assertIsNotNone(updated.shipped_at)

        # Step 2: Rollback shipped -> confirmed
        updated = execute_order_status_transition(
            order=updated,
            next_status="confirmed",
            actor=self.staff,
            reason="Dispatch label voided before carrier collected parcel.",
        )
        self.assertEqual(updated.status, "confirmed")
        self.assertIsNone(updated.shipped_at)
        self.assertIsNone(updated.delivered_at)

    def test_order_status_override_disallows_invalid_transitions(self):
        order = self._create_order(status="confirmed")

        # Cannot jump confirmed -> delivered directly
        with self.assertRaises(ValidationError) as ctx:
            execute_order_status_transition(
                order=order,
                next_status="delivered",
                actor=self.staff,
                reason="Skipping stages is not allowed.",
            )
        self.assertIn("Cannot transition order", str(ctx.exception))

        # Cannot transition to refunded through status override
        with self.assertRaises(ValidationError) as ctx:
            execute_order_status_transition(
                order=order,
                next_status="refunded",
                actor=self.staff,
                reason="Must use refund workflow.",
            )
        self.assertIn("Use the refund workflow", str(ctx.exception))

        # Once cancelled, cannot change status
        cancelled = execute_order_status_transition(
            order=order,
            next_status="cancelled",
            actor=self.staff,
            reason="Customer cancellation.",
        )
        with self.assertRaises(ValidationError) as ctx:
            execute_order_status_transition(
                order=cancelled,
                next_status="confirmed",
                actor=self.staff,
                reason="Attempting reactivation.",
            )
        self.assertIn("Cancelled orders cannot be modified", str(ctx.exception))


    def test_refund_decision_sends_one_html_email_to_buyer(self) -> None:
        from notification.models import NotificationDelivery

        order = self._create_order(payment_type="card")
        refund = Refund.objects.create(
            email=self.customer.email, order=order, reason="Return",
            refund_type=Refund.REFUND_TYPE_STORE_CREDIT,
        )
        with patch("notification.delivery._dispatch_delivery"), patch("notification.realtime.broker"), patch("notification.search.schedule_index_notification"):
            with self.captureOnCommitCallbacks(execute=True):
                process_order_refund(refund, self.staff)
        delivery = NotificationDelivery.objects.get(recipient=self.customer, subject__icontains="Refund Update")
        self.assertTrue(delivery.is_html)
        self.assertIn("Approved", delivery.body)
