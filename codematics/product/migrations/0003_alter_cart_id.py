# Generated by Django 4.1.4 on 2023-07-25 00:16

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("product", "0002_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cart",
            name="id",
            field=models.CharField(
                default="NOHMLUNDMyWwxmS",
                editable=False,
                max_length=15,
                primary_key=True,
                serialize=False,
                unique=True,
            ),
        ),
    ]