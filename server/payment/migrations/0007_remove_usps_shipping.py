from django.db import migrations, models


def normalize_delivery_types(apps, schema_editor):
    delivery_info = apps.get_model('payment', 'DeliveryInfo')
    delivery_info.objects.filter(
        delivery_type__in=['priority', 'firstclass']
    ).update(delivery_type='standard')


def restore_delivery_types(apps, schema_editor):
    delivery_info = apps.get_model('payment', 'DeliveryInfo')
    delivery_info.objects.filter(delivery_type='standard').update(
        delivery_type='priority'
    )


class Migration(migrations.Migration):
    dependencies = [('payment', '0006_order_stripe_session')]

    operations = [
        migrations.RunPython(normalize_delivery_types, restore_delivery_types),
        migrations.AlterField(
            model_name='deliveryinfo',
            name='delivery_type',
            field=models.CharField(
                choices=[('standard', 'Standard'), ('express', 'Express')],
                max_length=150,
            ),
        ),
        migrations.DeleteModel(name='DeliveryEstimates'),
    ]
