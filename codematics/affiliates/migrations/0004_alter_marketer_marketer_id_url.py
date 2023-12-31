# Generated by Django 4.1.4 on 2023-07-25 20:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("product", "0008_alter_cart_id"),
        ("affiliates", "0003_alter_marketer_marketer_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="marketer",
            name="marketer_id",
            field=models.CharField(
                default="adfe2262c81b", editable=False, max_length=70, unique=True
            ),
        ),
        migrations.CreateModel(
            name="Url",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("identifier", models.CharField(max_length=120)),
                ("abs_url", models.URLField()),
                ("active", models.BooleanField(default=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "marketer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="affiliates.marketer",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="product.product",
                    ),
                ),
            ],
        ),
    ]
