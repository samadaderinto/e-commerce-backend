from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("event_notification", "0002_rename_notification_recipient_unread_notif_rec_unread_idx"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="data",
            field=models.JSONField(blank=True, null=True, verbose_name="data"),
        ),
    ]
