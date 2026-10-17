from django.contrib.postgres.indexes import GinIndex
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("payment", "0020_order_order_settlement_within_total_and_more")]

    operations = [
        migrations.AddIndex(
            model_name="order",
            index=GinIndex(fields=["items_snapshot"], name="order_items_store_gin"),
        ),
    ]
