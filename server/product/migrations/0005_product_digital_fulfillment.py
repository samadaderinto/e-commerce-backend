from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('product', '0004_catalog_presentation')]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_digital',
            field=models.BooleanField(
                default=False,
                help_text='Digital products are delivered online and may be sold worldwide.',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='digital_file_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='Private fulfillment link shown only in the customer order.',
                max_length=1000,
            ),
        ),
    ]
