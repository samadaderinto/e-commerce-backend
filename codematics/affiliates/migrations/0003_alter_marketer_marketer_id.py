# Generated by Django 4.1.4 on 2023-07-25 13:19

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("affiliates", "0002_rename_affiliate_marketer"),
    ]

    operations = [
        migrations.AlterField(
            model_name="marketer",
            name="marketer_id",
            field=models.CharField(
                default="ab269106a29e", editable=False, max_length=70, unique=True
            ),
        ),
    ]