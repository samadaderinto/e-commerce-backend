"""Repair existing inbox associations without dispatching messages."""
import hashlib

from django.db import migrations


def backfill(apps, schema_editor):
    Notification = apps.get_model("event_notification", "Notification")
    Store = apps.get_model("store", "Store")
    Order = apps.get_model("payment", "Order")
    User = apps.get_model("core", "User")
    seen = set()
    for row in Notification.objects.order_by("-timestamp", "-pk").iterator():
        data = dict(row.data or {})
        text = f"{data.get('event', '')} {row.verb}".lower()
        explicit = data.get("category")
        category = explicit if explicit in {"order", "refund", "payout", "wallet", "store", "affiliates", "account", "general"} else "general"
        if not explicit:
            for name, keywords in [
                ("affiliates", ["affiliate", "referral"]), ("refund", ["refund"]),
                ("payout", ["payout", "withdrawal"]), ("wallet", ["wallet", "deposit"]),
                ("order", ["order", "shipping"]), ("store", ["store", "inventory", "verification_submitted"]),
                ("account", ["account", "password", "staff"]),
            ]:
                if any(word in text for word in keywords):
                    category = name
                    break
        ids = list(data.get("store_ids") or []) + [data.get("store_id"), data.get("store")]
        for ct_id, object_id in [(row.target_content_type_id, row.target_object_id), (row.action_object_content_type_id, row.action_object_object_id)]:
            if ct_id and object_id:
                ct = apps.get_model("contenttypes", "ContentType").objects.get(pk=ct_id)
                if ct.model == "store":
                    ids.append(object_id)
        ids = {int(value) for value in ids if str(value).isdigit()}
        order = Order.objects.filter(pk=data.get("order_id")).first() if str(data.get("order_id", "")).isdigit() else None
        if not ids and order:
            ids = {int(item["store"]) for item in order.items_snapshot or [] if item.get("store")}
        user = User.objects.get(pk=row.recipient_id)
        stores = Store.objects.filter(pk__in=ids)
        if order and order.user_id != user.pk and not (user.is_superuser or user.is_business_admin):
            from django.db.models import Q
            stores = stores.filter(Q(user_id=user.pk) | Q(assigned_staff=user.pk) | Q(is_official=True, user__isnull=False) if user.is_staff else Q(user_id=user.pk))
        row.stores.set(stores.distinct())
        changes = {"category": category}
        if order and data.get("event") == "order_placed":
            key = (row.recipient_id, order.pk)
            if key not in seen:
                changes["event_key"] = hashlib.sha256(f"order:{order.pk}:placed".encode()).hexdigest()
                seen.add(key)
            else:
                changes["deleted"] = True
        Notification.objects.filter(pk=row.pk).update(**changes)
    for row in Notification.objects.filter(data__event="new_order").iterator():
        order_id = (row.data or {}).get("order_id")
        if Notification.objects.filter(recipient_id=row.recipient_id, data__event="order_placed", data__order_id=order_id).exists():
            Notification.objects.filter(pk=row.pk).update(deleted=True)


class Migration(migrations.Migration):
    dependencies = [
        ("event_notification", "0007_notification_category_notification_event_key_and_more"),
        ("payment", "0020_order_order_settlement_within_total_and_more"),
    ]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
