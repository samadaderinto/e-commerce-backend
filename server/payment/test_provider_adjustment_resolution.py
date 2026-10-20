"""Stripe/proxy audit evidence. Uses local signatures, isolated records and no Stripe API calls."""

import hashlib
import hmac
import json
import time
from decimal import Decimal
from typing import Any
from rest_framework.response import Response
from uuid import uuid4

import pytest
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory
from cart.models import Cart, CartItem
from core.models import User
from payment.models import Order
from product.models import Product
from store.models import Store, StoreAddress, StoreEarningsLedger
from store.services import record_order_earnings_for_merchant

pytestmark = pytest.mark.django_db
SECRET = "whsec_isolated_audit_fixture"


def setup() -> tuple[User, User, Store, Product, APIClient]:
    buyer = User.objects.create_user(
        email="stripe-audit-buyer@example.test", password="fixture-only"
    )
    seller = User.objects.create_user(
        email="stripe-audit-seller@example.test", password="fixture-only"
    )
    store = Store.objects.create(
        user=seller,
        name="Stripe fixture store",
        status="active",
        verified_at=timezone.now(),
    )
    StoreAddress.objects.create(
        store=store,
        address="Fixture address",
        city="Austin",
        state="TX",
        country="US",
        zip="78701",
        is_default=True,
    )
    product = Product.objects.create(
        store=store,
        title="Stripe fixture product",
        price=100,
        discount=0,
        available=10,
        is_digital=True,
        digital_file_url="digital_products/fixture.pdf",
    )
    return buyer, seller, store, product, APIClient()


def post_signed(client: APIClient, event: dict[str, Any]) -> Response:
    body = json.dumps(event, separators=(",", ":")).encode()
    stamp = int(time.time())
    digest = hmac.new(
        SECRET.encode(), str(stamp).encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return client.post(
        "/api/v1/stripe/webhook/",
        body,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=f"t={stamp},v1={digest}",
    )


@override_settings(ROOT_URLCONF="storefront.urls", STRIPE_WEBHOOK_SECRET=SECRET)
def test_real_signature_checkout_callback_and_duplicate_complete_once() -> None:
    buyer, seller, store, product, client = setup()
    cart = Cart.objects.create(user=buyer)
    CartItem.objects.create(cart=cart, product=product, quantity=1)
    event = {
        "id": "evt_fixture_completed",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_fixture_completed",
                "object": "checkout.session",
                "client_reference_id": str(buyer.pk),
                "payment_status": "paid",
                "currency": "usd",
                "amount_total": 10000,
                "metadata": {"checkout_key": str(uuid4())},
            }
        },
    }
    for _ in range(2):
        response = post_signed(client, event)
        assert response.status_code == 200, response.data
    assert Order.objects.filter(user=buyer, ordered=True).count() == 1
    product.refresh_from_db()
    assert product.sales == 1


@override_settings(ROOT_URLCONF="storefront.urls", STRIPE_WEBHOOK_SECRET=SECRET)
@pytest.mark.parametrize("event_type", ["charge.refunded", "charge.dispute.created"])
def test_provider_reversal_reconciles_once(event_type: str) -> None:
    buyer, seller, store, product, client = setup()
    order = Order.objects.create(
        user=buyer,
        ordered=True,
        status="delivered",
        total=100,
        subtotal=100,
        paid_total=100,
        payment_type="stripe_wallet",
        stripe_session_id="cs_fixture_reversed",
        checkout_key=uuid4(),
        items_snapshot=[
            {
                "store": store.pk,
                "product": product.pk,
                "quantity": 1,
                "unit_price": "100.00",
                "net_total": "100.00",
                "line_total": "100.00",
                "is_digital": True,
            }
        ],
    )
    record_order_earnings_for_merchant(order)
    payload = {
        "id": "dp_fixture" if "dispute" in event_type else "ch_fixture",
        "payment_intent": "pi_fixture",
        "amount": 10000,
        "currency": "usd",
        "metadata": {"checkout_key": str(order.checkout_key)},
        "status": "needs_response",
    }
    if event_type == "charge.refunded":
        payload["refunds"] = {
            "data": [
                {
                    "id": "re_fixture",
                    "amount": 10000,
                    "status": "succeeded",
                    "currency": "usd",
                    "metadata": {"checkout_key": str(order.checkout_key)},
                }
            ]
        }
    event = {
        "id": "evt_fixture",
        "object": "event",
        "type": event_type,
        "data": {"object": payload},
    }
    for _ in range(2):
        response = post_signed(client, event)
        assert response.status_code == 200, response.data
    order.refresh_from_db()
    if event_type == "charge.refunded":
        assert order.refunded_total == Decimal("100")
        assert (
            StoreEarningsLedger.objects.filter(order=order, entry_type="refund").count()
            == 1
        )
    else:
        assert order.payment_disputed
        assert order.refunded_total == 0


def test_secure_deployment_requires_forwarded_proto() -> None:
    factory = APIRequestFactory()
    with override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        ALLOWED_HOSTS=["api.internal"],
    ):
        middleware = SecurityMiddleware(lambda request: HttpResponse("fixture"))
        # These are the protocol headers passed by the present Next proxy.
        absent = factory.get("/api/v1/products/", HTTP_HOST="api.internal")
        assert middleware(absent).status_code == 301
        assert middleware(absent)["Location"] == "https://api.internal/api/v1/products/"
        forwarded = factory.get(
            "/api/v1/products/",
            HTTP_HOST="api.internal",
            HTTP_X_FORWARDED_PROTO="https",
        )
        assert middleware(forwarded).status_code == 200


@override_settings(ROOT_URLCONF="storefront.urls", STRIPE_WEBHOOK_SECRET=SECRET)
def test_invalid_signature_cannot_complete_order() -> None:
    buyer, seller, store, product, client = setup()
    body = json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "client_reference_id": str(buyer.pk),
                    "payment_status": "paid",
                }
            },
        }
    ).encode()
    response = client.post(
        "/api/v1/stripe/webhook/",
        body,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=f"t={int(time.time())},v1=not-a-valid-fixture-signature",
    )
    assert response.status_code == 400, response.data
    assert not Order.objects.filter(user=buyer).exists()


@override_settings(STRIPE_SECRET="sk_isolated_fixture_no_network")
def test_failed_provider_refund_is_not_approved_or_restocked() -> None:
    from types import SimpleNamespace
    from unittest.mock import patch
    from core.models import Refund
    from payment.services import process_order_refund

    buyer, seller, store, product, client = setup()
    product.is_digital = False
    product.save(update_fields=["is_digital"])
    line = {
        "store": store.pk,
        "product": product.pk,
        "title": product.title,
        "quantity": 1,
        "unit_price": "100.00",
        "net_total": "100.00",
        "line_total": "100.00",
        "is_digital": False,
    }
    order = Order.objects.create(
        user=buyer,
        ordered=True,
        status="delivered",
        delivered_at=timezone.now(),
        total=100,
        subtotal=100,
        paid_total=100,
        payment_type="stripe_wallet",
        stripe_session_id="cs_fixture_failed_refund",
        items_snapshot=[line],
    )
    record_order_earnings_for_merchant(order)
    refund = Refund.objects.create(
        order=order,
        email=buyer.email,
        reason="Fixture return",
        refund_type="original_payment",
        selected_items=[line],
        refund_amount=100,
    )
    with (
        patch(
            "payment.services.stripe.checkout.Session.retrieve",
            return_value={"payment_intent": "pi_fixture_failed_refund"},
        ),
        patch(
            "payment.services.stripe.Refund.create",
            return_value=SimpleNamespace(
                id="re_fixture_failed",
                status="failed",
                failure_reason="fixture_failure",
            ),
        ),
    ):
        from payment.services import RefundProviderError

        with pytest.raises(RefundProviderError):
            process_order_refund(refund, seller, reason="Fixture operator decision")
    refund.refresh_from_db()
    order.refresh_from_db()
    product.refresh_from_db()
    assert refund.status == Refund.STATUS_FAILED
    assert order.refunded_total == Decimal("0")
    assert product.available == 10


@override_settings(STRIPE_SECRET="sk_fixture")
def test_pending_refund_waits_for_provider_success() -> None:
    from types import SimpleNamespace
    from unittest.mock import patch
    from core.models import Refund
    from payment.services import process_order_refund
    from payment.provider_events import reconcile_adjustment

    buyer, seller, store, product, client = setup()
    product.is_digital = False
    product.save(update_fields=["is_digital"])
    line = {
        "store": store.pk,
        "product": product.pk,
        "quantity": 1,
        "unit_price": "100.00",
        "line_total": "100.00",
        "net_total": "100.00",
        "is_digital": False,
    }
    order = Order.objects.create(
        user=buyer,
        ordered=True,
        status="delivered",
        delivered_at=timezone.now(),
        total=100,
        subtotal=100,
        paid_total=100,
        payment_type="stripe_wallet",
        stripe_session_id="cs_pending",
        checkout_key=uuid4(),
        items_snapshot=[line],
    )
    record_order_earnings_for_merchant(order)
    refund = Refund.objects.create(
        order=order,
        email=buyer.email,
        reason="Fixture",
        refund_type="original_payment",
        selected_items=[line],
        refund_amount=100,
    )
    with (
        patch(
            "payment.services.stripe.checkout.Session.retrieve",
            return_value={"payment_intent": "pi_fixture"},
        ),
        patch(
            "payment.services.stripe.Refund.create",
            return_value=SimpleNamespace(id="re_pending", status="pending"),
        ),
    ):
        process_order_refund(refund, seller)
    order.refresh_from_db()
    product.refresh_from_db()
    assert refund.status == "pending"
    assert order.refunded_total == 0
    assert product.available == 10
    for _ in range(2):
        reconcile_adjustment(
            "refund.updated",
            {
                "id": "re_pending",
                "status": "succeeded",
                "currency": "usd",
                "amount": 10000,
                "metadata": {"refund_id": str(refund.pk)},
            },
        )
    order.refresh_from_db()
    product.refresh_from_db()
    assert order.refunded_total == 100
    assert product.available == 11


@override_settings(STRIPE_SECRET="sk_fixture")
def test_settled_local_refund_webhook_does_not_deduct_twice() -> None:
    from types import SimpleNamespace
    from unittest.mock import patch
    from core.models import Refund
    from payment.services import process_order_refund
    from payment.provider_events import reconcile_adjustment

    buyer, seller, store, product, client = setup()
    product.is_digital = False
    product.save(update_fields=["is_digital"])
    line = {
        "store": store.pk,
        "product": product.pk,
        "quantity": 1,
        "unit_price": "100.00",
        "line_total": "100.00",
        "net_total": "100.00",
        "is_digital": False,
    }
    order = Order.objects.create(
        user=buyer,
        ordered=True,
        status="delivered",
        delivered_at=timezone.now(),
        total=100,
        subtotal=100,
        paid_total=100,
        payment_type="split_tender",
        wallet_paid=20,
        stripe_session_id="cs_local",
        items_snapshot=[line],
    )
    record_order_earnings_for_merchant(order)
    refund = Refund.objects.create(
        order=order,
        email=buyer.email,
        reason="Fixture",
        refund_type="original_payment",
        selected_items=[line],
        refund_amount=100,
    )
    with (
        patch(
            "payment.services.stripe.checkout.Session.retrieve",
            return_value={"payment_intent": "pi_local"},
        ),
        patch(
            "payment.services.stripe.Refund.create",
            return_value=SimpleNamespace(id="re_local", status="succeeded"),
        ),
    ):
        process_order_refund(refund, seller)
    baseline = StoreEarningsLedger.objects.filter(
        order=order, entry_type="refund"
    ).count()
    reconcile_adjustment(
        "refund.updated",
        {
            "id": "re_local",
            "status": "succeeded",
            "amount": 8000,
            "currency": "usd",
            "metadata": {"refund_id": str(refund.pk)},
        },
    )
    order.refresh_from_db()
    assert order.refunded_total == 100
    assert (
        StoreEarningsLedger.objects.filter(order=order, entry_type="refund").count()
        == baseline
    )

    with patch("stripe.Refund.retrieve", return_value={"status": "failed"}):
        reconcile_adjustment(
            "refund.failed",
            {
                "id": "re_local",
                "status": "failed",
                "amount": 8000,
                "currency": "usd",
                "metadata": {"refund_id": str(refund.pk)},
            },
        )
    order.refresh_from_db()
    assert order.refunded_total == 20
    with (
        patch(
            "payment.services.stripe.checkout.Session.retrieve",
            return_value={"payment_intent": "pi_local"},
        ),
        patch(
            "payment.services.stripe.Refund.create",
            return_value=SimpleNamespace(id="re_local_retry", status="succeeded"),
        ) as create,
    ):
        process_order_refund(refund, seller)
    assert create.call_args.kwargs["amount"] == 8000
    assert "retry_re_local" in create.call_args.kwargs["idempotency_key"]
    product.refresh_from_db()
    order.refresh_from_db()
    assert product.available == 11
    assert order.refunded_total == 100


@override_settings(STRIPE_SECRET="sk_fixture")
def test_dispute_hold_prevents_settlement_then_won_dispute_releases_it() -> None:
    from datetime import timedelta
    from unittest.mock import patch
    from payment.provider_events import reconcile_adjustment
    from store.services import (
        calculate_store_financials,
        settle_pending_merchant_earnings,
    )

    buyer, seller, store, product, client = setup()
    order = Order.objects.create(
        user=buyer,
        ordered=True,
        status="delivered",
        total=100,
        subtotal=100,
        paid_total=100,
        checkout_key=uuid4(),
        items_snapshot=[
            {
                "store": store.pk,
                "product": product.pk,
                "quantity": 1,
                "unit_price": "100.00",
                "line_total": "100.00",
                "net_total": "100.00",
                "is_digital": True,
            }
        ],
    )
    Order.objects.filter(pk=order.pk).update(created=timezone.now() - timedelta(days=8))
    order.refresh_from_db()
    record_order_earnings_for_merchant(order)
    StoreEarningsLedger.objects.filter(order=order, entry_type="sale").update(
        available_at=timezone.now() - timedelta(days=1)
    )
    data = {
        "id": "dp_hold",
        "status": "needs_response",
        "currency": "usd",
        "amount": 10000,
        "metadata": {"checkout_key": str(order.checkout_key)},
    }
    reconcile_adjustment("charge.dispute.created", data)
    assert Decimal(calculate_store_financials(store)["available_balance"]) == 0
    assert settle_pending_merchant_earnings() == 0
    with patch("stripe.Dispute.retrieve", return_value={"status": "won"}):
        reconcile_adjustment("charge.dispute.closed", {**data, "status": "won"})
    assert settle_pending_merchant_earnings() == 1
    assert Decimal(calculate_store_financials(store)["available_balance"]) == 96


@override_settings(STRIPE_SECRET="sk_fixture")
def test_failed_external_refund_restores_earnings_and_stale_success_cannot_reapply() -> (
    None
):
    from unittest.mock import patch
    from payment.provider_events import reconcile_adjustment
    from store.services import calculate_store_financials

    buyer, seller, store, product, client = setup()
    order = Order.objects.create(
        user=buyer,
        ordered=True,
        status="delivered",
        total=100,
        subtotal=100,
        paid_total=100,
        checkout_key=uuid4(),
        items_snapshot=[
            {
                "store": store.pk,
                "product": product.pk,
                "quantity": 1,
                "unit_price": "100.00",
                "line_total": "100.00",
                "net_total": "100.00",
                "is_digital": True,
            }
        ],
    )
    record_order_earnings_for_merchant(order)
    data = {
        "id": "re_later_failed",
        "status": "succeeded",
        "amount": 10000,
        "currency": "usd",
        "metadata": {"checkout_key": str(order.checkout_key)},
    }
    reconcile_adjustment("refund.updated", data)
    with patch("stripe.Refund.retrieve", return_value={"status": "failed"}):
        reconcile_adjustment("refund.failed", {**data, "status": "failed"})
        reconcile_adjustment("refund.updated", data)
    order.refresh_from_db()
    assert order.refunded_total == 0
    assert Decimal(calculate_store_financials(store)["net_sales"]) == 96


@override_settings(STRIPE_SECRET="sk_fixture")
def test_external_partial_refund_does_not_deduct_tax_from_merchant_earnings() -> None:
    from unittest.mock import patch
    from payment.provider_events import reconcile_adjustment
    from store.services import calculate_store_financials

    buyer, seller, store, product, client = setup()
    line = {
        "store": store.pk,
        "product": product.pk,
        "quantity": 1,
        "unit_price": "100.00",
        "net_total": "100.00",
        "line_total": "108.00",
        "tax_amount": "8.00",
        "is_digital": True,
    }
    order = Order.objects.create(
        user=buyer,
        ordered=True,
        status="delivered",
        total=108,
        subtotal=100,
        tax=8,
        paid_total=108,
        checkout_key=uuid4(),
        items_snapshot=[line],
    )
    record_order_earnings_for_merchant(order)
    data = {
        "id": "re_partial_tax",
        "status": "succeeded",
        "amount": 5400,
        "currency": "usd",
        "metadata": {"checkout_key": str(order.checkout_key)},
    }
    reconcile_adjustment("refund.updated", data)
    order.refresh_from_db()
    assert order.refunded_total == 54
    assert Decimal(calculate_store_financials(store)["net_sales"]) == 48
    with patch("stripe.Refund.retrieve", return_value={"status": "failed"}):
        reconcile_adjustment("refund.failed", {**data, "status": "failed"})
    assert Decimal(calculate_store_financials(store)["net_sales"]) == 96


@override_settings(STRIPE_SECRET="sk_fixture")
def test_taxed_split_refund_failure_and_retry_preserve_wallet_and_stock() -> None:
    from types import SimpleNamespace
    from unittest.mock import patch
    from core.models import Refund, UserWallet
    from payment.provider_events import reconcile_adjustment
    from payment.services import process_order_refund
    from store.services import calculate_store_financials

    buyer, seller, store, product, client = setup()
    product.is_digital = False
    product.save(update_fields=["is_digital"])
    line = {
        "store": store.pk,
        "product": product.pk,
        "quantity": 1,
        "unit_price": "100.00",
        "net_total": "100.00",
        "line_total": "108.00",
        "tax_amount": "8.00",
        "is_digital": False,
    }
    order = Order.objects.create(
        user=buyer,
        ordered=True,
        status="delivered",
        delivered_at=timezone.now(),
        total=108,
        subtotal=100,
        tax=8,
        paid_total=108,
        wallet_paid=20,
        payment_type="split_tender",
        stripe_session_id="cs_taxed",
        items_snapshot=[line],
    )
    record_order_earnings_for_merchant(order)
    refund = Refund.objects.create(
        order=order,
        email=buyer.email,
        reason="Fixture return",
        refund_type="original_payment",
        selected_items=[line],
        refund_amount=108,
    )
    with (
        patch(
            "payment.services.stripe.checkout.Session.retrieve",
            return_value={"payment_intent": "pi_taxed"},
        ),
        patch(
            "payment.services.stripe.Refund.create",
            return_value=SimpleNamespace(id="re_taxed", status="succeeded"),
        ),
    ):
        process_order_refund(refund, seller)
    assert Decimal(calculate_store_financials(store)["net_sales"]) == 0
    with patch("stripe.Refund.retrieve", return_value={"status": "failed"}):
        reconcile_adjustment(
            "refund.failed",
            {
                "id": "re_taxed",
                "status": "failed",
                "amount": 8800,
                "currency": "usd",
                "metadata": {"refund_id": str(refund.pk)},
            },
        )
    order.refresh_from_db()
    assert order.refunded_total == 20
    assert Decimal(calculate_store_financials(store)["net_sales"]) == Decimal("78.22")
    with (
        patch(
            "payment.services.stripe.checkout.Session.retrieve",
            return_value={"payment_intent": "pi_taxed"},
        ),
        patch(
            "payment.services.stripe.Refund.create",
            return_value=SimpleNamespace(id="re_taxed_retry", status="succeeded"),
        ) as create,
    ):
        process_order_refund(refund, seller)
    assert create.call_args.kwargs["amount"] == 8800
    order.refresh_from_db()
    product.refresh_from_db()
    assert order.refunded_total == 108
    assert product.available == 11
    assert UserWallet.objects.get(user=buyer).balance == 20
    assert Decimal(calculate_store_financials(store)["net_sales"]) == 0
