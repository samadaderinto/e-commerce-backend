"""Short-lived anonymous catalog snapshots; writes and authenticated reads stay authoritative."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.utils.dateparse import parse_datetime
from rest_framework.request import Request

from product.models import Product
from store.models import Store

REVISION_KEY = "storefront:catalog:revision"
WARM_LOCK_KEY = "storefront:catalog:warm:pending"
WARM_URL_KEY = "storefront:catalog:warm:url"
logger = logging.getLogger(__name__)


def invalidate_catalog_snapshot() -> None:
    def committed() -> None:
        cache.set(REVISION_KEY, uuid4().hex, timeout=None)
        if (
            getattr(settings, "PUBLIC_CATALOG_CACHE_SECONDS", 15) > 0
            and getattr(settings, "CATALOG_CACHE_WARM_ENABLED", True)
            and cache.add(WARM_LOCK_KEY, True, timeout=10)
        ):
            from .tasks import warm_catalog_snapshot

            try:
                warm_catalog_snapshot.apply_async(retry=False)
            except Exception:
                cache.delete(WARM_LOCK_KEY)
                logger.exception("Unable to enqueue catalog snapshot warming")

    transaction.on_commit(committed)


def snapshot_key(request: Request) -> str | None:
    if (
        request.user.is_authenticated
        or connection.in_atomic_block
        or getattr(settings, "PUBLIC_CATALOG_CACHE_SECONDS", 15) <= 0
        or request.query_params.get("search")
        or len(request.get_full_path()) > 1024
    ):
        return None
    # Store timestamps are updated transactionally by catalog dependency signals.
    # This also changes the key if Redis missed an invalidation during an outage.
    stamp = Store.objects.order_by("-updated").values_list("updated", flat=True).first()
    if stamp is None:
        return None
    revision = cache.get_or_set(REVISION_KEY, uuid4().hex, timeout=None)
    if not isinstance(revision, str):
        return None
    identity = json.dumps(
        [
            revision,
            stamp.isoformat(),
            request.build_absolute_uri(),
            sorted(request.query_params.lists()),
        ],
        sort_keys=True,
    )
    return "storefront:catalog:" + hashlib.sha256(identity.encode()).hexdigest()


def read_snapshot(key: str | None) -> dict[str, Any] | None:
    if key is None:
        return None
    data = cache.get(key)
    if not isinstance(data, dict) or not data.get("results"):
        return None
    items = {item["id"]: item for item in data["results"]}
    # Permissions, price, stock, and variants are checked even on a cache hit.
    # A bulk update that bypasses model signals must not expose blocked products
    # or return an old checkout price/stock value.
    rows = Product.objects.filter(
        pk__in=items,
        visibility=True,
        store__status=Store.STATUS_ACTIVE,
        store__verified_at__isnull=False,
    ).values("id", "updated", "store_id", "price", "discount", "available", "variants")
    current = list(rows)
    if len(current) != len(items):
        return None
    for row in current:
        item = items[row["id"]]
        if (
            row["updated"] != parse_datetime(item["updated"])
            or row["store_id"] != item["store"]
            or str(row["price"]) != item["price"]
            or row["discount"] != item["discount"]
            or row["available"] != item["available"]
            or row["variants"] != item["variants"]
        ):
            return None
    return data


def write_snapshot(
    key: str | None, data: dict[str, Any], warm_url: str | None = None
) -> None:
    if key is None or not data.get("results"):
        return
    cache.set(
        key, data, timeout=getattr(settings, "PUBLIC_CATALOG_CACHE_SECONDS", 15)
    )
    if warm_url:
        cache.set(WARM_URL_KEY, warm_url, timeout=3600)
