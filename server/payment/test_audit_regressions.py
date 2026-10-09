"""Endpoint and accounting regressions for the October commerce audit."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Callable
from unittest import skipUnless
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.apps import apps
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.test import APIClient

from affiliates.models import Marketer
from core.models import Address, Refund, User, UserWallet, UserWalletTransaction
from core.services import credit_user_wallet
from payment.accounting import allocate_amount
from payment.funding import confirm_funding, recover_wallet_funding
from payment.models import Coupon, Order, TaxJurisdiction, WalletFundingAttempt
from payment.services import execute_order_status_transition, process_order_refund
from payment.tax import LocalTaxProvider
from product.models import Product
from store.models import Store, StoreAddress, StoreEarningsLedger
from store.services import calculate_merchant_financials


@override_settings(ROOT_URLCONF="storefront.urls", STRIPE_SECRET="sk_audit")
class AuditRegressionTests(TestCase):
    def setUp(self) -> None:
        self.buyer = User.objects.create_user(
            email="audit-buyer@test.com", password="test-password"
        )
        self.seller = User.objects.create_user(
            email="audit-seller@test.com", password="test-password"
        )
        self.store = Store.objects.create(
            user=self.seller,
            name="Audit store",
            status="active",
            verified_at=timezone.now(),
        )
        StoreAddress.objects.create(
            store=self.store,
            address="1 Main St",
            city="Tampa",
            state="FL",
            country="US",
            zip="33602",
            is_default=True,
        )
        self.product = Product.objects.create(
            store=self.store,
            title="Audit item",
            price=Decimal("100"),
            discount=0,
            available=10,
        )
        self.address = Address.objects.create(
            user=self.buyer,
            address="1 Test Street",
            city="Tampa",
            state="FL",
            country="US",
            zip="33602",
            is_default=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)
        credit_user_wallet(self.buyer, Decimal("1000"), "Initial test funds")

    def checkout(
        self, payment_type: str = "user_wallet", coupon: str = "", add_item: bool = True
    ) -> Order:
        if add_item:
            response = self.client.post(
                "/api/v1/cart/",
                {"product": self.product.pk, "quantity": 1},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)
        response = self.client.post(
            "/api/v1/checkout/",
            {
                "checkout_key": str(uuid4()),
                "address": self.address.pk,
                "payment_type": payment_type,
                "coupon": coupon,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return Order.objects.get(pk=response.data["id"])

    def request_refund(self, order: Order, product: Product | None = None) -> Refund:
        response = self.client.post(
            f"/api/v1/orders/{order.pk}/refund/",
            {
                "reason": "item_damaged",
                "product_ids": [(product or self.product).pk],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return Refund.objects.get(pk=response.data["refund_id"])

    def cancel(self, order: Order) -> Response:
        return self.client.post(f"/api/v1/orders/{order.pk}/cancel/", {}, format="json")

    def test_unpaid_cod_cancellation_cannot_mint_credit_or_earnings(self) -> None:
        order = self.checkout("cash_on_delivery")
        self.assertEqual(order.paid_total, Decimal("0"))
        self.assertFalse(StoreEarningsLedger.objects.filter(order=order).exists())
        self.assertEqual(
            Decimal(calculate_merchant_financials(self.seller)["total_net_sales"]),
            Decimal("0"),
        )
        self.assertEqual(self.cancel(order).status_code, 200)
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance, Decimal("1000")
        )
        self.assertEqual(
            Decimal(calculate_merchant_financials(self.seller)["total_net_sales"]),
            Decimal("0"),
        )

    def test_unpaid_cod_refund_request_and_approval_are_rejected(self) -> None:
        order = self.checkout("cash_on_delivery")
        response = self.client.post(
            f"/api/v1/orders/{order.pk}/refund/",
            {"reason": "item_damaged", "product_ids": [self.product.pk]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        refund = Refund.objects.create(
            order=order, email=self.buyer.email, reason="Unpaid return"
        )
        with self.assertRaises(ValidationError):
            process_order_refund(refund, self.seller)
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance, Decimal("1000")
        )

    def test_cod_cannot_unlock_digital_products(self) -> None:
        self.product.is_digital = True
        self.product.save()
        self.client.post(
            "/api/v1/cart/", {"product": self.product.pk, "quantity": 1}, format="json"
        )
        response = self.client.post(
            "/api/v1/checkout/",
            {"checkout_key": str(uuid4()), "payment_type": "cash_on_delivery"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_legacy_unpaid_confirmed_digital_order_cannot_download(self) -> None:
        self.product.is_digital = True
        self.product.save()
        order = Order.objects.create(
            user=self.buyer,
            status="confirmed",
            ordered=True,
            total=100,
            items_snapshot=[{"product": self.product.pk, "is_digital": True}],
        )
        response = self.client.get(
            f"/api/v1/orders/{order.pk}/downloads/{self.product.pk}/"
        )
        self.assertEqual(response.status_code, 404)

    def test_customer_cancellation_reverses_wallet_ledger_and_variant_once(
        self,
    ) -> None:
        self.product.variants = [{"name": "Large", "available": 3, "price_delta": "0"}]
        self.product.save()
        self.client.post(
            "/api/v1/cart/",
            {"product": self.product.pk, "variant": "Large", "quantity": 1},
            format="json",
        )
        order = self.checkout(add_item=False)
        self.assertEqual(self.cancel(order).status_code, 200)
        self.assertEqual(self.cancel(order).status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.available, 10)
        self.assertEqual(self.product.variants[0]["available"], 3)
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance, Decimal("1000")
        )
        self.assertEqual(
            StoreEarningsLedger.objects.get(order=order, entry_type="sale").status,
            StoreEarningsLedger.STATUS_REVERSED,
        )
        self.assertEqual(
            UserWalletTransaction.objects.filter(
                idempotency_key=f"cancel-{order.pk}-wallet"
            ).count(),
            1,
        )
        self.assertEqual(
            Decimal(calculate_merchant_financials(self.seller)["total_net_sales"]),
            Decimal("0"),
        )

    def test_cancel_closes_pending_refund_and_blocks_second_credit(self) -> None:
        order = self.checkout()
        refund = self.request_refund(order)
        self.assertEqual(self.cancel(order).status_code, 200)
        refund.refresh_from_db()
        self.assertEqual(refund.status, Refund.STATUS_DECLINED)
        with self.assertRaises(ValidationError):
            process_order_refund(refund, self.seller)
        self.product.refresh_from_db()
        self.assertEqual(self.product.available, 10)
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance, Decimal("1000")
        )

    def test_duplicate_pending_and_failed_refund_claims_are_rejected(self) -> None:
        order = self.checkout()
        refund = self.request_refund(order)
        refund.status = Refund.STATUS_FAILED
        refund.save()
        response = self.client.post(
            f"/api/v1/orders/{order.pk}/refund/",
            {"reason": "item_damaged", "product_ids": [self.product.pk]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_coupon_refund_and_merchant_earnings_use_amount_paid(self) -> None:
        TaxJurisdiction.objects.create(
            country="US", state="FL", name="Test tax", rate=Decimal(".10")
        )
        Coupon.objects.create(
            code="HALF",
            discount=50,
            num_available=10,
            valid_to=timezone.now() + timezone.timedelta(days=1),
        )
        order = self.checkout(coupon="HALF")
        line = order.items_snapshot[0]
        self.assertEqual(Decimal(line["net_total"]), Decimal("50"))
        self.assertEqual(Decimal(line["tax_amount"]), Decimal("5"))
        self.assertEqual(Decimal(line["line_total"]), Decimal("55"))
        self.assertEqual(
            StoreEarningsLedger.objects.get(
                order=order, entry_type="sale"
            ).gross_amount,
            Decimal("50"),
        )
        refund = self.request_refund(order)
        self.assertEqual(refund.refund_amount, Decimal("55"))
        before = UserWallet.objects.get(user=self.buyer).balance
        process_order_refund(refund, self.seller)
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance, before + Decimal("55")
        )
        self.assertEqual(
            StoreEarningsLedger.objects.get(
                order=order, entry_type="refund"
            ).gross_amount,
            Decimal("-50"),
        )

    def test_targeted_coupon_does_not_discount_another_stores_earnings(self) -> None:
        other = Store.objects.create(
            user=self.seller,
            name="Second store",
            status="active",
            verified_at=timezone.now(),
        )
        StoreAddress.objects.create(
            store=other,
            address="1 Main St",
            city="Tampa",
            state="FL",
            country="US",
            zip="33602",
            is_default=True,
        )
        product = Product.objects.create(
            store=other, title="Second item", price=100, discount=0, available=10
        )
        Coupon.objects.create(
            code="TARGET",
            discount=50,
            num_available=10,
            type=Coupon.PRODUCT,
            product=self.product,
            valid_to=timezone.now() + timezone.timedelta(days=1),
        )
        for item in [self.product, product]:
            self.client.post(
                "/api/v1/cart/", {"product": item.pk, "quantity": 1}, format="json"
            )
        order = self.checkout(coupon="TARGET", add_item=False)
        self.assertEqual(
            StoreEarningsLedger.objects.get(
                order=order, store=self.store, entry_type="sale"
            ).gross_amount,
            Decimal("50"),
        )
        self.assertEqual(
            StoreEarningsLedger.objects.get(
                order=order, store=other, entry_type="sale"
            ).gross_amount,
            Decimal("100"),
        )

    @patch("payment.services.call_stripe_refund", return_value="re_audit")
    def test_split_tender_cancel_refunds_only_captured_card_and_wallet_shares(
        self, refund: Mock
    ) -> None:
        order = self.checkout()
        order.payment_type = "split_tender"
        order.stripe_session_id = "cs_split_cancel"
        order.wallet_paid = Decimal("30")
        order.save()
        before = UserWallet.objects.get(user=self.buyer).balance
        execute_order_status_transition(
            order, "cancelled", self.seller, "Verified cancellation"
        )
        self.assertEqual(
            refund.call_args.kwargs["amount"], order.paid_total - Decimal("30")
        )
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance, before + Decimal("30")
        )

    def test_partial_refund_then_cancel_only_reverses_remaining_money_and_stock(
        self,
    ) -> None:
        second = Product.objects.create(
            store=self.store, title="Second item", price=100, discount=0, available=10
        )
        for item in [self.product, second]:
            self.client.post(
                "/api/v1/cart/", {"product": item.pk, "quantity": 1}, format="json"
            )
        order = self.checkout(add_item=False)
        refund = self.request_refund(order)
        process_order_refund(refund, self.seller)
        self.assertEqual(self.cancel(order).status_code, 200)
        for product in [self.product, second]:
            product.refresh_from_db()
            self.assertEqual(product.available, 10)
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance, Decimal("1000")
        )

    def test_approval_cannot_exceed_remaining_settled_funds(self) -> None:
        order = self.checkout()
        refund = Refund.objects.create(
            order=order,
            email=self.buyer.email,
            reason="Invalid amount",
            refund_amount=order.total + 1,
        )
        with self.assertRaises(ValidationError):
            process_order_refund(refund, self.seller)
        self.assertEqual(order.refunded_total, 0)

    def test_merchant_cannot_set_financial_status_or_move_fulfillment_backward(
        self,
    ) -> None:
        order = self.checkout()
        self.client.force_authenticate(self.seller)
        url = f"/api/v1/stores/{self.store.pk}/orders/{order.pk}/tracking/"
        for status in ["cancelled", "refunded"]:
            self.assertEqual(
                self.client.patch(url, {"status": status}, format="json").status_code,
                400,
            )
        self.assertEqual(
            self.client.patch(url, {"status": "shipped"}, format="json").status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(url, {"status": "confirmed"}, format="json").status_code,
            400,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, "shipped")
        self.assertEqual(
            self.client.patch(url, {"status": "delivered"}, format="json").status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(url, {"status": "shipped"}, format="json").status_code,
            400,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, "delivered")

    def test_merchant_can_fulfill_directly_to_delivered(self) -> None:
        order = self.checkout()
        self.client.force_authenticate(self.seller)
        url = f"/api/v1/stores/{self.store.pk}/orders/{order.pk}/tracking/"
        res = self.client.patch(
            url,
            {"status": "delivered", "tracking_number": "TRACK-DELIV-1", "carrier": "USPS"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "delivered")
        self.assertIsNotNone(order.shipped_at)
        self.assertIsNotNone(order.delivered_at)
        fulfillment = order.fulfillments.get(store=self.store)
        self.assertEqual(fulfillment.status, "delivered")
        self.assertEqual(fulfillment.tracking_number, "TRACK-DELIV-1")
        self.assertIsNotNone(fulfillment.shipped_at)
        self.assertIsNotNone(fulfillment.delivered_at)

    def test_mixed_store_fulfillment_does_not_complete_another_store(self) -> None:
        seller = User.objects.create_user(
            email="other-audit-seller@test.com", password="test"
        )
        store = Store.objects.create(
            user=seller,
            name="Other seller",
            status="active",
            verified_at=timezone.now(),
        )
        StoreAddress.objects.create(
            store=store,
            address="1 Main St",
            city="Tampa",
            state="FL",
            country="US",
            zip="33602",
            is_default=True,
        )
        second = Product.objects.create(
            store=store, title="Other shipment", price=100, discount=0, available=10
        )
        for item in [self.product, second]:
            self.client.post(
                "/api/v1/cart/", {"product": item.pk, "quantity": 1}, format="json"
            )
        order = self.checkout(add_item=False)
        self.client.force_authenticate(self.seller)
        url = f"/api/v1/stores/{self.store.pk}/orders/{order.pk}/tracking/"
        for status in ["shipped", "delivered"]:
            self.assertEqual(
                self.client.patch(
                    url, {"status": status, "tracking_number": "123"}, format="json"
                ).status_code,
                200,
            )
        order.refresh_from_db()
        self.assertEqual(order.status, "shipped")
        self.assertEqual(order.fulfillments.get(store=store).status, "confirmed")
        self.assertEqual(order.fulfillments.get(store=self.store).status, "delivered")
        self.assertEqual(order.tracking_number, "")
        response = self.client.get(f"/api/v1/stores/{self.store.pk}/orders/")
        self.assertEqual(response.data["results"][0]["status"], "delivered")
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.cancel(order).status_code, 400)

    def test_tax_allocates_order_discount_across_taxable_and_exempt_items(self) -> None:
        TaxJurisdiction.objects.create(
            country="US",
            state="FL",
            name="Test",
            rate=Decimal(".10"),
            tax_digital=False,
        )
        items = [
            {"unit_price": "100", "quantity": 1, "is_digital": False},
            {"unit_price": "100", "quantity": 1, "is_digital": True},
        ]
        result = LocalTaxProvider().calculate_tax(
            items, Decimal("150"), Decimal("0"), self.address
        )
        self.assertEqual(result.taxable_merchandise, Decimal("75"))
        self.assertEqual(result.amount, Decimal("7.50"))
        self.assertEqual(result.details["line_taxes"], ["7.5", "0"])

    def test_tax_respects_explicit_coupon_on_exempt_line_only(self) -> None:
        TaxJurisdiction.objects.create(
            country="US",
            state="FL",
            name="Test",
            rate=Decimal(".10"),
            tax_digital=False,
        )
        items = [
            {"net_total": "100", "is_digital": False},
            {"net_total": "50", "is_digital": True},
        ]
        result = LocalTaxProvider().calculate_tax(
            items, Decimal("150"), Decimal("0"), self.address
        )
        self.assertEqual(result.taxable_merchandise, Decimal("100"))

    def test_zip_override_takes_precedence_over_default_state_exemption(self) -> None:
        TaxJurisdiction.objects.create(
            country="US",
            state="AK",
            postal_code="99501",
            name="Configured ZIP",
            rate=Decimal(".05"),
        )
        address = {"country": "US", "state": "AK", "zip": "99501"}
        result = LocalTaxProvider().calculate_tax(
            [{"unit_price": "100", "quantity": 1}],
            Decimal("100"),
            Decimal("0"),
            address,
        )
        self.assertEqual(result.amount, Decimal("5"))
        self.assertEqual(result.jurisdiction, "Configured ZIP")

    def test_cent_allocation_preserves_total_and_zero_weight_lines(self) -> None:
        result = allocate_amount(
            Decimal(".05"), [Decimal("1"), Decimal("1"), Decimal("1"), Decimal("0")]
        )
        self.assertEqual(sum(result), Decimal(".05"))
        self.assertEqual(result[-1], Decimal("0"))

    def test_generated_affiliate_link_uses_frontend_proxy_and_resolves(self) -> None:
        Marketer.objects.create(user=self.buyer, name="Audit marketer")
        response = self.client.post(
            "/api/v1/affiliates/links/",
            {"product": self.product.pk, "identifier": "audit-link"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(
            response.data["abs_url"].startswith("http://testserver/api/affiliates/r/")
        )
        backend_path = response.data["abs_url"].replace(
            "http://testserver/api/", "/api/v1/"
        )
        self.assertEqual(self.client.get(backend_path).status_code, 302)
        self.assertEqual(
            self.client.post(
                "/api/v1/affiliates/links/",
                {"product": self.product.pk, "identifier": "../bad"},
                format="json",
            ).status_code,
            400,
        )

    def test_shipping_tax_preview_uses_the_applied_coupon(self) -> None:
        TaxJurisdiction.objects.create(
            country="US", state="FL", name="Test", rate=Decimal(".10")
        )
        Coupon.objects.create(
            code="PREVIEW",
            discount=50,
            num_available=10,
            valid_to=timezone.now() + timezone.timedelta(days=1),
        )
        self.client.post(
            "/api/v1/cart/", {"product": self.product.pk, "quantity": 1}, format="json"
        )
        response = self.client.get(
            f"/api/v1/checkout/shipping-rates/?address={self.address.pk}&coupon=PREVIEW"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Decimal(response.data[0]["tax"]), Decimal("5"))

    def test_migration_recognizes_wallet_debit_but_not_unpaid_placement(self) -> None:
        from importlib import import_module

        migration = import_module("payment.migrations.0019_backfill_settled_payments")
        order = self.checkout()
        Order.objects.filter(pk=order.pk).update(paid_total=0, wallet_paid=0)
        unpaid = Order.objects.create(
            user=self.buyer,
            ordered=True,
            status="confirmed",
            total=100,
            payment_type="cash_on_delivery",
        )
        unknown = Order.objects.create(
            user=self.buyer,
            ordered=True,
            status="confirmed",
            total=100,
            payment_type="card",
        )
        migration.backfill_settlement(apps, SimpleNamespace(connection=connection))
        order.refresh_from_db()
        unpaid.refresh_from_db()
        unknown.refresh_from_db()
        self.assertEqual(order.paid_total, order.total)
        self.assertEqual(order.wallet_paid, order.total)
        self.assertEqual(unpaid.paid_total, 0)
        self.assertEqual(unknown.paid_total, 0)

    def test_unverified_legacy_sale_ledger_is_excluded_from_payout_balances(
        self,
    ) -> None:
        from store.models import MerchantWallet

        wallet = MerchantWallet.objects.create(user=self.seller, pending_balance=96)
        order = Order.objects.create(
            user=self.buyer,
            ordered=True,
            status="confirmed",
            total=100,
            payment_type="cash_on_delivery",
        )
        StoreEarningsLedger.objects.create(
            order=order,
            store=self.store,
            wallet=wallet,
            entry_type="sale",
            gross_amount=100,
            fee_amount=4,
            net_amount=96,
            status="pending",
        )
        result = calculate_merchant_financials(self.seller)
        self.assertEqual(Decimal(result["pending_balance"]), Decimal("0"))
        self.assertEqual(Decimal(result["available_balance"]), Decimal("0"))

    @override_settings(STRIPE_TAX_ENABLED=True)
    @patch("stripe.tax.Calculation.create")
    def test_stripe_tax_preserves_exact_provider_line_and_shipping_taxes(
        self, create: Mock
    ) -> None:
        from payment.tax import StripeTaxProvider

        create.return_value = SimpleNamespace(
            id="taxcalc_audit",
            tax_amount_exclusive=1200,
            shipping_cost=SimpleNamespace(amount_tax=200),
            tax_breakdown=[],
            line_items=SimpleNamespace(
                data=[
                    SimpleNamespace(reference="line_0", amount_tax=1000),
                    SimpleNamespace(reference="line_1", amount_tax=0),
                ]
            ),
        )
        result = StripeTaxProvider().calculate_tax(
            [
                {"net_total": "100", "is_digital": False},
                {"net_total": "100", "is_digital": True},
            ],
            Decimal("200"),
            Decimal("20"),
            self.address,
        )
        self.assertEqual(result.shipping_tax, Decimal("2"))
        self.assertEqual(result.details["line_taxes"], ["10", "0"])
        self.assertEqual(create.call_args.kwargs["expand"], ["line_items"])

    def funding_session(
        self, session_id: str = "cs_funding", amount: int = 1000
    ) -> dict[str, object]:
        return {
            "payment_status": "paid",
            "payment_intent": "pi_funding",
            "client_reference_id": str(self.buyer.pk),
            "metadata": {"wallet_topup": "true"},
            "currency": "usd",
            "amount_total": amount,
        }

    def test_one_paid_topup_can_credit_only_once(self) -> None:
        session = self.funding_session()
        first = confirm_funding(self.buyer, "cs_funding", session)
        second = confirm_funding(self.buyer, "cs_funding", session)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.status, "credited")
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance, Decimal("1010")
        )
        self.assertEqual(
            UserWalletTransaction.objects.filter(
                reference="stripe_topup:cs_funding"
            ).count(),
            1,
        )

    def test_wallet_credit_has_database_enforced_unique_idempotency(self) -> None:
        first = credit_user_wallet(
            self.buyer, Decimal("5"), "First", idempotency_key="audit-credit"
        )
        second = credit_user_wallet(
            self.buyer, Decimal("5"), "Retry", idempotency_key="audit-credit"
        )
        self.assertEqual(first.pk, second.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            UserWalletTransaction.objects.create(
                wallet=first.wallet,
                amount=5,
                transaction_type="credit",
                idempotency_key="audit-credit",
            )

    @patch("payment.funding.stripe.checkout.Session.create")
    def test_open_payment_sessions_reserve_daily_deposit_allowance(
        self, create: Mock
    ) -> None:
        create.side_effect = [
            SimpleNamespace(id="cs_limit_1", url="https://checkout.test/1"),
            SimpleNamespace(id="cs_limit_2", url="https://checkout.test/2"),
        ]
        for _ in range(2):
            response = self.client.post(
                "/api/v1/wallet/topup-session/", {"amount": "25000"}, format="json"
            )
            self.assertEqual(response.status_code, 200, response.data)
        response = self.client.post(
            "/api/v1/wallet/topup-session/", {"amount": "5"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(create.call_count, 2)
        self.assertEqual(
            WalletFundingAttempt.objects.filter(status="reserved").count(), 2
        )

    @patch(
        "payment.funding.stripe.checkout.Session.create",
        return_value=SimpleNamespace(id="cs_month", url="https://checkout.test"),
    )
    def test_monthly_limit_includes_paid_and_reserved_deposits(
        self, create: Mock
    ) -> None:
        credit_user_wallet(
            self.buyer,
            Decimal("75000"),
            "Prior month-to-date deposit",
            source="deposit",
        )
        # Backdate the deposit so it is in this month but not today's allowance.
        from datetime import datetime, timezone as datetime_timezone

        earlier = datetime(
            timezone.now().year, timezone.now().month, 1, tzinfo=datetime_timezone.utc
        )
        UserWalletTransaction.objects.filter(source="deposit").update(created=earlier)
        response = self.client.post(
            "/api/v1/wallet/topup-session/", {"amount": "25000"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            self.client.post(
                "/api/v1/wallet/topup-session/", {"amount": "5"}, format="json"
            ).status_code,
            400,
        )

    @patch("payment.funding.stripe.Refund.create")
    def test_legacy_over_limit_payment_is_refunded_without_credit(
        self, refund: Mock
    ) -> None:
        credit_user_wallet(
            self.buyer, Decimal("50000"), "Daily deposits", source="deposit"
        )
        result = confirm_funding(self.buyer, "cs_over_limit", self.funding_session())
        self.assertEqual(result.status, "refunded")
        self.assertFalse(
            UserWalletTransaction.objects.filter(
                reference="stripe_topup:cs_over_limit"
            ).exists()
        )
        refund.assert_called_once()
        self.assertEqual(
            confirm_funding(self.buyer, "cs_over_limit", self.funding_session()).status,
            "refunded",
        )
        self.assertEqual(refund.call_count, 1)

    @patch("payment.funding.stripe.Refund.create")
    def test_failed_funding_refund_remains_durable_until_recovery(
        self, refund: Mock
    ) -> None:
        credit_user_wallet(
            self.buyer, Decimal("50000"), "Daily deposits", source="deposit"
        )
        refund.side_effect = RuntimeError("offline")
        result = confirm_funding(self.buyer, "cs_pending", self.funding_session())
        self.assertEqual(result.status, "refund_pending")
        refund.side_effect = None
        with patch(
            "payment.funding.stripe.checkout.Session.retrieve",
            return_value=self.funding_session(),
        ):
            self.assertEqual(recover_wallet_funding(), 1)
        result.refresh_from_db()
        self.assertEqual(result.status, "refunded")
        self.assertEqual(
            UserWalletTransaction.objects.filter(
                reference="stripe_topup:cs_pending"
            ).count(),
            0,
        )

    @patch("payment.funding.stripe.checkout.Session.expire")
    @patch(
        "payment.funding.stripe.checkout.Session.retrieve",
        return_value={"payment_status": "unpaid", "status": "open"},
    )
    def test_recovery_expires_unpaid_session_before_releasing_allowance(
        self, retrieve: Mock, expire: Mock
    ) -> None:
        attempt = WalletFundingAttempt.objects.create(
            user=self.buyer,
            session_id="cs_expired",
            amount=100,
            expires_at=timezone.now(),
        )
        self.assertEqual(recover_wallet_funding(), 1)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "released")
        expire.assert_called_once_with("cs_expired")

    @patch("payment.funding.stripe.Refund.create")
    def test_funding_currency_mismatch_is_refunded_not_credited(
        self, refund: Mock
    ) -> None:
        session = self.funding_session()
        session["currency"] = "eur"
        self.assertEqual(
            confirm_funding(self.buyer, "cs_wrong_currency", session).status, "refunded"
        )
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance, Decimal("1000")
        )
        refund.assert_called_once()

    def test_coupon_atomic_used_increments_and_deactivates_at_cap(self) -> None:
        coupon = Coupon.objects.create(
            code="ATOMICCAP",
            discount=10,
            num_available=2,
            num_used=1,
            valid_to=timezone.now() + timezone.timedelta(days=1),
        )
        coupon.used()
        coupon.refresh_from_db()
        self.assertEqual(coupon.num_used, 2)
        self.assertFalse(coupon.active)
        with self.assertRaises(ValidationError):
            coupon.used()

    def test_compensate_checkout_applies_idempotency_key_without_double_crediting(self) -> None:
        from payment.checkout_recovery import compensate_checkout
        from payment.models import CheckoutAttempt

        key = uuid4()
        attempt = CheckoutAttempt.objects.create(
            user=self.buyer,
            checkout_key=key,
            session_id="cs_test_comp",
            wallet_amount=Decimal("50.00"),
            expires_at=timezone.now() + timezone.timedelta(minutes=30),
            status="reserved",
        )
        initial_balance = UserWallet.objects.get(user=self.buyer).balance
        session = {"payment_status": "unpaid", "status": "expired"}
        self.assertTrue(compensate_checkout(attempt, session, "Session expired"))
        self.buyer.refresh_from_db()
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance,
            initial_balance + Decimal("50.00"),
        )
        self.assertEqual(
            UserWalletTransaction.objects.filter(
                idempotency_key=f"compensate-{key}-wallet"
            ).count(),
            1,
        )
        # Calling again should not double credit
        self.assertTrue(compensate_checkout(attempt, session, "Retry"))
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance,
            initial_balance + Decimal("50.00"),
        )

    def test_settle_pending_merchant_earnings_atomic_execution(self) -> None:
        from store.services import settle_pending_merchant_earnings

        settled = settle_pending_merchant_earnings()
        self.assertIsInstance(settled, int)



@skipUnless(
    connection.vendor == "postgresql", "Row-lock concurrency requires PostgreSQL."
)
@override_settings(ROOT_URLCONF="storefront.urls", STRIPE_SECRET="sk_audit")
class PostgresConcurrencyTests(TransactionTestCase):
    # Legacy state-only deletions retain foreign-key tables; test-only flush must cascade.
    available_apps = [config.name for config in apps.get_app_configs()]

    def setUp(self) -> None:
        AuditRegressionTests.setUp(self)

    def simultaneously(self, action: Callable[[APIClient], int]) -> list[int]:
        barrier = Barrier(2)

        def worker() -> int:
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=self.buyer.pk))
                barrier.wait(timeout=10)
                return action(client)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            return [future.result(timeout=30) for future in futures]

    def test_concurrent_cancellation_reverses_money_and_inventory_once(self) -> None:
        order = AuditRegressionTests.checkout(self)
        codes = self.simultaneously(
            lambda client: client.post(
                f"/api/v1/orders/{order.pk}/cancel/", {}, format="json"
            ).status_code
        )
        self.assertEqual(sorted(codes), [200, 400])
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance, Decimal("1000")
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.available, 10)
        self.assertEqual(
            UserWalletTransaction.objects.filter(
                idempotency_key=f"cancel-{order.pk}-wallet"
            ).count(),
            1,
        )

    def test_concurrent_refund_requests_reserve_one_claim(self) -> None:
        order = AuditRegressionTests.checkout(self)
        codes = self.simultaneously(
            lambda client: client.post(
                f"/api/v1/orders/{order.pk}/refund/",
                {"reason": "item_damaged", "product_ids": [self.product.pk]},
                format="json",
            ).status_code
        )
        self.assertEqual(sorted(codes), [201, 400])
        self.assertEqual(Refund.objects.filter(order=order).count(), 1)

    @patch("storefront.views.stripe.checkout.Session.retrieve")
    def test_concurrent_topup_callbacks_credit_one_receipt(
        self, retrieve: Mock
    ) -> None:
        retrieve.return_value = AuditRegressionTests.funding_session(self)
        codes = self.simultaneously(
            lambda client: client.post(
                "/api/v1/wallet/topup-confirm/",
                {"session_id": "cs_concurrent"},
                format="json",
            ).status_code
        )
        self.assertEqual(codes, [200, 200])
        self.assertEqual(
            UserWallet.objects.get(user=self.buyer).balance, Decimal("1010")
        )
        self.assertEqual(
            UserWalletTransaction.objects.filter(
                reference="stripe_topup:cs_concurrent"
            ).count(),
            1,
        )
