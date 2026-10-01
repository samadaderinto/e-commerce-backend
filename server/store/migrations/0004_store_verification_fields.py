from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def move_unverified_active_stores_to_pending(apps, schema_editor):
    Store = apps.get_model("store", "Store")
    Store.objects.filter(status="active", verified_at__isnull=True).update(status="pending")


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("store", "0003_store_moderation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="store",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "pending"),
                    ("active", "active"),
                    ("blocked", "blocked"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="store",
            name="verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="store",
            name="verified_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="verified_stores",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(
            move_unverified_active_stores_to_pending,
            migrations.RunPython.noop,
        ),
    ]
