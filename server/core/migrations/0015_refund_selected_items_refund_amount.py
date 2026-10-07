from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0014_user_staff_blocked_at')]
    operations = [
        migrations.AddField(model_name='refund', name='selected_items', field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name='refund', name='refund_amount', field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
    ]
