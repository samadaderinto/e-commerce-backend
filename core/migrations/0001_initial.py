# Generated by Django 4.1.4 on 2023-07-07 06:38

from django.conf import settings
import django.contrib.auth.validators
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import phonenumber_field.modelfields
import taggit.managers


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0013_remove_user_first_name_remove_user_last_name'),
        ('taggit', '0005_auto_20220424_2025'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(error_messages={'unique': 'A user with that username already exists.'}, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name='username')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('firstname', models.CharField(max_length=30)),
                ('lastname', models.CharField(max_length=30)),
                ('gender', models.CharField(max_length=30)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('phone1', phonenumber_field.modelfields.PhoneNumberField(max_length=128, region='US')),
                ('password', models.CharField(max_length=90)),
                ('phone2', phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, null=True, region='US')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', models.TextField()),
                ('zip', models.CharField(blank=True, max_length=10, null=True)),
                ('country', models.CharField(blank=True, max_length=30, null=True)),
                ('state', models.CharField(blank=True, max_length=30, null=True)),
                ('city', models.CharField(max_length=100)),
                ('is_default', models.BooleanField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Cart',
            fields=[
                ('id', models.CharField(default='NG_V6xLtGXnn19z', editable=False, max_length=15, primary_key=True, serialize=False, unique=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('ordered', models.BooleanField(default=False)),
                ('userId', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='CartItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)])),
                ('cartId', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.cart')),
            ],
        ),
        migrations.CreateModel(
            name='Coupon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True)),
                ('valid_from', models.DateTimeField(auto_now_add=True)),
                ('valid_to', models.DateTimeField()),
                ('discount', models.IntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('num_available', models.IntegerField(validators=[django.core.validators.MinValueValidator(0)])),
                ('num_used', models.IntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)])),
                ('active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='DeliveryInfo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('method', models.CharField(choices=[('pckup', 'pick up'), ('hmdlvry', 'home delivery')], max_length=15)),
                ('discount', models.IntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('estimate', models.IntegerField(default=0)),
                ('delivery_type', models.CharField(max_length=50)),
                ('delivery_address', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.address')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=110)),
                ('description', models.TextField(blank=True, null=True)),
                ('price', models.DecimalField(decimal_places=2, max_digits=15)),
                ('discount', models.IntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(50)])),
                ('available', models.IntegerField(validators=[django.core.validators.MinValueValidator(0)])),
                ('category', models.CharField(choices=[('FSHN', 'fishing'), ('SPRT', 'sports'), ('ELCT', 'electronics'), ('PHNS', 'phones'), ('GMES', 'games'), ('TBLT', 'tablets'), ('OUWR', 'outwear'), ('PETS', 'pets'), ('TOYS', 'toys'), ('CMPT', 'computing'), ('LNGR', 'lingerie'), ('BOOK', 'books')], max_length=4)),
                ('label', models.CharField(choices=[('NEW', 'new'), ('', 'none'), ('BTS', 'bestseller'), ('SDT', 'sold out')], default='NEW', max_length=50)),
                ('product_visibility', models.BooleanField(default=True)),
                ('image', models.ImageField(blank=True, default='', null=True, upload_to='images')),
                ('average_rating', models.DecimalField(decimal_places=2, default=0.0, max_digits=4, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(5)])),
                ('usps_delivery_date', models.IntegerField(default=0)),
                ('usps_service', models.CharField(choices=[('express', 'none'), ('priority', 'new'), ('firstclass', 'bestseller')], max_length=20)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Specifications',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weight', models.CharField(choices=[('FSHN', 'fishing'), ('SPRT', 'sports'), ('ELCT', 'electronics'), ('PHNS', 'phones'), ('GMES', 'games'), ('TBLT', 'tablets'), ('OUWR', 'outwear'), ('PETS', 'pets'), ('TOYS', 'toys'), ('CMPT', 'computing'), ('LNGR', 'lingerie'), ('BOOK', 'books')], max_length=4)),
                ('height', models.DecimalField(decimal_places=2, max_digits=4)),
                ('width', models.DecimalField(decimal_places=2, max_digits=4)),
                ('depth', models.DecimalField(decimal_places=2, max_digits=4)),
                ('average_rating', models.DecimalField(decimal_places=2, default=0.0, max_digits=4, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(5)])),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Store',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=30, unique=True)),
                ('name', models.CharField(default='official store', max_length=70)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Wishlist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('liked', models.BooleanField(default=False)),
                ('productId', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.product')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='StoreInfo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('about', models.TextField()),
                ('phone', models.CharField(max_length=30)),
                ('site', models.URLField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('storeId', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.store')),
            ],
        ),
        migrations.CreateModel(
            name='StoreImg',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.ImageField(blank=True, default='', null=True, upload_to='images')),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.store')),
            ],
        ),
        migrations.CreateModel(
            name='StoreAddress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', models.TextField()),
                ('zip', models.CharField(blank=True, max_length=10, null=True)),
                ('country', models.CharField(blank=True, max_length=30, null=True)),
                ('state', models.CharField(blank=True, max_length=30, null=True)),
                ('city', models.CharField(max_length=100)),
                ('is_default', models.BooleanField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.store')),
            ],
        ),
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('make_visible_at', models.DateTimeField()),
                ('productId', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.product')),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.store')),
            ],
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=40)),
                ('comment', models.TextField(max_length=60)),
                ('rating', models.IntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(5)])),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('productId', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.product')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Refund',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField()),
                ('accepted', models.BooleanField(default=False)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.cartitem')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Recent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('viewed', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('productId', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.product')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ProductImg',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(blank=True, default='', null=True, upload_to='images')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='app.product')),
            ],
        ),
        migrations.AddField(
            model_name='product',
            name='store',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.store'),
        ),
        migrations.AddField(
            model_name='product',
            name='tags',
            field=taggit.managers.TaggableManager(help_text='A comma-separated list of tags.', through='taggit.TaggedItem', to='taggit.Tag', verbose_name='Tags'),
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_charge_id', models.CharField(max_length=50)),
                ('amount', models.FloatField()),
                ('status', models.CharField(choices=[('pnd', 'pending'), ('sfl', 'successful'), ('fld', 'failed')], default='PND', max_length=50)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('orderId', models.CharField(default='0000000000', max_length=15)),
                ('coupon_used', models.CharField(max_length=50)),
                ('tax', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('status', models.CharField(choices=[('CND', 'cancelled'), ('RFD', 'refunded'), ('DLV', 'delivered'), ('SHP', 'shipped'), ('PKU', 'picked up'), ('PND', 'pending'), ('CFD', 'confirmed')], max_length=3)),
                ('total', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('subtotal', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('ordered_date', models.DateTimeField(auto_now=True)),
                ('payment_type', models.CharField(default='card', max_length=30)),
                ('cartId', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.cart')),
                ('delivery', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.deliveryinfo')),
            ],
        ),
        migrations.CreateModel(
            name='DeliveryEstimates',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('usps_service', models.CharField(choices=[('express', 'none'), ('priority', 'new'), ('firstclass', 'bestseller')], max_length=20)),
                ('usps_delivery_date', models.IntegerField(default=0)),
                ('pick_up', models.IntegerField(default=25)),
                ('standard_delivery', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('express_delivery', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('destination_zip', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.address')),
                ('origin_zip', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.storeaddress')),
            ],
        ),
        migrations.AddField(
            model_name='cartitem',
            name='productId',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.product'),
        ),
        migrations.CreateModel(
            name='Affiliate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=70)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]