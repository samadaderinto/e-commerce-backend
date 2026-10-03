from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0008_alter_storepayout_store_merchantwallet_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='storeinfo',
            name='avatar_url',
            field=models.URLField(blank=True, max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='storeinfo',
            name='banner_url',
            field=models.URLField(blank=True, max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='storeinfo',
            name='website',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='storeinfo',
            name='bio',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='storeinfo',
            name='instagram',
            field=models.URLField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='storeinfo',
            name='twitter',
            field=models.URLField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='storeinfo',
            name='facebook',
            field=models.URLField(blank=True, default=''),
        ),
    ]
