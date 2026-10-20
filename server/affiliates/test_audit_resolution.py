"""App-wide audit evidence; isolated fixtures and provider mocks only."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from core.models import User, UserWallet
from payment.models import Order
from product.models import Product
from store.models import Store
from affiliates.models import Marketer, Referral
from affiliates.services import record_referral, process_referral_reward_for_order

pytestmark = pytest.mark.django_db


def setup() -> tuple[User, User, Store, Product, APIClient]:
    buyer = User.objects.create_user(
        email="wide-buyer@example.test", password="fixture-only"
    )
    seller = User.objects.create_user(
        email="wide-seller@example.test", password="fixture-only"
    )
    store = Store.objects.create(
        user=seller, name="Audit store", status="active", verified_at=timezone.now()
    )
    product = Product.objects.create(
        store=store,
        title="Search fixture",
        description="Search fixture",
        price=10,
        discount=0,
        available=5,
    )
    client = APIClient()
    client.force_authenticate(buyer)
    return buyer, seller, store, product, client


def referred_order(
    payment_type: str = "cash_on_delivery", paid_total: int = 0
) -> tuple[User, User, Order, APIClient]:
    buyer, seller, store, product, client = setup()
    marketer = Marketer.objects.create(user=seller, name="Fixture affiliate")
    record_referral(marketer.marketer_id, buyer)
    order = Order.objects.create(
        user=buyer,
        ordered=True,
        status="confirmed",
        total=10,
        paid_total=paid_total,
        payment_type=payment_type,
        wallet_paid=paid_total if payment_type == "user_wallet" else 0,
        items_snapshot=[
            {
                "product": product.pk,
                "store": store.pk,
                "title": product.title,
                "quantity": 1,
                "unit_price": "10.00",
                "net_total": "10.00",
                "line_total": "10.00",
                "is_digital": False,
            }
        ],
    )
    return buyer, seller, order, client


def test_unpaid_cod_order_does_not_award_referral_credit() -> None:
    buyer, seller, order, client = referred_order()
    process_referral_reward_for_order(order)
    assert order.paid_total == 0
    assert Referral.objects.get(referred_user=buyer).status == Referral.PENDING
    assert not UserWallet.objects.filter(user=seller, balance__gt=0).exists()


def test_cancelled_order_reverses_referrer_reward() -> None:
    from payment.services import execute_order_status_transition

    buyer, seller, order, client = referred_order(
        payment_type="user_wallet", paid_total=10
    )
    process_referral_reward_for_order(order)
    execute_order_status_transition(
        order, "cancelled", buyer, reason="Audit fixture cancellation"
    )
    order.refresh_from_db()
    assert order.status == "cancelled"
    assert Referral.objects.get(referred_user=buyer).status == "reversed"
    assert UserWallet.objects.get(user=seller).balance == Decimal("0.00")


def test_search_date_filter_returns_accurate_count() -> None:
    buyer, seller, store, product, client = setup()
    old = Product.objects.create(
        store=store,
        title="Search old",
        description="Fixture",
        price=10,
        discount=0,
        available=5,
    )
    Product.objects.filter(pk=old.pk).update(
        created=timezone.now() - timedelta(days=30)
    )
    with patch(
        "storefront.views.search_product_ids",
        return_value={"ids": [old.pk, product.pk], "count": 2},
    ):
        result = client.get(
            "/api/v1/products/",
            {"search": "Search", "start_date": timezone.now().date().isoformat()},
        )
    assert result.status_code == 200, result.data
    assert len(result.data["results"]) == 1
    assert result.data["count"] == 1


def test_primary_digital_upload_returns_actionable_storage_error() -> None:
    buyer, seller, store, product, client = setup()
    client.force_authenticate(seller)
    upload = SimpleUploadedFile(
        "fixture.pdf", b"fixture document", content_type="application/pdf"
    )
    with patch(
        "django.core.files.storage.default_storage.save",
        side_effect=OSError("Fixture storage unavailable"),
    ):
        response = client.post(
            f"/api/v1/stores/{store.pk}/products/{product.pk}/digital-file/",
            {"file": upload},
            format="multipart",
        )
    assert response.status_code == 503
    assert "Fixture storage unavailable" not in str(response.data)


def test_auth_limits_distinguish_accounts_behind_shared_proxy() -> None:
    from types import SimpleNamespace
    from django.core.cache import cache
    from rest_framework.request import Request
    from rest_framework.parsers import JSONParser
    from rest_framework.test import APIRequestFactory
    from core.throttles import AccountAuthThrottle

    cache.clear()
    factory = APIRequestFactory()
    view = SimpleNamespace(throttle_scope="auth", kwargs={"action": "login"})
    with patch.object(AccountAuthThrottle, "THROTTLE_RATES", {"auth": "10/minute"}):
        for index in range(11):
            request = Request(
                factory.post(
                    "/api/v1/auth/login/",
                    {"email": f"fixture{index}@example.test"},
                    format="json",
                    REMOTE_ADDR="172.20.0.5",
                ),
                parsers=[JSONParser()],
            )
            assert AccountAuthThrottle().allow_request(request, view)
        for _ in range(9):
            request = Request(
                factory.post(
                    "/api/v1/auth/login/",
                    {"email": "fixture0@example.test"},
                    format="json",
                ),
                parsers=[JSONParser()],
            )
            assert AccountAuthThrottle().allow_request(request, view)
        assert not AccountAuthThrottle().allow_request(request, view)
