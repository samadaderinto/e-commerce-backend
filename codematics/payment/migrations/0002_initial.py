# Generated by Django 4.1.4 on 2023-07-24 23:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("product", "0001_initial"),
        ("payment", "0001_initial"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="cartId",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="product.cart"
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="core.deliveryinfo"
            ),
        ),
    ]