# Generated by Django 4.1.4 on 2023-07-29 08:18

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Coupon",
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
                ("code", models.CharField(max_length=50, unique=True)),
                ("valid_from", models.DateTimeField(auto_now_add=True)),
                ("valid_to", models.DateTimeField()),
                (
                    "discount",
                    models.IntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ]
                    ),
                ),
                (
                    "num_available",
                    models.IntegerField(
                        validators=[django.core.validators.MinValueValidator(0)]
                    ),
                ),
                (
                    "num_used",
                    models.IntegerField(
                        default=0,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="Order",
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
                ("orderId", models.CharField(default="0000000000", max_length=15)),
                ("coupon_used", models.CharField(max_length=50)),
                (
                    "tax",
                    models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("CND", "cancelled"),
                            ("RFD", "refunded"),
                            ("DLV", "delivered"),
                            ("SHP", "shipped"),
                            ("PKU", "picked up"),
                            ("PND", "pending"),
                            ("CFD", "confirmed"),
                        ],
                        max_length=3,
                    ),
                ),
                (
                    "total",
                    models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
                ),
                (
                    "subtotal",
                    models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
                ),
                ("ordered_date", models.DateTimeField(auto_now=True)),
                ("ordered", models.BooleanField(verbose_name=False)),
                ("payment_type", models.CharField(default="card", max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name="Payment",
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
                ("stripe_charge_id", models.CharField(max_length=50)),
                ("amount", models.FloatField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pnd", "pending"),
                            ("sfl", "successful"),
                            ("fld", "failed"),
                        ],
                        default="PND",
                        max_length=50,
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
