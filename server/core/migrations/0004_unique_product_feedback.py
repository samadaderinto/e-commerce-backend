from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0003_remove_legacy_verification')]

    operations = [
        migrations.AddConstraint(
            model_name='review',
            constraint=models.UniqueConstraint(
                fields=('user', 'product'), name='unique_user_product_review'
            ),
        ),
        migrations.AddConstraint(
            model_name='wishlist',
            constraint=models.UniqueConstraint(
                fields=('user', 'product'), name='unique_user_product_wishlist'
            ),
        ),
    ]
