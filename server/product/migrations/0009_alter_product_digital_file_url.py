from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('product', '0008_product_variants')]
    operations = [migrations.AlterField(model_name='product', name='digital_file_url', field=models.CharField(blank=True, default='', max_length=1000, help_text='Private storage key exposed through authenticated, expiring download links.'))]
