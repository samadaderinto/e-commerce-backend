from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('payment', '0003_order_cart_reference')]
    operations = [
        migrations.AddField(model_name='order', name='items_snapshot', field=models.JSONField(default=list, blank=True)),
        migrations.AddField(model_name='order', name='address_snapshot', field=models.JSONField(default=dict, blank=True)),
        migrations.AddField(model_name='order', name='checkout_key', field=models.UUIDField(null=True, blank=True, unique=True)),
    ]
