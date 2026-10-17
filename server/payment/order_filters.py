"""Store membership from immutable order items, with a legacy cart fallback."""

from django.db import connections
from django.db.models import Q, QuerySet
from django.db.models.expressions import RawSQL

from payment.models import Order


def orders_for_store(orders: QuerySet[Order], store_id: int) -> QuerySet[Order]:
    database = connections[orders.db]
    if database.vendor == "sqlite":
        table = database.ops.quote_name(Order._meta.db_table)
        # Keep JSON membership self-contained: Django may rename the outer
        # table when this queryset is embedded in dashboard aggregate queries.
        snapshot = Q(
            pk__in=RawSQL(
                f"SELECT snapshot_order.id FROM {table} AS snapshot_order "
                "WHERE EXISTS (SELECT 1 FROM json_each(snapshot_order.items_snapshot) AS item "
                "WHERE CAST(json_extract(item.value, '$.store') AS TEXT) = %s)",
                [str(store_id)],
            )
        )
    else:
        snapshot = Q(items_snapshot__contains=[{"store": store_id}]) | Q(
            items_snapshot__contains=[{"store": str(store_id)}],
        )
    legacy = (Q(items_snapshot=[]) | Q(items_snapshot__isnull=True)) & Q(
        cart__cart_items__product__store_id=store_id,
    )
    return orders.filter(
        snapshot | legacy | Q(fulfillments__store_id=store_id)
    ).distinct()
