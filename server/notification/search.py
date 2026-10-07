from __future__ import annotations

import logging
from typing import Any, Optional

from django.conf import settings
from django.db import transaction

from notification.models import Notification

logger = logging.getLogger("codematics.notification_search")


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


def extract_category_and_store(notification: Notification) -> tuple[str, Optional[int], Optional[str]]:
    data = notification.data or {}
    event = str(data.get("event") or "").lower()
    verb = (notification.verb or "").lower()
    target_model = (
        notification.target_content_type.model
        if notification.target_content_type
        else ""
    ).lower()

    if data.get("category"):
        category = str(data["category"]).lower()
    elif (
        "referral" in event
        or "affiliate" in event
        or "referral" in verb
        or "affiliate" in verb
    ):
        category = "affiliates"
    elif "refund" in event or "refund" in verb or target_model == "refund":
        category = "refund"
    elif (
        "payout" in event
        or "payout" in verb
        or "withdrawal" in event
        or "withdrawal" in verb
        or target_model == "storepayout"
    ):
        category = "payout"
    elif "store" in event or "store" in verb or target_model == "store":
        category = "store"
    elif "order" in event or "order" in verb or target_model == "order":
        category = "order"
    else:
        category = "general"

    store_id = None
    store_name = None
    raw_sid = data.get("store_id") or data.get("store")
    if raw_sid and str(raw_sid).isdigit():
        store_id = int(raw_sid)
    elif target_model == "store" and str(notification.target_object_id).isdigit():
        store_id = int(notification.target_object_id)
    elif (
        notification.action_object_content_type
        and notification.action_object_content_type.model == "store"
        and str(notification.action_object_object_id).isdigit()
    ):
        store_id = int(notification.action_object_object_id)

    if store_id:
        try:
            from store.models import Store

            store_obj = Store.objects.filter(pk=store_id).first()
            if store_obj:
                store_name = store_obj.name
        except Exception:
            pass

    return category, store_id, store_name


def notification_document(notification: Notification) -> dict[str, Any]:
    category, store_id, store_name = extract_category_and_store(notification)
    return {
        "id": notification.id,
        "recipient_id": notification.recipient_id,
        "verb": notification.verb,
        "description": notification.description or "",
        "level": notification.level,
        "category": category,
        "store_id": store_id,
        "store_name": store_name or "",
        "unread": notification.unread,
        "deleted": notification.deleted,
        "public": notification.public,
        "timestamp": notification.timestamp.isoformat() if notification.timestamp else None,
    }


def ensure_notifications_index(es: Any = None) -> bool:
    if not enabled():
        return False
    from elasticsearch.exceptions import ApiError, BadRequestError

    es = es or client()
    index = getattr(
        settings,
        "ELASTICSEARCH_NOTIFICATIONS_INDEX",
        f"{getattr(settings, 'ELASTICSEARCH_INDEX_PREFIX', 'commerce')}-notifications",
    )
    try:
        if es.indices.exists(index=index):
            return True
        es.indices.create(
            index=index,
            mappings={
                "properties": {
                    "id": {"type": "integer"},
                    "recipient_id": {"type": "integer"},
                    "verb": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "description": {"type": "text"},
                    "level": {"type": "keyword"},
                    "category": {"type": "keyword"},
                    "store_id": {"type": "integer"},
                    "store_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "unread": {"type": "boolean"},
                    "deleted": {"type": "boolean"},
                    "public": {"type": "boolean"},
                    "timestamp": {"type": "date"},
                }
            },
        )
        return True
    except (BadRequestError, ApiError) as exc:
        if "resource_already_exists_exception" in str(exc) or getattr(exc, "status_code", None) == 400:
            return True
        raise


def index_notification(notification_id: int) -> None:
    if not enabled():
        return
    try:
        notification = Notification.objects.select_related(
            "recipient",
            "actor_content_type",
            "target_content_type",
            "action_object_content_type",
        ).get(pk=notification_id)
        es = client()
        ensure_notifications_index(es)
        index = getattr(
            settings,
            "ELASTICSEARCH_NOTIFICATIONS_INDEX",
            f"{getattr(settings, 'ELASTICSEARCH_INDEX_PREFIX', 'commerce')}-notifications",
        )
        es.index(
            index=index,
            id=notification.id,
            document=notification_document(notification),
        )
    except Notification.DoesNotExist:
        delete_notification(notification_id)
    except Exception:
        logger.exception("Failed to index notification in Elasticsearch", extra={"notification_id": notification_id})


def delete_notification(notification_id: int) -> None:
    if not enabled():
        return
    try:
        index = getattr(
            settings,
            "ELASTICSEARCH_NOTIFICATIONS_INDEX",
            f"{getattr(settings, 'ELASTICSEARCH_INDEX_PREFIX', 'commerce')}-notifications",
        )
        client().delete(
            index=index,
            id=notification_id,
            ignore=[404],
        )
    except Exception:
        logger.exception("Failed to delete notification from Elasticsearch", extra={"notification_id": notification_id})


def schedule_index_notification(notification_id: int) -> None:
    if enabled():
        transaction.on_commit(lambda: index_notification(notification_id))


def schedule_delete_notification(notification_id: int) -> None:
    if enabled():
        transaction.on_commit(lambda: delete_notification(notification_id))


def search_notification_ids(
    query: str,
    recipient_id: int,
    filters: Optional[dict[str, Any]] = None,
    offset: int = 0,
    limit: int = 20,
) -> Optional[dict[str, Any]]:
    if not enabled() or not query:
        return None
    filters = filters or {}
    must = [{
        "multi_match": {
            "query": query,
            "fields": ["verb^4", "description^2", "store_name^2", "category"],
            "fuzziness": "AUTO",
        }
    }]

    filter_clauses = [
        {"term": {"recipient_id": recipient_id}},
    ]

    include_archived = filters.get("include_archived", False)
    if not include_archived:
        filter_clauses.append({"term": {"deleted": False}})

    state = filters.get("state")
    if state == "unread":
        filter_clauses.append({"term": {"unread": True}})
    elif state == "read":
        filter_clauses.append({"term": {"unread": False}})

    category = filters.get("category")
    if category and category != "all":
        filter_clauses.append({"term": {"category": category}})

    store_id = filters.get("store_id")
    if store_id is not None:
        filter_clauses.append({"term": {"store_id": int(store_id)}})

    level = filters.get("level")
    if level:
        filter_clauses.append({"term": {"level": level}})

    index = getattr(
        settings,
        "ELASTICSEARCH_NOTIFICATIONS_INDEX",
        f"{getattr(settings, 'ELASTICSEARCH_INDEX_PREFIX', 'commerce')}-notifications",
    )

    try:
        response = client().search(
            index=index,
            query={"bool": {"must": must, "filter": filter_clauses}},
            sort=[{"timestamp": "desc"}, {"id": "desc"}],
            from_=offset,
            size=limit,
            track_total_hits=True,
        )
    except Exception:
        logger.exception("Elasticsearch notification search failed")
        return None

    hits = response["hits"]["hits"]
    total = response["hits"]["total"]
    if isinstance(total, dict):
        total = total["value"]
    return {
        "ids": [int(hit["_id"]) for hit in hits],
        "count": int(total),
    }
