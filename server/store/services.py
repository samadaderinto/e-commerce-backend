from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from product.models import Product
from store.models import Schedule, Store


@transaction.atomic
def publish_due_products() -> int:
    from store.views import invalidate_catalog

    count = 0
    schedules = Schedule.objects.select_for_update().select_related('store').filter(
        make_visible_at__lte=timezone.now()
    )
    for schedule in schedules:
        store = schedule.store
        if store.status != Store.STATUS_ACTIVE or store.verified_at is None:
            continue
        product = Product.objects.select_for_update().filter(pk=schedule.product_id, store_id=schedule.store_id).first()
        if product is not None:
            product.visibility = True
            product.save(update_fields=['visibility', 'updated'])
            transaction.on_commit(lambda product=product: invalidate_catalog(product))
            count += 1
        schedule.delete()
    return count

