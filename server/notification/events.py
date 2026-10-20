"""Persist tenant-scoped events atomically; broadcast and dispatch after commit."""
from collections.abc import Iterable
from typing import Any

from django.db.models import Model, Q, QuerySet
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from core.models import User
from notification.models import Notification
from notification.realtime import publish
from payment.models import Order
from product.models import Product
from store.models import Store, StoreTeamMember


def operators(store: Store | None = None, admins_only: bool = False) -> QuerySet[User]:
    roles = Q(is_superuser=True) | Q(is_business_admin=True)
    if not admins_only:
        roles |= (
            Q(is_staff=True)
            if store is None
            else Q(is_staff=True, assigned_stores=store)
        )
    return User.objects.filter(roles, is_active=True).distinct()


def store_recipients(store: Store, *, inventory: bool = False) -> list[User]:
    roles = [StoreTeamMember.ROLE_STORE_ADMIN]
    roles.append(
        StoreTeamMember.ROLE_CATALOG_MANAGER
        if inventory
        else StoreTeamMember.ROLE_FULFILLMENT_SPECIALIST
    )
    members = User.objects.filter(
        is_active=True,
        store_team_memberships__store=store,
        store_team_memberships__status=StoreTeamMember.STATUS_ACTIVE,
        store_team_memberships__role__in=roles,
    )
    return list(
        {user.pk: user for user in [store.user, *operators(store), *members]}.values()
    )


def send(recipients: Iterable[User], event: str, title: str, target: Model, data: dict[str, Any]) -> None:
    from notification.views import create_notification
    for recipient in recipients:
        create_notification(
            recipient, title, target=target, data={**data, "event": event},
            level="warning" if event in {"inventory_low", "verification_submitted"} else "info",
        )


@receiver(post_save, sender=Notification)
def notification_changed(sender: type[Model], instance: Notification, created: bool, **kwargs: Any) -> None:
    publish(instance.recipient_id, {
        "event": "notification.created" if created else "notification.changed",
        "notification_id": instance.pk, "title": instance.verb if created else None,
        "data": instance.data or {},
    })


@receiver(post_delete, sender=Notification)
def notification_deleted(sender: type[Model], instance: Notification, **kwargs: Any) -> None:
    publish(instance.recipient_id, {"event": "notification.changed", "notification_id": instance.pk})


@receiver(pre_save, sender=Store)
@receiver(pre_save, sender=Product)
@receiver(pre_save, sender=Order)
def previous_state(sender: type[Model], instance: Model, **kwargs: Any) -> None:
    fields = {Store: ["status"], Product: ["available"], Order: ["status", "tracking_number"]}[sender]
    instance._event_previous = sender.objects.filter(pk=instance.pk).values(*fields).first() if instance.pk else None


@receiver(post_save, sender=Store)
def store_changed(sender: type[Model], instance: Store, created: bool, raw: bool = False, **kwargs: Any) -> None:
    if raw:
        return
    if created:
        send(operators(), "store_created", f"New store: {instance.name}", instance, {"store_id": instance.pk})
        if not instance.is_official:
            send(operators(admins_only=True), "verification_submitted", f"Review seller: {instance.name}", instance, {"store_id": instance.pk})
    for user_id in {instance.user_id, *operators(instance).values_list("pk", flat=True)}:
        publish(user_id, {"event": "store.changed", "data": {"store_id": instance.pk}})


@receiver(post_save, sender=Product)
def inventory_changed(sender: type[Model], instance: Product, created: bool, raw: bool = False, **kwargs: Any) -> None:
    if raw:
        return
    old = getattr(instance, "_event_previous", None)
    low = not instance.is_digital and instance.available <= 5 and (
        created or (old and (old["available"] > 5 or (old["available"] > 0 and instance.available == 0)))
    )
    recipients = {
        user.pk: user for user in store_recipients(instance.store, inventory=True)
    }
    for user_id in recipients:
        publish(user_id, {"event": "inventory.changed", "data": {"store_id": instance.store_id, "product_id": instance.pk}})
    if low:
        send(recipients.values(), "inventory_low", f"Low inventory: {instance.title}", instance, {
            "store_id": instance.store_id, "product_id": instance.pk, "available": instance.available,
        })


@receiver(post_save, sender=Order)
def order_changed(sender: type[Model], instance: Order, created: bool, raw: bool = False, **kwargs: Any) -> None:
    if raw or getattr(instance, "_notification_managed", False):
        return
    old = getattr(instance, "_event_previous", None)
    changed = created or not old or any(old[field] != getattr(instance, field) for field in ["status", "tracking_number"])
    if not changed:
        return
    ids = {int(row["store"]) for row in instance.items_snapshot or [] if row.get("store")}
    if not ids and instance.cart_id:
        ids = set(instance.cart.cart_items.values_list("product__store_id", flat=True))
    stores = list(Store.objects.filter(pk__in=ids).select_related("user"))
    recipients = {user.pk: user for user in operators(admins_only=True)}
    scoped_ids = {user_id: set(ids) for user_id in recipients}
    for store in stores:
        for user in store_recipients(store):
            recipients[user.pk] = user
            scoped_ids.setdefault(user.pk, set()).add(store.pk)
    event = "order_placed" if created else "shipping_updated"
    if created and instance.user_id:
        recipients[instance.user_id] = instance.user
        scoped_ids[instance.user_id] = set(ids)
    receipt_ids = getattr(instance, "_receipt_recipient_ids", set())
    for recipient in recipients.values():
        send([recipient], event, f"Order {instance.orderId}: {instance.status}", instance, {
            "order_id": instance.pk, "store_ids": sorted(scoped_ids[recipient.pk]),
            "status": instance.status, "email": recipient.pk not in receipt_ids,
            "event_key": f"order:{instance.pk}:placed" if created else f"order:{instance.pk}:{instance.updated}:{instance.status}:{instance.tracking_number}",
        })
    if instance.user_id:
        publish(instance.user_id, {"event": "order.changed", "data": {"order_id": instance.pk}})


@receiver(m2m_changed, sender=Store.assigned_staff.through)
def assignment_changed(sender: type[Model], instance: Store, action: str, reverse: bool, pk_set: set[int] | None, **kwargs: Any) -> None:
    if reverse or action not in {"post_add", "post_remove", "pre_clear"}:
        return
    ids = set(pk_set or instance.assigned_staff.values_list("pk", flat=True))
    for user_id in ids | {instance.user_id}:
        publish(user_id, {"event": "store.changed", "data": {"store_id": instance.pk}})


@receiver(pre_save, sender=StoreTeamMember)
def remember_membership_role(
    sender: type[Model], instance: StoreTeamMember, **kwargs: Any
) -> None:
    instance._previous_membership = (
        sender.objects.filter(pk=instance.pk).values("role", "status", "user_id").first()
        if instance.pk
        else None
    )


@receiver(post_save, sender=StoreTeamMember)
@receiver(post_delete, sender=StoreTeamMember)
def membership_notice(
    sender: type[Model], instance: StoreTeamMember, signal: Any, **kwargs: Any
) -> None:
    if kwargs.get("raw"):
        return
    if not instance.user:
        return
    removed = signal is post_delete
    origin = kwargs.get("origin")
    if removed and (isinstance(origin, User) or getattr(origin, "model", None) is User):
        return
    if (
        not removed
        and not kwargs.get("created")
        and getattr(instance, "_previous_membership", None) == {
            "role": instance.role,
            "status": instance.status,
            "user_id": instance.user_id,
        }
    ):
        return
    from notification.views import create_notification

    description = (
        f"Your access to {instance.store.name} was removed."
        if removed
        else f"Your role at {instance.store.name} is now {instance.get_role_display()}."
    )
    create_notification(
        instance.user,
        "Store team access changed",
        target=instance.store,
        description=description,
        data={
            "event": "store_team_access_changed",
            "store_id": instance.store_id,
            # Creation already has the invitation's HTML email; keep its inbox/push.
            "email": not kwargs.get("created", False),
        },
        event_key=f"team:{instance.pk}:{instance.updated}:{instance.role}:{instance.status}:{removed}",
    )
