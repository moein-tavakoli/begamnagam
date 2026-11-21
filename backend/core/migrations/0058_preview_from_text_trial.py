from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0057_conversion_experiments')]
    operations = [
        migrations.AddField(model_name='preview', name='from_text_trial',
            field=models.BooleanField(db_default=False, default=False, editable=False)),
    ]
