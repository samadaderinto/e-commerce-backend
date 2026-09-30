from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("event_notification", "0001_initial"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="notification",
            new_name="notif_rec_unread_idx",
            old_fields=("recipient", "unread"),
        ),
    ]
