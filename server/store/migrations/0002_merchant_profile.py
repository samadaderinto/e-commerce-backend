from django.db import migrations
import phonenumber_field.modelfields


class Migration(migrations.Migration):
    dependencies = [('store', '0001_initial')]

    operations = [
        migrations.RenameField(model_name='storeinfo', old_name='contact_email', new_name='email'),
        migrations.RenameField(model_name='storeinfo', old_name='whatsapp1', new_name='whatsapp'),
        migrations.AlterField(
            model_name='storeinfo', name='whatsapp',
            field=phonenumber_field.modelfields.PhoneNumberField(blank=True, null=True, max_length=128, region=None),
        ),
        migrations.AlterField(
            model_name='storeinfo', name='phone1',
            field=phonenumber_field.modelfields.PhoneNumberField(blank=True, null=True, max_length=128, region=None),
        ),
    ]
