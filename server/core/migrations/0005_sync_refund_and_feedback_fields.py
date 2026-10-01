from django.db import migrations, models


def copy_refund_emails(apps, schema_editor):
    Refund = apps.get_model('core', 'Refund')
    for refund in Refund.objects.select_related('userId').all().iterator():
        if refund.userId_id:
            refund.email = refund.userId.email
            refund.save(update_fields=['email'])


class Migration(migrations.Migration):
    dependencies = [('core', '0004_unique_product_feedback')]

    operations = [
        migrations.RemoveField(model_name='recent', name='viewed'),
        migrations.AddField(
            model_name='refund', name='email',
            field=models.EmailField(default='', max_length=254),
            preserve_default=False,
        ),
        migrations.RunPython(copy_refund_emails, migrations.RunPython.noop),
        migrations.RemoveField(model_name='refund', name='userId'),
        migrations.AlterField(
            model_name='review', name='label',
            field=models.CharField(max_length=80),
        ),
    ]
