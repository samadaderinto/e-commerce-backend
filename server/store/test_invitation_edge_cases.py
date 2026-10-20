"""Invitation and cent-allocation regressions using isolated accounts only."""

from decimal import Decimal
from html import unescape
import re
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from django.db.models import Sum
from rest_framework.test import APIClient

from core.models import User
from notification.models import Notification, NotificationDelivery
from payment.models import Order
from payment.provider_events import adjust_earnings
from store.models import MerchantWallet, Store, StoreEarningsLedger, StoreTeamMember
from store.services import link_pending_store_team_invitations

pytestmark = pytest.mark.django_db


@pytest.fixture
def invitation_setup() -> tuple[APIClient, Store]:
    owner = User.objects.create_user(
        email="edge-owner@example.test", password="fixture-only"
    )
    store = Store.objects.create(user=owner, name="Invitation edge fixtures")
    client = APIClient()
    client.force_authenticate(owner)
    return client, store


def test_invitation_link_preserves_plus_address(
    invitation_setup: tuple[APIClient, Store],
) -> None:
    client, store = invitation_setup
    email = "invited+catalog@example.test"
    response = client.post(
        f"/api/v1/stores/{store.pk}/team/",
        {"email": email, "role": "catalog_manager"},
        format="json",
    )
    assert response.status_code == 201
    delivery = NotificationDelivery.objects.get(recipient_email=email)
    links = re.findall(r'href="([^"]+)"', unescape(delivery.body))
    invitation = next(url for url in links if "invite=" in url)
    assert parse_qs(urlsplit(invitation).query)["email"] == [email]


def test_registered_pending_invitee_cannot_be_added_twice(
    invitation_setup: tuple[APIClient, Store],
) -> None:
    client, store = invitation_setup
    email = "registered-pending@example.test"
    invitation = StoreTeamMember.objects.create(
        store=store,
        invited_email=email,
        status="pending",
        role="catalog_manager",
    )
    user = User.objects.create_user(email=email, password="fixture-only")
    response = client.post(
        f"/api/v1/stores/{store.pk}/team/",
        {"email": email, "role": "fulfillment_specialist"},
        format="json",
    )
    assert response.status_code == 400
    assert link_pending_store_team_invitations(user) == 1
    invitation.refresh_from_db()
    assert invitation.user_id == user.pk
    assert StoreTeamMember.objects.filter(store=store).count() == 1


def test_each_explicit_resend_creates_a_delivery(
    invitation_setup: tuple[APIClient, Store],
) -> None:
    client, store = invitation_setup
    member = StoreTeamMember.objects.create(
        store=store,
        invited_email="resend-edge@example.test",
        status="pending",
        invite_token="fixture-token",
    )
    for _ in range(2):
        response = client.post(f"/api/v1/stores/{store.pk}/team/{member.pk}/resend/")
        assert response.status_code == 200
    assert (
        NotificationDelivery.objects.filter(recipient_email=member.email).count() == 2
    )


@pytest.mark.parametrize("resend", [False, True])
def test_invitation_queue_failure_returns_retryable_error(
    invitation_setup: tuple[APIClient, Store],
    resend: bool,
) -> None:
    client, store = invitation_setup
    path = f"/api/v1/stores/{store.pk}/team/"
    payload = {"email": "queue-failed@example.test", "role": "catalog_manager"}
    if resend:
        member = StoreTeamMember.objects.create(
            store=store,
            invited_email=payload["email"],
            status="pending",
        )
        path += f"{member.pk}/resend/"
    with patch(
        "utils.functions.send_mail", side_effect=RuntimeError("private diagnostic")
    ):
        response = client.post(path, payload, format="json")
    assert response.status_code == 503
    assert "private diagnostic" not in str(response.data)
    assert StoreTeamMember.objects.filter(store=store).count() == (1 if resend else 0)


def test_legacy_duplicate_invitation_does_not_break_login(
    invitation_setup: tuple[APIClient, Store],
) -> None:
    _, store = invitation_setup
    user = User.objects.create_user(
        email="legacy-duplicate@example.test", password="fixture-only"
    )
    active = StoreTeamMember.objects.create(
        store=store, user=user, role="catalog_manager"
    )
    pending = StoreTeamMember.objects.create(
        store=store,
        invited_email=user.email,
        status="pending",
        role="store_admin",
    )
    assert link_pending_store_team_invitations(user) == 0
    active.refresh_from_db()
    assert active.role == "catalog_manager"
    assert not StoreTeamMember.objects.filter(pk=pending.pk).exists()


def test_failed_registered_invitation_rolls_back_access_notice(
    invitation_setup: tuple[APIClient, Store],
) -> None:
    client, store = invitation_setup
    user = User.objects.create_user(
        email="registered-queue-failed@example.test", password="fixture-only"
    )
    with patch("utils.functions.send_mail", side_effect=RuntimeError("queue offline")):
        response = client.post(
            f"/api/v1/stores/{store.pk}/team/",
            {"email": user.email, "role": "catalog_manager"},
            format="json",
        )
    assert response.status_code == 503
    assert not StoreTeamMember.objects.filter(store=store, user=user).exists()
    assert not Notification.objects.filter(recipient=user).exists()
    assert not NotificationDelivery.objects.filter(recipient=user).exists()


@pytest.mark.parametrize("amount", [".01", ".02", ".03"])
def test_provider_adjustment_preserves_cents_across_four_stores(amount: str) -> None:
    owner = User.objects.create_user(
        email="rounding-owner@example.test", password="fixture-only"
    )
    wallet = MerchantWallet.objects.create(user=owner)
    order = Order.objects.create(
        user=owner, total=Decimal(".04"), paid_total=Decimal(".04")
    )
    for index in range(4):
        store = Store.objects.create(user=owner, name=f"Cent fixture {index}")
        StoreEarningsLedger.objects.create(
            store=store,
            wallet=wallet,
            order=order,
            entry_type="sale",
            gross_amount=Decimal(".01"),
            net_amount=Decimal(".01"),
            fee_amount=0,
        )
    allocations = adjust_earnings(order, Decimal(amount))
    assert sum(map(Decimal, allocations.values())) == Decimal(amount)
    actual = StoreEarningsLedger.objects.filter(
        order=order, entry_type="refund"
    ).aggregate(total=Sum("gross_amount"))["total"]
    assert actual == -Decimal(amount)
    assert all(Decimal(value) <= Decimal(".01") for value in allocations.values())
    adjust_earnings(order, -Decimal(amount), allocations)
    restored = StoreEarningsLedger.objects.filter(
        order=order, entry_type="refund"
    ).aggregate(total=Sum("gross_amount"))["total"]
    assert restored == 0
