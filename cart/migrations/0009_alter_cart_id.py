# Generated by Django 4.1.4 on 2023-07-22 10:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0008_alter_cart_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cart',
            name='id',
            field=models.CharField(default='6nrMvQvOhkVOyMG', editable=False, max_length=15, primary_key=True, serialize=False, unique=True),
        ),
    ]
