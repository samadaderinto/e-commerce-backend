from django.db import migrations, models
from django.core.validators import MinValueValidator
from decimal import Decimal

class Migration(migrations.Migration):
    dependencies = [('product', '0010_product_digital_preview_watermark')]
    operations = [
        migrations.AddField(model_name='product', name='length', field=models.DecimalField(blank=True, decimal_places=2, help_text='Package length in inches.', max_digits=7, null=True, validators=[MinValueValidator(Decimal('0.01'))])),
        migrations.AddField(model_name='product', name='width', field=models.DecimalField(blank=True, decimal_places=2, help_text='Package width in inches.', max_digits=7, null=True, validators=[MinValueValidator(Decimal('0.01'))])),
        migrations.AddField(model_name='product', name='height', field=models.DecimalField(blank=True, decimal_places=2, help_text='Package height in inches.', max_digits=7, null=True, validators=[MinValueValidator(Decimal('0.01'))])),
    ]
