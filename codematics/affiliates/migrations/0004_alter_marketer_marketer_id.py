# Generated by Django 4.1.4 on 2023-08-01 15:30

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("affiliates", "0003_alter_marketer_marketer_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="marketer",
            name="marketer_id",
            field=models.CharField(
                default="oRGM5UFWIe9aWMi", editable=False, max_length=70, unique=True
            ),
        ),
    ]