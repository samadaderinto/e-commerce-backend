from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0015_refund_selected_items_refund_amount')]
    operations = [migrations.AddField(model_name='refund', name='processing_reason', field=models.TextField(blank=True, default=''))]
