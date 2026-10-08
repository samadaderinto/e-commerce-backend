"""Propagate catalog revisions to store timestamps without changing ownership."""
from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from product.models import Product, ProductImg, Specification
from store.models import Store, StoreAddress, StoreInfo


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
@receiver(post_save, sender=ProductImg)
@receiver(post_delete, sender=ProductImg)
@receiver(post_save, sender=Specification)
@receiver(post_save, sender=StoreInfo)
@receiver(post_save, sender=StoreAddress)
def store_revision(sender: type, instance: Any, **kwargs: Any) -> None:
    if kwargs.get('raw'):
        return
    try:
        store_id = None
        if isinstance(instance, (ProductImg, Specification)):
            product = getattr(instance, 'product', None)
            if product:
                store_id = getattr(product, 'store_id', None)
            elif hasattr(instance, 'product_id') and instance.product_id:
                store_id = Product.objects.filter(pk=instance.product_id).values_list('store_id', flat=True).first()
        else:
            store_id = getattr(instance, 'store_id', None)
        if store_id:
            Store.objects.filter(pk=store_id).update(updated=timezone.now())
    except Exception:
        pass
