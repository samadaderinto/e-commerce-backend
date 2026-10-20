"""Background Elasticsearch synchronization for catalog writes."""
from __future__ import annotations

import logging
from collections.abc import Callable

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from product.models import SearchIndexJob

from product.search import delete_product, enabled, index_product, index_store_products

logger = logging.getLogger("codematics.search")


def _execute_intent(action: str, target_id: int, operation: Callable[..., None]) -> None:
    if not enabled():
        return
    # Serialize duplicate workers; never acknowledge a refreshed revision.
    with transaction.atomic():
        job = SearchIndexJob.objects.select_for_update().filter(
            action=action, target_id=target_id
        ).first()
        if job is None:
            return
        revision = job.revision
        operation(target_id, strict=True)
        SearchIndexJob.objects.filter(pk=job.pk, revision=revision).delete()


@shared_task(
    ignore_result=True, name="product.tasks.index_product_task",
    autoretry_for=(Exception,), retry_backoff=5, retry_backoff_max=300,
    retry_jitter=True, max_retries=5,
)
def index_product_task(product_id: int) -> None:
    _execute_intent(SearchIndexJob.INDEX_PRODUCT, product_id, index_product)


@shared_task(
    ignore_result=True, name="product.tasks.index_store_products_task",
    autoretry_for=(Exception,), retry_backoff=5, retry_backoff_max=300,
    retry_jitter=True, max_retries=5,
)
def index_store_products_task(store_id: int) -> None:
    _execute_intent(SearchIndexJob.INDEX_STORE, store_id, index_store_products)


@shared_task(
    ignore_result=True, name="product.tasks.delete_product_task",
    autoretry_for=(Exception,), retry_backoff=5, retry_backoff_max=300,
    retry_jitter=True, max_retries=5,
)
def delete_product_task(product_id: int) -> None:
    _execute_intent(SearchIndexJob.DELETE_PRODUCT, product_id, delete_product)


@shared_task(ignore_result=True, name="product.tasks.recover_search_index_jobs")
def recover_search_index_jobs(limit: int = 100) -> int:
    """Rotate a bounded batch fairly; publishing does not clear an intent."""
    if not enabled():
        return 0
    tasks = {
        SearchIndexJob.INDEX_PRODUCT: index_product_task,
        SearchIndexJob.INDEX_STORE: index_store_products_task,
        SearchIndexJob.DELETE_PRODUCT: delete_product_task,
    }
    jobs = list(
        SearchIndexJob.objects.order_by("updated_at", "pk")[:max(0, min(limit, 100))]
    )
    published = 0
    for job in jobs:
        # Rotate failed publications too, preventing starvation by a bad batch.
        SearchIndexJob.objects.filter(pk=job.pk, revision=job.revision).update(
            updated_at=timezone.now()
        )
        try:
            tasks[job.action].apply_async(args=(job.target_id,))
            published += 1
        except Exception:
            logger.exception("Unable to recover search intent", extra={"job_id": job.pk})
    return published
