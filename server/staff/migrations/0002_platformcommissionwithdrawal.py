import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('staff', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name='PlatformCommissionWithdrawal', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('created', models.DateTimeField(auto_now_add=True)), ('updated', models.DateTimeField(auto_now=True)),
        ('amount', models.DecimalField(decimal_places=2, max_digits=15)), ('payout_method', models.CharField(max_length=50)),
        ('account_details', models.JSONField(default=dict)), ('status', models.CharField(choices=[('pending','pending'),('completed','completed'),('failed','failed')], default='pending', max_length=20)),
        ('reference', models.CharField(max_length=40, unique=True)),
        ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='commission_withdrawals', to=settings.AUTH_USER_MODEL)),
    ])]
