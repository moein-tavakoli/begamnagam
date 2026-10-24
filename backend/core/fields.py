from django.db import models
from .privacy import encrypt, decrypt


class EncryptedTextField(models.TextField):
    """Transparent encryption for capability-bearing snapshots and report details.

    Reads legacy clear text only for the forward migration. ORM writes always use
    the active key; filters must never compare ciphertext by equality.
    """
    def from_db_value(self, value, expression, connection):
        if value and value.startswith('enc:v1:'):
            return decrypt(value[7:])
        return value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return 'enc:v1:' + encrypt(value) if value else value
