from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0055_identity_request_settings')]

    operations = [
        migrations.AddField(
            model_name='creditpurchase',
            name='resume_preview',
            field=models.ForeignKey(to='core.preview', on_delete=models.SET_NULL, null=True, blank=True,
                                    editable=False, related_name='+'),
        ),
        migrations.AddField(
            model_name='creditpurchase',
            name='resume_reference_digest',
            field=models.CharField(max_length=64, default='', db_default='', blank=True, editable=False),
        ),
    ]
