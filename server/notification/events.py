"""Tenant-scoped domain notifications and live invalidations."""
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from core.models import User
from notification.models import Notification
from notification.realtime import publish
from store.models import Store
from product.models import Product
from payment.models import Order


def operators(store=None, admins_only=False):
    roles = Q(is_superuser=True) | Q(is_business_admin=True)
    if not admins_only:
        if store is None or getattr(store, 'is_official', False):
            roles |= Q(is_staff=True)
        else:
            roles |= Q(is_staff=True, assigned_stores=store)
    return User.objects.filter(roles, is_active=True).distinct()


def send(recipients, event, title, target, data):
    from notification.views import create_notification
    for recipient in recipients:
        create_notification(recipient, title, target=target, data={**data, 'event': event},
                            level='warning' if event in {'inventory_low', 'verification_submitted'} else 'info')


@receiver(post_save, sender=Notification)
def notification_changed(sender, instance, created, **kwargs):
    publish(instance.recipient_id, {'event': 'notification.created' if created else 'notification.changed',
            'notification_id': instance.pk, 'title': instance.verb if created else None,
            'data': instance.data or {}})


@receiver(post_delete, sender=Notification)
def notification_deleted(sender, instance, **kwargs):
    publish(instance.recipient_id, {'event': 'notification.changed', 'notification_id': instance.pk})


@receiver(pre_save, sender=Store)
@receiver(pre_save, sender=Product)
@receiver(pre_save, sender=Order)
def previous_state(sender, instance, **kwargs):
    fields = {Store: ['status'], Product: ['available'], Order: ['status', 'tracking_number']}[sender]
    instance._event_previous = sender.objects.filter(pk=instance.pk).values(*fields).first() if instance.pk else None


@receiver(post_save, sender=Store)
def store_changed(sender, instance, created, raw=False, **kwargs):
    if raw: return
    def committed():
        store = Store.objects.filter(pk=instance.pk).first()
        if not store: return
        if created:
            send(operators(), 'store_created', f'New store: {store.name}', store, {'store_id': store.pk})
            if not store.is_official:
                send(operators(admins_only=True), 'verification_submitted', f'Review seller: {store.name}', store, {'store_id': store.pk})
        for user_id in {store.user_id, *operators(store).values_list('pk', flat=True)}:
            publish(user_id, {'event': 'store.changed', 'data': {'store_id': store.pk}})
    transaction.on_commit(committed)


@receiver(post_save, sender=Product)
def inventory_changed(sender, instance, created, raw=False, **kwargs):
    if raw: return
    old = getattr(instance, '_event_previous', None)
    threshold = 5
    low = not instance.is_digital and instance.available <= threshold and (created or (old and (old['available'] > threshold or (old['available'] > 0 and instance.available == 0))))
    def committed():
        product = Product.objects.select_related('store').filter(pk=instance.pk).first()
        if not product: return
        recipients = list(operators(product.store))
        for user_id in {product.store.user_id, *[user.pk for user in recipients]}:
            publish(user_id, {'event': 'inventory.changed', 'data': {'store_id': product.store_id, 'product_id': product.pk}})
        if low:
            send(recipients, 'inventory_low', f'Low inventory: {product.title}', product,
                 {'store_id': product.store_id, 'product_id': product.pk, 'available': product.available})
    transaction.on_commit(committed)


@receiver(post_save, sender=Order)
def order_changed(sender, instance, created, raw=False, **kwargs):
    if raw: return
    old = getattr(instance, '_event_previous', None)
    changed = created or not old or any(old[field] != getattr(instance, field) for field in ['status', 'tracking_number'])
    if not changed: return
    def committed():
        order = Order.objects.filter(pk=instance.pk).first()
        if not order: return
        ids = {row.get('store') for row in (order.items_snapshot or []) if row.get('store')}
        if not ids and order.cart_id:
            ids = set(order.cart.cart_items.values_list('product__store_id', flat=True))
        recipients = {user.pk: user for user in operators(admins_only=True)}
        for store in Store.objects.filter(pk__in=ids):
            recipients.update({user.pk: user for user in operators(store)})
            recipients[store.user_id] = store.user
        title = f'Order {order.orderId}: {order.status}'
        event = 'order_placed' if created else 'order_paid' if old and old['status'] == 'pending' and order.status == 'confirmed' else 'shipping_updated'
        if event in {'order_placed', 'order_paid'} and order.user_id and order.user:
            recipients[order.user_id] = order.user
        send(recipients.values(), event, title, order, {'order_id': order.pk, 'store_ids': list(ids), 'status': order.status})
        # Customer tracking/payment screens also refresh without exposing another tenant's order.
        if order.user_id:
            publish(order.user_id, {'event': 'order.changed', 'data': {'order_id': order.pk}})
    transaction.on_commit(committed)

from django.db.models.signals import m2m_changed


@receiver(m2m_changed, sender=Store.assigned_staff.through)
def assignment_changed(sender, instance, action, reverse, pk_set, **kwargs):
    if reverse or action not in {'post_add', 'post_remove', 'pre_clear'}:
        return
    ids = set(pk_set or instance.assigned_staff.values_list('pk', flat=True))
    for user_id in ids | {instance.user_id}:
        publish(user_id, {'event': 'store.changed', 'data': {'store_id': instance.pk}})
