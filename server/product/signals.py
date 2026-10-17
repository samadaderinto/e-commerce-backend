from typing import Any

from django.db.models.signals import post_delete, post_save, pre_save
from django.db import transaction
from django.dispatch import receiver

from product.models import Product
from product.search import (
    schedule_delete_product,
    schedule_index_product,
    schedule_index_store_products,
)
from store.models import Store


@receiver(pre_save, sender=Store)
def remember_store_search_state(
    sender: type[Store], instance: Store, **kwargs: Any
) -> None:
    if not instance.pk:
        instance._search_state_changed = False
        return
    previous = (
        Store.objects.filter(pk=instance.pk)
        .values("status", "verified_at")
        .first()
    )
    instance._search_state_changed = bool(
        previous
        and (
            previous["status"] != instance.status
            or previous["verified_at"] != instance.verified_at
        )
    )


@receiver(post_save, sender=Store)
def sync_store_products_to_search(
    sender: type[Store], instance: Store, created: bool, **kwargs: Any
) -> None:
    if not created and getattr(instance, "_search_state_changed", False):
        schedule_index_store_products(instance.pk)
        transaction.on_commit(
            lambda store_id=instance.pk: _invalidate_store_product_payloads(store_id)
        )


def _invalidate_store_product_payloads(store_id: int) -> None:
    from product.cache import invalidate_store_product_payload_cache

    invalidate_store_product_payload_cache(store_id)


@receiver(post_save, sender=Product)
def sync_product_to_search(
    sender: type[Product], instance: Product, **kwargs: Any
) -> None:
    schedule_index_product(instance.pk)


@receiver(post_delete, sender=Product)
def remove_product_from_search(
    sender: type[Product], instance: Product, **kwargs: Any
) -> None:
    schedule_delete_product(instance.pk)
