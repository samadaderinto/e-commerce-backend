from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0002_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='label',
            field=models.CharField(
                choices=[
                    ('new', 'new'),
                    ('', 'none'),
                    ('bestseller', 'bestseller'),
                    ('sold out', 'sold out'),
                ],
                default='new',
                max_length=50,
            ),
        ),
    ]
