# Generated by Django 4.1.4 on 2023-08-01 01:32

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("store", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="store",
            name="username",
            field=models.CharField(
                default="2vY17JF3d2y-Jdc", max_length=17, unique=True
            ),
        ),
    ]