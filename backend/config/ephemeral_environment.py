"""Environment-only keys for isolated tests and static asset collection.

Application startup never calls this helper. No generated value is persisted.
"""
import base64
import os
import secrets


def prepare_ephemeral_secrets():
    os.environ.setdefault("DJANGO_SECRET_KEY", secrets.token_urlsafe(48))
    os.environ.setdefault("PHONE_HASH_KEY", secrets.token_urlsafe(48))
    os.environ.setdefault("PHONE_ENCRYPTION_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode())
