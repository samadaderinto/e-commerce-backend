import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product", "0017_product_drop_at")]

    operations = [
        migrations.CreateModel(
            name="SearchIndexJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("index_product", "Index product"), ("index_store", "Index store products"), ("delete_product", "Delete product")], max_length=20)),
                ("target_id", models.PositiveBigIntegerField()),
                ("revision", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("action", "target_id"), name="search_job_action_target_unique")],
            },
        ),
    ]
