import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_socialaccount'),
    ]

    operations = [
        migrations.CreateModel(
            name='StripePayoutDestination',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=120)),
                ('account_id_encrypted', models.TextField()),
                ('account_id_last4', models.CharField(max_length=4)),
                ('is_default', models.BooleanField(default=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stripe_payout_destinations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(condition=models.Q(('is_default', True)), fields=('user',), name='one_default_stripe_destination_per_user')],
            },
        ),
    ]
