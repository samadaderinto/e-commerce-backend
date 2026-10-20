from __future__ import annotations

import logging
import os
import uuid
from threading import Lock
from typing import TYPE_CHECKING
from typing import Any, Optional

from django.conf import settings
from django.db import transaction

from product.models import Product, SearchIndexJob

if TYPE_CHECKING:
    from elasticsearch import Elasticsearch

logger = logging.getLogger("codematics.search")
_client_instance: Elasticsearch | None = None
_client_config: tuple[int, str, float, int] | None = None
_client_lock = Lock()
_mapped_text_indices: set[tuple[int, str, str]] = set()


def _reset_client_after_fork() -> None:
    # Child workers must create their own sockets and cannot inherit a held lock.
    global _client_instance, _client_config, _client_lock, _mapped_text_indices
    _client_instance = None
    _client_config = None
    _client_lock = Lock()
    _mapped_text_indices = set()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_client_after_fork)


def enabled() -> bool:
    return bool(getattr(settings, "ELASTICSEARCH_ENABLED", False))


def client() -> Elasticsearch:
    from elasticsearch import Elasticsearch

    global _client_instance, _client_config
    config = (
        os.getpid(),
        settings.ELASTICSEARCH_URL,
        float(settings.ELASTICSEARCH_TIMEOUT),
        int(getattr(settings, 'ELASTICSEARCH_CONNECTIONS_PER_NODE', 32)),
    )
    with _client_lock:
        if _client_instance is None or config != _client_config:
            if (
                _client_instance is not None
                and _client_config
                and _client_config[0] == config[0]
            ):
                _client_instance.close()
            _client_instance = Elasticsearch(
                config[1],
                request_timeout=config[2],
                retry_on_timeout=True,
                max_retries=1,
                connections_per_node=config[3],
            )
            _client_config = config
        return _client_instance


def product_document(product: Product) -> dict[str, Any]:
    tags = [tag.name for tag in product.tags.all()]
    return {
        "id": product.id,
        "title": product.title,
        "description": product.description,
        "brand": product.brand,
        "category": product.category,
        "category_text": product.category,
        "store_id": product.store_id,
        "store_status": product.store.status,
        "store_verified": product.store.verified_at is not None,
        "visibility": product.visibility and not getattr(product, "is_blocked", False),
        "price": float(product.price),
        "discount": product.discount,
        "available": product.available,
        "average_rating": float(product.average_rating),
        "sales": product.sales,
        "sponsored": product.sponsored,
        "tags": tags,
        "tags_text": tags,
        "created": product.created.isoformat() if product.created else None,
    }


def ensure_products_index(es: Any = None) -> bool:
    if not enabled():
        return False
    from elasticsearch.exceptions import ApiError, BadRequestError

    es = es or client()
    index = settings.ELASTICSEARCH_PRODUCTS_INDEX
    mapping_key = (os.getpid(), settings.ELASTICSEARCH_URL, index)
    text_mappings = {
        "category_text": {"type": "text"},
        "tags_text": {"type": "text"},
    }
    try:
        if es.indices.exists(index=index):
            if mapping_key not in _mapped_text_indices:
                es.indices.put_mapping(index=index, properties=text_mappings)
                _mapped_text_indices.add(mapping_key)
            return True
        es.indices.create(
            index=index,
            mappings={
                "properties": {
                    "id": {"type": "integer"},
                    "title": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "description": {"type": "text"},
                    "brand": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "category": {"type": "keyword"},
                    **text_mappings,
                    "store_id": {"type": "integer"},
                    "store_status": {"type": "keyword"},
                    "store_verified": {"type": "boolean"},
                    "visibility": {"type": "boolean"},
                    "price": {"type": "double"},
                    "discount": {"type": "integer"},
                    "available": {"type": "integer"},
                    "average_rating": {"type": "double"},
                    "sales": {"type": "integer"},
                    "sponsored": {"type": "boolean"},
                    "tags": {"type": "keyword"},
                    "created": {"type": "date"},
                }
            },
        )
        _mapped_text_indices.add(mapping_key)
        return True
    except (BadRequestError, ApiError) as exc:
        if "resource_already_exists_exception" in str(exc):
            return True
        raise


def index_product(product_id: int, *, strict: bool = False) -> None:
    if not enabled():
        return
    try:
        product = (
            Product.objects.select_related("store")
            .prefetch_related("tags")
            .get(pk=product_id)
        )
        es = client()
        ensure_products_index(es)
        es.index(
            index=settings.ELASTICSEARCH_PRODUCTS_INDEX,
            id=product.id,
            document=product_document(product),
        )
    except Product.DoesNotExist:
        delete_product(product_id, strict=strict)
    except Exception:
        logger.exception(
            "Failed to index product in Elasticsearch", extra={"product_id": product_id}
        )
        if strict:
            raise


def index_store_products(store_id: int, *, strict: bool = False) -> None:
    if not enabled():
        return
    try:
        from elasticsearch.helpers import bulk

        es = client()
        ensure_products_index(es)
        products = (
            Product.objects.select_related("store")
            .prefetch_related("tags")
            .filter(store_id=store_id)
        )
        actions = (
            {
                "_index": settings.ELASTICSEARCH_PRODUCTS_INDEX,
                "_id": product.pk,
                "_source": product_document(product),
            }
            for product in products.iterator(chunk_size=100)
        )
        bulk(es, actions, chunk_size=100, raise_on_error=True)
        es.indices.refresh(index=settings.ELASTICSEARCH_PRODUCTS_INDEX)
    except Exception:
        logger.exception(
            "Failed to reindex store products in Elasticsearch",
            extra={"store_id": store_id},
        )
        if strict:
            raise


def delete_product(product_id: int, *, strict: bool = False) -> None:
    if not enabled():
        return
    try:
        client().delete(
            index=settings.ELASTICSEARCH_PRODUCTS_INDEX,
            id=product_id,
            ignore=[404],
        )
    except Exception:
        logger.exception(
            "Failed to delete product from Elasticsearch",
            extra={"product_id": product_id},
        )
        if strict:
            raise


def schedule_index_product(product_id: int) -> None:
    if enabled():
        SearchIndexJob.objects.update_or_create(
            action=SearchIndexJob.INDEX_PRODUCT, target_id=product_id,
            defaults={"revision": uuid.uuid4()},
        )

        def enqueue() -> None:
            try:
                from product.tasks import index_product_task

                index_product_task.apply_async(args=(product_id,))
            except Exception:
                logger.exception(
                    "Unable to enqueue product search indexing",
                    extra={"product_id": product_id},
                )

        transaction.on_commit(enqueue)


def schedule_index_store_products(store_id: int) -> None:
    if enabled():
        SearchIndexJob.objects.update_or_create(
            action=SearchIndexJob.INDEX_STORE, target_id=store_id,
            defaults={"revision": uuid.uuid4()},
        )

        def enqueue() -> None:
            try:
                from product.tasks import index_store_products_task

                index_store_products_task.apply_async(args=(store_id,))
            except Exception:
                logger.exception(
                    "Unable to enqueue store product search indexing",
                    extra={"store_id": store_id},
                )

        transaction.on_commit(enqueue)


def schedule_delete_product(product_id: int) -> None:
    if enabled():
        SearchIndexJob.objects.update_or_create(
            action=SearchIndexJob.DELETE_PRODUCT, target_id=product_id,
            defaults={"revision": uuid.uuid4()},
        )

        def enqueue() -> None:
            try:
                from product.tasks import delete_product_task

                delete_product_task.apply_async(args=(product_id,))
            except Exception:
                logger.exception(
                    "Unable to enqueue product search deletion",
                    extra={"product_id": product_id},
                )

        transaction.on_commit(enqueue)


def search_product_ids(
    query: str,
    filters: Optional[dict[str, Any]] = None,
    ordering: str | None = None,
    offset: int = 0,
    limit: int = 24,
    use_request_cache: bool = False,
) -> Optional[dict[str, Any]]:
    query = query.strip()
    # Elasticsearch token matching does not find a single-character substring
    # inside a token (for example, "k" in "Black kettle"). Let the catalog's
    # icontains fallback handle short fragments so partial searches stay useful.
    if not enabled() or len(query) < 3:
        return None
    mapping_key = (os.getpid(), settings.ELASTICSEARCH_URL, settings.ELASTICSEARCH_PRODUCTS_INDEX)
    filters = filters or {}
    search_fields = [
        "title^4",
        "brand^3",
        "category_text^2",
        "tags_text^2",
        "description",
    ]
    must = [
        {
            "multi_match": {
                "query": term,
                "fields": search_fields,
                "fuzziness": "AUTO",
            }
        }
        for term in query.split()
    ]
    filter_clauses = [
        {"term": {"visibility": True}},
        {"term": {"store_status": "active"}},
        {"term": {"store_verified": True}},
    ]
    for field in ("category", "store_id"):
        if filters.get(field) is not None:
            filter_clauses.append({"term": {field: filters[field]}})
    if filters.get("deals"):
        filter_clauses.append({"range": {"discount": {"gt": 0}}})
    price_range = {}
    if filters.get("min_price") is not None:
        price_range["gte"] = float(filters["min_price"])
    if filters.get("max_price") is not None:
        price_range["lte"] = float(filters["max_price"])
    if price_range:
        filter_clauses.append({"range": {"price": price_range}})
    sort = {
        "price": [{"price": "asc"}],
        "-price": [{"price": "desc"}],
        "-average_rating": [{"average_rating": "desc"}],
        "-sales": [{"sales": "desc"}],
        "-discount": [{"discount": "desc"}],
        "-created": [{"created": "desc"}],
    }.get(ordering, [{"_score": "desc"}, {"created": "desc"}])
    try:
        if mapping_key not in _mapped_text_indices:
            ensure_products_index()
        response = client().search(
            index=settings.ELASTICSEARCH_PRODUCTS_INDEX,
            query={"bool": {"must": must, "filter": filter_clauses}},
            sort=sort + [{"id": "desc"}],
            from_=offset,
            size=limit,
            track_total_hits=True,
            source=False,
            request_cache=use_request_cache and getattr(
                settings, "SEARCH_REQUEST_CACHE_ENABLED", True
            ),
            allow_partial_search_results=False,
        )
        if response.get('timed_out') or response.get('_shards', {}).get('failed', 0):
            logger.warning('Incomplete Elasticsearch result; using catalog fallback')
            return None
        hits = response["hits"]["hits"]
        total = response["hits"]["total"]
        if isinstance(total, dict):
            total = total["value"]
        return {
            "ids": [int(hit["_id"]) for hit in hits],
            "count": int(total),
        }
    except Exception:
        logger.exception("Elasticsearch product search failed")
        return None
