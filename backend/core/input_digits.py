"""Canonicalize newly entered digits before validation, hashing and storage."""
from unicodedata import decimal


OPAQUE_FIELDS = frozenset({
    'id', 'username', 'password', 'password1', 'password2', 'old_password',
    'new_password1', 'new_password2', 'csrfmiddlewaretoken', 'token', 'signature',
    'authority', 'status', 'category', 'message_tone', 'source_mode', 'source',
})
OPAQUE_SUFFIXES = ('_id', '_token', '_signature', '_key', '_hash', '_digest', '_cipher', '_version')


def opaque_field(name):
    name = name.lower()
    return name in OPAQUE_FIELDS or name.endswith(OPAQUE_SUFFIXES)


def ascii_digits(value):
    if value.isascii():
        return value
    return ''.join(str(number) if (number := decimal(char, None)) is not None else char for char in value)


def canonical_input(value, field='', depth=0):
    if depth > 32:
        raise ValueError('input_nesting_too_deep')
    # Opaque credentials and capabilities must retain their exact bytes.
    if opaque_field(field):
        return value
    if isinstance(value, str):
        return ascii_digits(value)
    if isinstance(value, list):
        return [canonical_input(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        return {key: canonical_input(item, key, depth + 1) for key, item in value.items()}
    return value
