from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('product', '0014_digital_product_categories')]

    operations = [
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['-created', '-id'], name='catalog_created_id_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['category', '-created', '-id'], name='catalog_category_page_idx'),
        ),
    ]
