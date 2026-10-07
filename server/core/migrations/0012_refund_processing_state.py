from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def initialize_refund_status(apps, schema_editor):
    Refund = apps.get_model('core', 'Refund')
    Refund.objects.filter(accepted=True).update(status='approved')


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0011_alter_refund_order_alter_userwallet_user'),
    ]
    operations = [
        migrations.AddField(
            model_name='refund', name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('declined', 'Declined')], db_index=True, default='pending', max_length=12),
        ),
        migrations.AddField(
            model_name='refund', name='processed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='refund', name='processed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='processed_refunds', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(initialize_refund_status, migrations.RunPython.noop),
    ]
