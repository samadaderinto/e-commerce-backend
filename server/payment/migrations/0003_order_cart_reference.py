from django.db import migrations, models
import payment.models


class Migration(migrations.Migration):
    dependencies = [('payment', '0002_initial')]

    operations = [
        migrations.RenameField(model_name='order', old_name='cartId', new_name='cart'),
        migrations.AlterField(
            model_name='order', name='orderId',
            field=models.CharField(default=payment.models.generate_order_reference,
                                   editable=False, max_length=15, unique=True),
        ),
    ]
