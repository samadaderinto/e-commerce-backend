# Generated by Django 4.1.4 on 2023-08-04 22:59

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cart", "0005_alter_cart_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cart",
            name="id",
            field=models.CharField(
                default="rTIHG2TS82iF_Nr",
                editable=False,
                max_length=15,
                primary_key=True,
                serialize=False,
                unique=True,
            ),
        ),
    ]