# Generated by Django 4.1.4 on 2023-08-04 22:59

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("store", "0002_alter_store_username"),
    ]

    operations = [
        migrations.AlterField(
            model_name="store",
            name="username",
            field=models.CharField(
                default="vnSU_1acFRbFiRh", max_length=17, unique=True
            ),
        ),
    ]
