from django.db import migrations
from django.utils import timezone


def enable_requested_tones(apps, schema_editor):
    database = schema_editor.connection.alias
    Configuration = apps.get_model('core', 'AIConfiguration')
    Audit = apps.get_model('core', 'OperatorAudit')
    fields = ('tone_polite_enabled', 'tone_firm_enabled', 'tone_blunt_enabled')
    for config in Configuration.objects.using(database).all():
        before = {name: getattr(config, name) for name in fields}
        before['revision'] = config.revision
        after = {name: True for name in fields}
        after.update(revision=config.revision + 1, updated_at=timezone.now())
        Configuration.objects.using(database).filter(pk=config.pk).update(**after)
        Audit.objects.using(database).create(
            action='enable_requested_tones', object_id='ai:1',
            reason='User requested polite, firm and blunt choices with firm default; release 0.21.0',
            before=before, after={**{name: True for name in fields}, 'revision': config.revision + 1})


class Migration(migrations.Migration):
    dependencies = [('core', '0039_blunt_message_tone')]
    operations = [migrations.RunPython(enable_requested_tones, migrations.RunPython.noop)]
