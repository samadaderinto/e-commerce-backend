from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('product', '0003_alter_product_label')]
    operations = [
        migrations.AddField(model_name='product', name='image_url', field=models.URLField(blank=True, default='', max_length=1000)),
        migrations.AddField(model_name='product', name='brand', field=models.CharField(blank=True, default='', max_length=80)),
    ]
