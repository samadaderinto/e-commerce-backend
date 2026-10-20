"""Focused role/drop audit: isolated fixtures, no real accounts or notifications."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient, APIRequestFactory
from core.models import User
from cart.models import Cart, CartItem
from product.models import Product
from product.policies import validate_purchase
from store.models import Store, StoreAddress, StoreTeamMember, StorePayout, Schedule
from storefront.views import cart_data

pytestmark = pytest.mark.django_db


def setup() -> tuple[User, User, User, Store, Product, APIClient]:
    owner = User.objects.create_user(
        email="roles-owner@example.test", password="fixture-only"
    )
    member = User.objects.create_user(
        email="roles-member@example.test", password="fixture-only"
    )
    buyer = User.objects.create_user(
        email="roles-buyer@example.test", password="fixture-only"
    )
    store = Store.objects.create(
        user=owner, name="Roles store", status="active", verified_at=timezone.now()
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
        title="Drop fixture",
        description="Fixture",
        price=Decimal("10"),
        discount=0,
        available=10,
    )
    client = APIClient()
    return owner, member, buyer, store, product, client


def test_store_admin_cannot_read_owner_payout_bank_details() -> None:
    owner, member, buyer, store, product, client = setup()
    StoreTeamMember.objects.create(
        store=store, user=member, role=StoreTeamMember.ROLE_STORE_ADMIN
    )
    StorePayout.objects.create(
        store=store,
        amount=5,
        reference="fixture-payout",
        account_details={
            "account_number": "000012345678",
            "routing_number": "000111222",
        },
    )
    client.force_authenticate(member)
    response = client.get(f"/api/v1/stores/{store.pk}/payouts/")
    assert response.status_code == 403, response.data


def test_rescheduled_cart_item_reported_unavailable() -> None:
    owner, member, buyer, store, product, client = setup()
    cart = Cart.objects.create(user=buyer)
    CartItem.objects.create(cart=cart, product=product, quantity=1)
    product.drop_at = timezone.now() + timedelta(hours=1)
    product.save(update_fields=["drop_at"])
    request = APIRequestFactory().get("/api/v1/cart/")
    request.user = buyer
    assert cart_data(cart, request)["items"][0]["purchasable"] is False
    with pytest.raises(ValidationError):
        validate_purchase(product, buyer)


def test_role_revocation_blocks_product_api_immediately() -> None:
    owner, member, buyer, store, product, client = setup()
    membership = StoreTeamMember.objects.create(
        store=store, user=member, role=StoreTeamMember.ROLE_CATALOG_MANAGER
    )
    client.force_authenticate(member)
    assert client.get(f"/api/v1/stores/{store.pk}/products/").status_code == 200
    membership.role = StoreTeamMember.ROLE_FULFILLMENT_SPECIALIST
    membership.save(update_fields=["role"])
    assert client.get(f"/api/v1/stores/{store.pk}/products/").status_code == 403
    membership.delete()
    assert client.get(f"/api/v1/stores/{store.pk}/").status_code == 404


def test_future_drop_rejects_cart_add_and_checkout_lines_then_opens_on_time() -> None:
    from storefront.views import CheckoutView

    owner, member, buyer, store, product, client = setup()
    release = timezone.now() + timedelta(hours=1)
    product.drop_at = release
    product.save(update_fields=["drop_at"])
    client.force_authenticate(buyer)
    assert (
        client.post(
            "/api/v1/cart/", {"product": product.pk, "quantity": 1}, format="json"
        ).status_code
        == 400
    )
    cart = Cart.objects.create(user=buyer)
    CartItem.objects.create(cart=cart, product=product, quantity=1)
    with pytest.raises(ValidationError):
        CheckoutView()._lines(buyer)
    with patch(
        "django.utils.timezone.now", return_value=release + timedelta(seconds=1)
    ):
        validate_purchase(product, buyer)


def test_drop_sse_emits_one_release_event() -> None:
    from storefront.views import ProductDropLiveView

    owner, member, buyer, store, product, client = setup()
    product.drop_at = timezone.now() - timedelta(seconds=1)
    product.save(update_fields=["drop_at"])
    request = APIRequestFactory().get(
        f"/api/v1/products/{product.pk}/drop-live/", HTTP_ACCEPT="*/*"
    )
    with (
        patch("notification.realtime.broker", return_value=None),
        patch("time.sleep"),
        patch("time.monotonic", side_effect=[0, 0, 3, 30]),
    ):
        response = ProductDropLiveView.as_view()(request, pk=product.pk)
        payload = b"".join(response.streaming_content).decode()
    assert payload.count("event: dropped") == 1


def test_team_listing_applies_search_and_role_filters() -> None:
    owner, member, buyer, store, product, client = setup()
    StoreTeamMember.objects.create(
        store=store, user=member, role=StoreTeamMember.ROLE_CATALOG_MANAGER
    )
    StoreTeamMember.objects.create(
        store=store, user=buyer, role=StoreTeamMember.ROLE_FULFILLMENT_SPECIALIST
    )
    client.force_authenticate(owner)
    response = client.get(
        f"/api/v1/stores/{store.pk}/team/",
        {"search": "no-such-fixture", "role": "store_admin", "limit": 1},
    )
    assert response.status_code == 200, response.data
    assert isinstance(response.data, list)
    assert len(response.data) == 0


def test_draft_visibility_job_is_scheduled_and_publishes() -> None:
    from django.conf import settings
    from store.services import publish_due_products

    owner, member, buyer, store, product, client = setup()
    product.visibility = False
    product.save(update_fields=["visibility"])
    Schedule.objects.create(
        store=store,
        product=product,
        make_visible_at=timezone.now() - timedelta(minutes=1),
    )
    tasks = {entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()}
    assert "store.publish_due_products_task" in tasks
    assert publish_due_products() == 1
    product.refresh_from_db()
    assert product.visibility is True


def test_team_access_changes_notify_affected_member() -> None:
    from notification.models import Notification, NotificationDelivery

    owner, member, buyer, store, product, client = setup()
    client.force_authenticate(owner)
    before = (
        Notification.objects.filter(recipient=member).count(),
        NotificationDelivery.objects.filter(recipient=member).count(),
    )
    created = client.post(
        f"/api/v1/stores/{store.pk}/team/",
        {"email": member.email, "role": "catalog_manager"},
        format="json",
    )
    assert created.status_code == 201, created.data
    identity = created.data["id"]
    assert (
        client.patch(
            f"/api/v1/stores/{store.pk}/team/{identity}/",
            {"role": "fulfillment_specialist"},
            format="json",
        ).status_code
        == 200
    )
    assert (
        client.delete(f"/api/v1/stores/{store.pk}/team/{identity}/").status_code == 204
    )
    after = (
        Notification.objects.filter(recipient=member).count(),
        NotificationDelivery.objects.filter(recipient=member).count(),
    )
    assert after[0] == before[0] + 3
    assert after[1] > before[1]


def test_fulfillment_member_receives_new_order_notification() -> None:
    from notification.models import Notification
    from payment.models import Order
    from notification.events import order_changed

    owner, member, buyer, store, product, client = setup()
    StoreTeamMember.objects.create(
        store=store, user=member, role=StoreTeamMember.ROLE_FULFILLMENT_SPECIALIST
    )
    order = Order.objects.create(
        user=buyer,
        ordered=True,
        status="confirmed",
        total=10,
        paid_total=10,
        items_snapshot=[
            {
                "store": store.pk,
                "product": product.pk,
                "quantity": 1,
                "unit_price": "10.00",
                "is_digital": False,
            }
        ],
    )
    assert Notification.objects.filter(
        recipient=owner, data__event="order_placed", data__order_id=order.pk
    ).exists()
    assert Notification.objects.filter(
        recipient=member, data__event="order_placed", data__order_id=order.pk
    ).exists()
    client.force_authenticate(member)
    assert client.get(f"/api/v1/stores/{store.pk}/orders/").status_code == 200


def test_deleting_member_account_does_not_queue_mail_to_deleted_user() -> None:
    from notification.models import NotificationDelivery

    owner, member, buyer, store, product, client = setup()
    StoreTeamMember.objects.create(
        store=store, user=member, role=StoreTeamMember.ROLE_CATALOG_MANAGER
    )
    member_id = member.pk
    member.delete()
    assert not User.objects.filter(pk=member_id).exists()
    assert not NotificationDelivery.objects.filter(recipient_id=member_id).exists()


def test_accepting_pending_invitation_notifies_once() -> None:
    from notification.models import Notification, NotificationDelivery
    from store.services import link_pending_store_team_invitations

    owner, member, buyer, store, product, client = setup()
    invitation = StoreTeamMember.objects.create(
        store=store,
        invited_email=member.email,
        status=StoreTeamMember.STATUS_PENDING,
        role=StoreTeamMember.ROLE_CATALOG_MANAGER,
    )
    assert not Notification.objects.filter(recipient=member).exists()
    assert link_pending_store_team_invitations(member) == 1
    assert link_pending_store_team_invitations(member) == 0
    invitation.refresh_from_db()
    invitation.save(update_fields=["role", "updated"])
    assert (
        Notification.objects.filter(
            recipient=member, data__event="store_team_access_changed"
        ).count()
        == 1
    )
    assert (
        NotificationDelivery.objects.filter(recipient=member, channel="email").count()
        == 1
    )


def test_invitation_uses_one_html_email_and_an_inbox_notice() -> None:
    from notification.models import Notification, NotificationDelivery

    owner, member, buyer, store, product, client = setup()
    client.force_authenticate(owner)
    response = client.post(
        f"/api/v1/stores/{store.pk}/team/",
        {"email": member.email, "role": StoreTeamMember.ROLE_CATALOG_MANAGER},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert (
        Notification.objects.filter(
            recipient=member, data__event="store_team_access_changed"
        ).count()
        == 1
    )
    assert (
        NotificationDelivery.objects.filter(recipient=member, channel="email").count()
        == 1
    )
    assert NotificationDelivery.objects.get(recipient=member, channel="email").is_html
