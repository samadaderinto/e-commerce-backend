"""Background Elasticsearch synchronization for catalog writes."""
from __future__ import annotations

from celery import shared_task

from product.search import delete_product, index_product, index_store_products


@shared_task(ignore_result=True, name="product.tasks.index_product_task")
def index_product_task(product_id: int) -> None:
    index_product(product_id)


@shared_task(ignore_result=True, name="product.tasks.index_store_products_task")
def index_store_products_task(store_id: int) -> None:
    index_store_products(store_id)


@shared_task(ignore_result=True, name="product.tasks.delete_product_task")
def delete_product_task(product_id: int) -> None:
    delete_product(product_id)
