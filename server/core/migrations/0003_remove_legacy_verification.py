from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('core', '0002_initial')]

    operations = [
        migrations.RemoveField(model_name='user', name='is_verified'),
        migrations.AlterModelOptions(name='review', options={'ordering': ['-created']}),
    ]
