# Generated by Django 4.1.4 on 2023-07-25 00:16

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="gender",
            field=models.CharField(
                choices=[("male", "male"), ("male", "female")], max_length=7
            ),
        ),
    ]
