"""Regression coverage for store permissions, moderation and push recovery."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from core.models import User
from product.models import Product
from store.models import Store, StoreTeamMember

pytestmark = pytest.mark.django_db


def fixtures() -> tuple[Store, User, APIClient]:
    owner = User.objects.create_user(
        email="audit-owner@example.test", password="fixture-only"
    )
    member = User.objects.create_user(
        email="audit-member@example.test", password="fixture-only"
    )
    store = Store.objects.create(
        user=owner, name="Audit store", status="active", verified_at=timezone.now()
    )
    StoreTeamMember.objects.create(
        store=store, user=member, role=StoreTeamMember.ROLE_FULFILLMENT_SPECIALIST
    )
    client = APIClient()
    client.force_authenticate(member)
    return store, member, client


def test_fulfillment_member_cannot_rename_store() -> None:
    store, member, client = fixtures()
    response = client.patch(
        f"/api/v1/stores/{store.pk}/", {"name": "Changed by fulfillment"}, format="json"
    )
    assert response.status_code == 403, response.data
    store.refresh_from_db()
    assert store.name == "Audit store"


def test_fulfillment_member_cannot_change_public_contact() -> None:
    store, member, client = fixtures()
    response = client.patch(
        f"/api/v1/stores/{store.pk}/profile/",
        {"email": "changed@example.test"},
        format="json",
    )
    assert response.status_code == 403, response.data
    assert not store.storeinfo_set.exists()


@pytest.mark.parametrize("blocked", [False, True])
def test_staff_can_preview_blocked_product(blocked: bool) -> None:
    store, member, client = fixtures()
    staff = User.objects.create_staffuser(
        email="audit-staff@example.test", password="fixture-only"
    )
    product = Product.objects.create(
        store=store,
        title="Blocked product",
        description="Fixture",
        price=Decimal("10"),
        discount=0,
        available=1,
        visibility=True,
        is_blocked=blocked,
    )
    client.force_authenticate(staff)
    assert client.get(f"/api/v1/products/{product.pk}/").status_code == 200


def test_push_retry_skips_successful_batches() -> None:
    from types import SimpleNamespace
    from django.test import override_settings
    from django.contrib.contenttypes.models import ContentType
    from notification.models import Notification, NotificationDelivery, PushDevice
    from notification.tasks import _deliver_push

    store, member, client = fixtures()
    notification = Notification.objects.create(
        recipient=member,
        actor_content_type=ContentType.objects.get_for_model(User),
        actor_object_id=str(member.pk),
        verb="Audit fixture",
        data={},
    )
    delivery = NotificationDelivery.objects.create(
        notification=notification,
        recipient=member,
        channel="push",
        idempotency_key="audit-push-fixture",
    )
    PushDevice.objects.bulk_create(
        [PushDevice(user=member, token=f"fixture-token-{i}") for i in range(501)]
    )
    batch_ok = SimpleNamespace(
        success_count=500, responses=[SimpleNamespace(success=True) for _ in range(500)]
    )
    with (
        override_settings(FCM_ENABLED=True),
        patch("notification.tasks._firebase_app", return_value=object()),
        patch(
            "firebase_admin.messaging.send_each_for_multicast",
            side_effect=[batch_ok, RuntimeError("Simulated transport error")],
        ) as sender,
    ):
        with pytest.raises(RuntimeError):
            _deliver_push(delivery)
        first_tokens = list(sender.call_args_list[0].args[0].tokens)
    delivery.refresh_from_db()
    assert delivery.metadata.get("pending_tokens") == ["fixture-token-500"]
    with (
        override_settings(FCM_ENABLED=True),
        patch("notification.tasks._firebase_app", return_value=object()),
        patch(
            "firebase_admin.messaging.send_each_for_multicast",
            side_effect=RuntimeError("Stop before any delivery"),
        ) as retry,
    ):
        with pytest.raises(RuntimeError):
            _deliver_push(delivery)
        assert list(retry.call_args.args[0].tokens) == ["fixture-token-500"]


def test_store_delete_preserves_blocked_products_and_moderation_history() -> None:
    from product.models import ProductModerationEvent

    store, member, client = fixtures()
    product = Product.objects.create(
        store=store,
        title="Blocked fixture",
        price=Decimal("10"),
        discount=0,
        available=1,
        is_blocked=True,
    )
    event = ProductModerationEvent.objects.create(
        product=product, actor=member, action="block", reason="Fixture review"
    )
    product_pk, event_pk = product.pk, event.pk
    client.force_authenticate(store.user)
    response = client.delete(f"/api/v1/stores/{store.pk}/delete/")
    assert response.status_code == 400, response.data
    assert Product.objects.filter(pk=product_pk).exists()
    assert ProductModerationEvent.objects.filter(pk=event_pk).exists()


@pytest.mark.parametrize("blocked", [False, True])
def test_draft_preview_requires_operator_and_explicit_flag(blocked: bool) -> None:
    store, member, client = fixtures()
    staff = User.objects.create_staffuser(
        email="preview-operator@example.test", password="fixture-only"
    )
    product = Product.objects.create(
        store=store,
        title="Draft under review",
        price=Decimal("10"),
        discount=0,
        available=1,
        visibility=False,
        is_blocked=blocked,
    )
    url = f"/api/v1/products/{product.pk}/"
    for actor in (store.user, member, None):
        client.force_authenticate(actor)
        assert client.get(url + "?preview=1").status_code == 404
    client.force_authenticate(staff)
    assert client.get(url).status_code == 404
    assert client.get(url + "?preview=1").status_code == 200
