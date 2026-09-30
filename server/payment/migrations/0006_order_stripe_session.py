from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('payment', '0005_coupon_rules')]
    operations = [migrations.AddField(
        model_name='order', name='stripe_session_id',
        field=models.CharField(blank=True, max_length=255, null=True, unique=True),
    )]
