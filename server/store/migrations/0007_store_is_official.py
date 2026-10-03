from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0006_storepayout'),
    ]

    operations = [
        migrations.AddField(
            model_name='store',
            name='is_official',
            field=models.BooleanField(default=False),
        ),
    ]
