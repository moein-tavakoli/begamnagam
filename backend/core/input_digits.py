"""Canonicalize newly entered digits before validation, hashing and storage."""
import re
from unicodedata import decimal


OPAQUE_FIELDS = frozenset({
    'id', 'username', 'password', 'password1', 'password2', 'old_password',
    'new_password1', 'new_password2', 'csrfmiddlewaretoken', 'token', 'signature',
    'authority', 'status', 'category', 'message_tone', 'source_mode', 'source',
})
OPAQUE_SUFFIXES = ('_id', '_token', '_signature', '_key', '_hash', '_digest', '_cipher', '_version')

# JSON fields whose existing contract is an integer. Numeric foreign keys are
# explicit here so UUIDs, provider identifiers and codes keep their own format.
JSON_INTEGER_FIELDS = frozenset({
    'account_id', 'group_id', 'package_id', 'role_id', 'package_revision', 'revision', 'expected_revision',
    'amount_toman', 'price_toman', 'message_count', 'sort_order', 'page', 'page_size', 'limit',
    'through_sequence', 'last_sequence', 'reply_to_sequence', 'maximum', 'window_seconds',
    'sender_daily_limit', 'rewrite_daily_limit', 'timeout_seconds', 'parallel_requests',
    'daily_limit', 'user_daily_limit', 'sender_limit', 'sender_window_hours', 'recipient_limit',
    'recipient_window_hours', 'recipient_cooldown_hours', 'pair_cooldown_hours',
    'sending_start_hour', 'sending_end_hour', 'invitation_max_sends', 'invitation_limit',
    'invitation_window_hours', 'invitation_cooldown_hours', 'invitation_validity_days',
    'otp_validity_seconds', 'otp_max_attempts', 'preview_validity_seconds',
    'provider_daily_budget_rial', 'otp_max_cost_rial', 'sms_max_cost_rial', 'rewrite_user_limit',
})


def opaque_field(name):
    name = name.lower()
    return name in OPAQUE_FIELDS or name.endswith(OPAQUE_SUFFIXES)


def ascii_digits(value):
    if value.isascii():
        return value
    return ''.join(str(number) if (number := decimal(char, None)) is not None else char for char in value)


def canonical_input(value, field='', depth=0, *, json_numbers=False):
    if depth > 32:
        raise ValueError('input_nesting_too_deep')
    if json_numbers and field in JSON_INTEGER_FIELDS and isinstance(value, str) and not value.isascii():
        normalized = ascii_digits(value)
        number = normalized.strip()
        if normalized != value and re.fullmatch(r'-?[0-9]{1,19}', number):
            return int(number)
    # Opaque credentials and capabilities must retain their exact bytes.
    if opaque_field(field):
        return value
    if isinstance(value, str):
        return ascii_digits(value)
    if isinstance(value, list):
        return [canonical_input(item, depth=depth + 1, json_numbers=json_numbers) for item in value]
    if isinstance(value, dict):
        return {key: canonical_input(item, key, depth + 1, json_numbers=json_numbers) for key, item in value.items()}
    return value
