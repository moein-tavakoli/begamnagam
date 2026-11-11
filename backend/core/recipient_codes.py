"""Formats and generation for private recipient links."""
import re
import secrets
import string


_ALPHABET = string.ascii_letters + string.digits
_STOP_START = string.ascii_uppercase + '01234'
_REPLY_START = string.ascii_lowercase + '56789'

# A digit distinguishes a root-path code from a named site page.
_CONTAINS_DIGIT = r'(?=[A-Za-z0-9]{0,4}[0-9])'
SHORT_CODE_PATTERN = _CONTAINS_DIGIT + r'[A-Za-z0-9]{5}'
SHORT_STOP_PATTERN = _CONTAINS_DIGIT + r'[A-Z0-4][A-Za-z0-9]{4}'
SHORT_REPLY_PATTERN = _CONTAINS_DIGIT + r'[a-z5-9][A-Za-z0-9]{4}'
STOP_TOKEN_PATTERN = rf'(?:{SHORT_STOP_PATTERN}|[A-Za-z0-9]{{8}}|[A-Za-z0-9_-]{{43}})'
REPLY_TOKEN_PATTERN = rf'(?:{SHORT_REPLY_PATTERN}|[A-Za-z0-9]{{8}})'

# These examples have valid syntax but are never issued to recipients.
SAMPLE_STOP_CODE = 'S0TOP'
SAMPLE_REPLY_CODE = 'r3PLY'


def is_short_code(token):
    return isinstance(token, str) and re.fullmatch(SHORT_CODE_PATTERN, token) is not None


def generate_short_code(*, reply=False):
    first = _REPLY_START if reply else _STOP_START
    while True:
        code = secrets.choice(first) + ''.join(secrets.choice(_ALPHABET) for _ in range(4))
        if is_short_code(code) and code not in {SAMPLE_STOP_CODE, SAMPLE_REPLY_CODE}:
            return code
