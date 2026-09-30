from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("store", "0002_merchant_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="status",
            field=models.CharField(
                choices=[("active", "active"), ("blocked", "blocked")],
                default="active",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="store",
            name="blocked_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="store",
            name="blocked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="store",
            name="blocked_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="blocked_stores",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
