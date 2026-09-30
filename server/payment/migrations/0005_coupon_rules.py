from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [('payment', '0004_order_snapshots'), ('product', '0004_catalog_presentation')]
    operations = [
        migrations.AddField(model_name='coupon', name='type', field=models.CharField(choices=[('order_total', 'Order total'), ('product', 'Product'), ('product_quantity', 'Product quantity'), ('category', 'Category')], default='order_total', max_length=30)),
        migrations.AddField(model_name='coupon', name='product', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='coupons', to='product.product')),
        migrations.AddField(model_name='coupon', name='category', field=models.CharField(blank=True, default='', max_length=100)),
        migrations.AddField(model_name='coupon', name='minimum_quantity', field=models.PositiveIntegerField(default=1)),
        migrations.AlterField(model_name='coupon', name='discount', field=models.IntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)])),
        migrations.CreateModel(name='CouponRedemption', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('created', models.DateTimeField(auto_now_add=True)), ('updated', models.DateTimeField(auto_now=True)),
            ('order', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='coupon_redemption', to='payment.order')),
            ('coupon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='redemptions', to='payment.coupon')),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupon_redemptions', to='core.user')),
        ], options={'constraints': [models.UniqueConstraint(fields=('coupon', 'user'), name='unique_coupon_redemption_per_user')]}),
    ]
