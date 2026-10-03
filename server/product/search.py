from __future__ import annotations

import logging
from typing import Any, Optional

from django.conf import settings
from django.db import transaction

from product.models import Product

logger = logging.getLogger("codematics.search")


def enabled() -> bool:
    return bool(getattr(settings, "ELASTICSEARCH_ENABLED", False))


def client() -> Any:
    from elasticsearch import Elasticsearch

    return Elasticsearch(
        settings.ELASTICSEARCH_URL,
        request_timeout=settings.ELASTICSEARCH_TIMEOUT,
        retry_on_timeout=True,
        max_retries=1,
    )


def product_document(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "title": product.title,
        "description": product.description,
        "brand": product.brand,
        "category": product.category,
        "store_id": product.store_id,
        "store_status": product.store.status,
        "store_verified": product.store.verified_at is not None,
        "visibility": product.visibility,
        "price": float(product.price),
        "discount": product.discount,
        "available": product.available,
        "average_rating": float(product.average_rating),
        "sales": product.sales,
        "sponsored": product.sponsored,
        "tags": [tag.name for tag in product.tags.all()],
        "created": product.created.isoformat() if product.created else None,
    }


def ensure_products_index(es: Any = None) -> bool:
    if not enabled():
        return False
    es = es or client()
    index = settings.ELASTICSEARCH_PRODUCTS_INDEX
    if es.indices.exists(index=index):
        return True
    es.indices.create(
        index=index,
        mappings={
            "properties": {
                "id": {"type": "integer"},
                "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "description": {"type": "text"},
                "brand": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "category": {"type": "keyword"},
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
    return True


def index_product(product_id: int) -> None:
    if not enabled():
        return
    try:
        product = Product.objects.select_related("store").prefetch_related("tags").get(pk=product_id)
        es = client()
        ensure_products_index(es)
        es.index(
            index=settings.ELASTICSEARCH_PRODUCTS_INDEX,
            id=product.id,
            document=product_document(product),
        )
    except Product.DoesNotExist:
        delete_product(product_id)
    except Exception:
        logger.exception("Failed to index product in Elasticsearch", extra={"product_id": product_id})


def delete_product(product_id: int) -> None:
    if not enabled():
        return
    try:
        client().delete(
            index=settings.ELASTICSEARCH_PRODUCTS_INDEX,
            id=product_id,
            ignore=[404],
        )
    except Exception:
        logger.exception("Failed to delete product from Elasticsearch", extra={"product_id": product_id})


def schedule_index_product(product_id: int) -> None:
    if enabled():
        transaction.on_commit(lambda: index_product(product_id))


def schedule_delete_product(product_id: int) -> None:
    if enabled():
        transaction.on_commit(lambda: delete_product(product_id))


def search_product_ids(
    query: str,
    filters: Optional[dict[str, Any]] = None,
    ordering: str = "-created",
    offset: int = 0,
    limit: int = 24,
) -> Optional[dict[str, Any]]:
    if not enabled() or not query:
        return None
    filters = filters or {}
    must = [{
        "multi_match": {
            "query": query,
            "fields": ["title^4", "brand^3", "category^2", "tags^2", "description"],
            "fuzziness": "AUTO",
        }
    }]
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
    }.get(ordering, [{"created": "desc"}])
    try:
        response = client().search(
            index=settings.ELASTICSEARCH_PRODUCTS_INDEX,
            query={"bool": {"must": must, "filter": filter_clauses}},
            sort=sort + [{"id": "desc"}],
            from_=offset,
            size=limit,
            track_total_hits=True,
        )
    except Exception:
        logger.exception("Elasticsearch product search failed")
        return None
    hits = response["hits"]["hits"]
    total = response["hits"]["total"]
    if isinstance(total, dict):
        total = total["value"]
    return {
        "ids": [int(hit["_id"]) for hit in hits],
        "count": int(total),
    }

