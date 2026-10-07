from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('product', '0009_alter_product_digital_file_url')]
    operations = [migrations.AddField(model_name='product', name='digital_preview_watermark', field=models.BooleanField(default=False, help_text='Overlay buyer-specific watermark on in-platform previews of digital images.'))]
