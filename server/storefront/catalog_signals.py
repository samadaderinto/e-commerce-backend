"""Invalidate anonymous snapshots only after commit, including related catalog edits."""

from __future__ import annotations

import logging
from typing import Any
from django.db import DatabaseError, transaction
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from taggit.models import Tag, TaggedItem

from core.models import Review
from product.models import Product, ProductImg, Specification
from store.models import Store, StoreEarningsLedger
from .catalog_cache import invalidate_catalog_snapshot

logger = logging.getLogger("codematics.catalog_cache")


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
@receiver(post_save, sender=ProductImg)
@receiver(post_delete, sender=ProductImg)
@receiver(post_save, sender=Specification)
@receiver(post_delete, sender=Specification)
@receiver(post_save, sender=Review)
@receiver(post_delete, sender=Review)
@receiver(post_save, sender=Store)
@receiver(post_delete, sender=Store)
@receiver(post_save, sender=StoreEarningsLedger)
@receiver(post_delete, sender=StoreEarningsLedger)
def catalog_changed(sender: type, instance: Any, **kwargs: Any) -> None:
    if kwargs.get("raw"):
        return
    if isinstance(instance, StoreEarningsLedger):
        store_id = instance.store_id

        def earnings_committed() -> None:
            # Do not introduce Store row locks into wallet/earnings transactions.
            if store_id:
                try:
                    Store.objects.filter(pk=store_id).update(updated=timezone.now())
                except DatabaseError:
                    logger.warning(
                        "Earnings catalog revision unavailable", exc_info=True
                    )
            invalidate_catalog_snapshot()

        transaction.on_commit(earnings_committed)
        return
    if not isinstance(instance, Store):
        store_id = getattr(instance, "store_id", None)
        if store_id is None:
            store_id = (
                Product.objects.filter(
                    pk=getattr(instance, "product_id", None),
                )
                .values_list("store_id", flat=True)
                .first()
            )
        if store_id:
            Store.objects.filter(pk=store_id).update(updated=timezone.now())
    if isinstance(instance, Product):
        product_id = instance.pk
        product_store_id = instance.store_id
        transaction.on_commit(
            lambda: _invalidate_product_payload(product_id, product_store_id)
        )
    elif isinstance(instance, ProductImg):
        product_id = instance.product_id
        product_store_id = Product.objects.filter(pk=product_id).values_list(
            "store_id", flat=True
        ).first()
        if product_store_id is not None:
            transaction.on_commit(
                lambda: _invalidate_product_payload(product_id, product_store_id)
            )
    invalidate_catalog_snapshot()


def _invalidate_product_payload(product_id: int, store_id: int) -> None:
    from product.cache import invalidate_product_payload_cache

    invalidate_product_payload_cache(product_id, store_id)


@receiver(post_save, sender=Tag)
@receiver(pre_delete, sender=Tag)
def tag_changed(sender: type, instance: Tag, **kwargs: Any) -> None:
    if kwargs.get("raw"):
        return
    products = tuple(Product.objects.filter(tags=instance).values_list("pk", "store_id"))
    stores = {store_id for _, store_id in products}
    Store.objects.filter(pk__in=stores).update(updated=timezone.now())
    transaction.on_commit(lambda: _invalidate_product_payloads(products))
    invalidate_catalog_snapshot()


def _invalidate_product_payloads(products: tuple[tuple[int, int], ...]) -> None:
    from product.cache import invalidate_product_payload_caches

    invalidate_product_payload_caches(products)


@receiver(m2m_changed, sender=TaggedItem)
def product_tags_changed(
    sender: type,
    instance: Any,
    action: str,
    **kwargs: Any,
) -> None:
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    if isinstance(instance, Product):
        Store.objects.filter(pk=instance.store_id).update(updated=timezone.now())
        products = ((instance.pk, instance.store_id),)
    elif isinstance(instance, Tag):
        products = tuple(Product.objects.filter(tags=instance).values_list("pk", "store_id"))
        stores = {store_id for _, store_id in products}
        Store.objects.filter(pk__in=stores).update(updated=timezone.now())
    else:
        # TaggedItem is shared by products and other tagged models, such as posts.
        return
    transaction.on_commit(lambda: _invalidate_product_payloads(products))
    invalidate_catalog_snapshot()
