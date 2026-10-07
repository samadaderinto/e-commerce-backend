from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0013_refund_failure_reason_refund_provider_reference_and_more")]
    operations = [
        migrations.AddField(
            model_name="user",
            name="staff_blocked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
