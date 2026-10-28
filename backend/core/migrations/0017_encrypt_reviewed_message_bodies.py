import core.fields
from django.db import migrations


def encrypt_bodies(apps, schema_editor):
    for name in ("Preview", "Order"):
        model = apps.get_model("core", name)
        rows = model.objects.using(schema_editor.connection.alias)
        for row in rows.exclude(text="").only("pk", "text").iterator(chunk_size=200):
            # Legacy plaintext is readable, but every write uses authenticated
            # encryption. Reviewed content/signatures and recipient links stay exact.
            rows.filter(pk=row.pk).update(text=row.text)


def decrypt_bodies(apps, schema_editor):
    # Restore the original storage format on an intentional schema rollback.
    # Parameterized SQL bypasses the encrypted field's write conversion only here.
    quote = schema_editor.quote_name
    for name in ("Preview", "Order"):
        model = apps.get_model("core", name)
        rows = model.objects.using(schema_editor.connection.alias)
        statement = f"UPDATE {quote(model._meta.db_table)} SET {quote('text')} = %s WHERE {quote(model._meta.pk.column)} = %s"
        with schema_editor.connection.cursor() as cursor:
            for row in rows.exclude(text="").only("pk", "text").iterator(chunk_size=200):
                cursor.execute(statement, [row.text, model._meta.pk.get_db_prep_value(row.pk, schema_editor.connection)])


class Migration(migrations.Migration):
    dependencies = [("core", "0016_runtime_site_limits")]
    operations = [
        migrations.AlterField(model_name="preview", name="text", field=core.fields.EncryptedTextField()),
        migrations.AlterField(model_name="order", name="text", field=core.fields.EncryptedTextField()),
        migrations.RunPython(encrypt_bodies, decrypt_bodies),
    ]
