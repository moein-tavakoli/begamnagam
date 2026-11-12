"""Formats and generation for private recipient links."""
import re
import secrets
import string


_ALPHABET = string.ascii_letters + string.digits

# Require a digit so root codes do not match named paths such as /invite.
_CONTAINS_DIGIT = r'(?=[A-Za-z0-9]{0,4}[0-9])'
_SUFFIX = _CONTAINS_DIGIT + r'[A-Za-z0-9]{5}'
_LEGACY_STOP = _CONTAINS_DIGIT + r'[A-Z0-4][A-Za-z0-9]{4}'
_LEGACY_REPLY = _CONTAINS_DIGIT + r'[a-z5-9][A-Za-z0-9]{4}'
SHORT_CODE_PATTERN = rf'(?:[rc]{_SUFFIX}|{_SUFFIX})'
SHORT_STOP_PATTERN = rf'(?:c{_SUFFIX}|{_LEGACY_STOP})'
SHORT_REPLY_PATTERN = rf'(?:r{_SUFFIX}|{_LEGACY_REPLY})'
INVITE_CODE_PATTERN = rf'i{_SUFFIX}'
STOP_TOKEN_PATTERN = rf'(?:{SHORT_STOP_PATTERN}|[A-Za-z0-9]{{8}}|[A-Za-z0-9_-]{{43}})'
REPLY_TOKEN_PATTERN = rf'(?:{SHORT_REPLY_PATTERN}|[A-Za-z0-9]{{8}})'

# These examples have valid syntax but are never issued to recipients.
SAMPLE_STOP_CODE = 'c56Yc2'
SAMPLE_REPLY_CODE = 'r56Yc2'
SAMPLE_INVITE_CODE = 'i56Yc2'


def is_short_code(token):
    return isinstance(token, str) and re.fullmatch(SHORT_CODE_PATTERN, token) is not None


def generate_short_code(prefix):
    if prefix not in {'c', 'r', 'i'}:
        raise ValueError('Unknown SMS link prefix')
    while True:
        suffix = ''.join(secrets.choice(_ALPHABET) for _ in range(5))
        code = prefix + suffix
        if re.fullmatch(_SUFFIX, suffix) and code not in {SAMPLE_STOP_CODE, SAMPLE_REPLY_CODE, SAMPLE_INVITE_CODE}:
            return code
