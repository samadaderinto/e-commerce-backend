# Generated by Django 4.1.4 on 2023-10-08 10:25

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cart', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Coupon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True)),
                ('valid_from', models.DateTimeField(auto_now_add=True)),
                ('valid_to', models.DateTimeField()),
                ('discount', models.IntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(60)])),
                ('num_available', models.IntegerField(validators=[django.core.validators.MinValueValidator(0)])),
                ('num_used', models.IntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)])),
                ('active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_charge_id', models.CharField(max_length=50)),
                ('amount', models.FloatField()),
                ('status', models.CharField(choices=[('pending', 'pending'), ('successful', 'successful'), ('failed', 'failed')], default='PND', max_length=50)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('orderId', models.CharField(default='o7tBdjLyKO8Tq', editable=False, max_length=15, unique=True)),
                ('coupon_used', models.CharField(max_length=50)),
                ('tax', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('status', models.CharField(choices=[('pending', 'pending'), ('cancelled', 'cancelled'), ('refunded', 'refunded'), ('delivered', 'delivered'), ('shipped', 'shipped'), ('picked up', 'picked up'), ('confirmed', 'confirmed')], max_length=15)),
                ('ordered', models.BooleanField(default=False)),
                ('payment_type', models.CharField(default='card', max_length=30)),
                ('ordered_date', models.DateTimeField(auto_now=True)),
                ('total', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('subtotal', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('cartId', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cart.cart')),
                ('delivery', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.deliveryinfo')),
            ],
        ),
    ]
