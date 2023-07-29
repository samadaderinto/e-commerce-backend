# Generated by Django 4.1.4 on 2023-07-29 08:18

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import taggit.managers


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("taggit", "0005_auto_20220424_2025"),
        ("product", "0001_initial"),
        ("store", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="store",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="store.store"
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="tags",
            field=taggit.managers.TaggableManager(
                help_text="A comma-separated list of tags.",
                through="taggit.TaggedItem",
                to="taggit.Tag",
                verbose_name="Tags",
            ),
        ),
        migrations.AddField(
            model_name="cartitem",
            name="cartId",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="product.cart"
            ),
        ),
        migrations.AddField(
            model_name="cartitem",
            name="productId",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="product.product"
            ),
        ),
        migrations.AddField(
            model_name="cart",
            name="userId",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
