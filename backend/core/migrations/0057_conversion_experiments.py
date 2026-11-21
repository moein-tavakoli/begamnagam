import django.db.models.deletion
from django.db import migrations, models


def seed_price_offer(apps, schema_editor):
    apps.get_model('core', 'MessagePackage').objects.using(schema_editor.connection.alias).create(
        name='بستهٔ ۸ پیامی', message_count=8, price_toman=25000,
        active=False, sort_order=9, price_experiment_only=True)


def retire_price_offer(apps, schema_editor):
    packages = apps.get_model('core', 'MessagePackage').objects.using(schema_editor.connection.alias)
    packages.filter(price_experiment_only=True).update(active=False)


class Migration(migrations.Migration):
    dependencies = [('core', '0056_creditpurchase_resume_preview')]
    operations = [
        migrations.AddField(model_name='messagepackage', name='price_experiment_only',
            field=models.BooleanField(db_default=False, default=False, editable=False)),
        migrations.AddConstraint(model_name='messagepackage', constraint=models.CheckConstraint(
            condition=models.Q(price_experiment_only=False) | models.Q(active=False, message_count=8, price_toman=25000), name='private_price_trial_offer')),
        migrations.CreateModel(name='ConversionExposure', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('experiment', models.CharField(max_length=12)),
            ('variant', models.CharField(max_length=10)),
            ('environment', models.CharField(max_length=8)),
            ('surface', models.CharField(max_length=12)),
            ('preview_id', models.UUIDField(editable=False, null=True)),
            ('exposed_at', models.DateTimeField(auto_now_add=True)),
            ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.account')),
        ], options={
            'default_permissions': (),
            'indexes': [models.Index(fields=['experiment', 'environment', 'exposed_at'], name='conversion_exposure_cohort')],
            'constraints': [models.UniqueConstraint(fields=('account', 'environment'), name='one_conversion_trial_per_account')],
        }),
        migrations.RunPython(seed_price_offer, retire_price_offer),
    ]
