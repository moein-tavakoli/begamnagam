"""Shared OpenAPI contracts and validation for the v2 HTTP boundary."""
import re
import uuid
from functools import wraps

from django.http import JsonResponse

from core.input_digits import ascii_digits
from core.services import APIError, api, error_response, is_product_authenticated, limited
from core.views import body


def ref(name):
    return {'$ref': '#/components/schemas/' + name}


def obj(properties, required=None, *, closed=False):
    result = {'type': 'object', 'properties': properties}
    if required is None:
        required = properties.keys()
    if required:
        result['required'] = list(required)
    if closed:
        result['additionalProperties'] = False
    return result


def array(items):
    return {'type': 'array', 'items': items}


def string(**kwargs):
    return {'type': 'string', **kwargs}


def integer(**kwargs):
    return {'type': 'integer', **kwargs}


BOOL = {'type': 'boolean'}
UUID = string(format='uuid')
DATE = string(format='date-time')
NULL_DATE = {**DATE, 'nullable': True}
NULL_STRING = string(nullable=True)
PHONE = string(minLength=11, maxLength=32, description='Iran mobile; Persian/Arabic digits and +98 are accepted.', example='09123456789')
TONE = string(enum=['polite', 'firm', 'angry'])
TEXT = string(minLength=1, maxLength=280)
TOKEN = string(minLength=1, maxLength=4096, description='Opaque capability. Preserve exactly; never put in a URL or log.')
CONSENT = {'type': 'boolean', 'enum': [True]}
EMPTY = obj({}, closed=True)
STATUS = string(enum=['awaiting_payment', 'queued', 'accepted', 'delivered', 'delivered_demo', 'unknown', 'cancelled', 'failed'])

SCHEMAS = {
    'Error': obj({'error': obj({
        'code': string(), 'message': string(), 'fields': {'type': 'object'},
        'request_id': string(), 'details': obj({'alternatives': array(ref('Alternative'))}),
    }, ['code', 'message'])}, ['error']),
    'Alternative': obj({'id': string(), 'label': string(), 'text': string(), 'token': TOKEN,
                        'message_tone': TONE, 'expires_at': DATE}),
    'Session': obj({'authenticated': BOOL, 'csrf_token': string(), 'recent_auth': BOOL,
                    'expires_in': integer(), 'otp_length': integer(), 'demo_mode': BOOL,
                    'otp_is_real': BOOL}, ['authenticated', 'csrf_token', 'recent_auth', 'expires_in', 'otp_length', 'demo_mode', 'otp_is_real']),
    'Me': obj({'id': string(), 'phone_masked': string(), 'suspended': BOOL,
               'deletion_requested_at': NULL_DATE, 'recent_auth': BOOL},
              ['id', 'phone_masked', 'suspended', 'deletion_requested_at', 'recent_auth']),
    'Credits': obj({'gift_remaining': integer(minimum=0), 'gift_total': integer(minimum=0),
                    'invitation_rewards_total': integer(minimum=0), 'purchased_remaining': integer(minimum=0),
                    'total_remaining': integer(minimum=0), 'wallet_balance_toman': string(pattern='^[0-9]+$'),
                    'environment': string(enum=['demo', 'live'])},
                   ['gift_remaining', 'gift_total', 'invitation_rewards_total', 'purchased_remaining', 'total_remaining', 'wallet_balance_toman', 'environment']),
    'Category': obj({'id': integer(), 'label': string()}, ['id', 'label']),
    'Example': obj({'id': integer(), 'category_id': integer(), 'topic': string(), 'label': string(),
                    'description': string(), 'text': TEXT}, ['id', 'category_id', 'topic', 'label', 'description', 'text']),
    'Tone': obj({'id': TONE, 'label': string(), 'description': string()}, ['id', 'label', 'description']),
    'Package': obj({'id': integer(), 'name': string(), 'message_count': integer(), 'price_toman': integer(),
                    'active': BOOL, 'sort_order': integer(), 'revision': integer()},
                   ['id', 'name', 'message_count', 'price_toman', 'active', 'sort_order', 'revision']),
    'Channel': obj({'name': string(), 'label': string(), 'url': string()}, ['name', 'label', 'url']),
    'PaymentOptions': obj({'wallet_enabled': BOOL, 'card_enabled': BOOL, 'gateway_enabled': BOOL,
                           'gateway_configured': BOOL, 'wallet_terms_version': string(),
                           'receipt_channels': array(ref('Channel'))}),
    'InvitationPolicy': obj({'consent_version': string(), 'max_sends': integer(nullable=True),
                             'cooldown_hours': integer(), 'validity_days': integer(nullable=True),
                             'window_hours': integer(), 'window_limit': integer(nullable=True)}),
    'Catalog': obj({'categories': array(ref('Category')), 'examples': array(ref('Example')),
                    'message_tones': array(ref('Tone')), 'default_message_tone': TONE,
                    'rewrite_mode': string(enum=['template', 'ollama', 'gapgpt']), 'freeform_enabled': BOOL,
                    'message_packages': array(ref('Package')), 'package_checkout_enabled': BOOL,
                    'payment_options': ref('PaymentOptions'), 'terms_version': string(),
                    'invitation_policy': ref('InvitationPolicy'), 'support_contact': string()}),
    'Bootstrap': obj({'session': ref('Session'), 'me': {**ref('Me')}, 'credits': {**ref('Credits')},
                      'catalog': ref('Catalog')}, ['session', 'catalog']),
    'OTPInput': obj({'phone': PHONE}, ['phone'], closed=True),
    'OTPChallenge': obj({'challenge_id': UUID, 'expires_in': integer(), 'demo_mode': BOOL,
                         'delivery_status': string(enum=['accepted', 'unknown']),
                         'debug_code': string(description='Isolated demo tests only; never returned by the real OTP provider.')},
                        ['challenge_id', 'expires_in', 'demo_mode']),
    'LoginInput': obj({'challenge_id': UUID, 'code': string(pattern='^[0-9]{4}$', description='Keep leading zeroes; Persian/Arabic digits are canonicalized.')},
                      ['challenge_id', 'code'], closed=True),
    'RecipientValidation': obj({'valid': BOOL, 'phone': string(pattern='^09[0-9]{9}$'), 'phone_masked': string()},
                               ['valid', 'phone', 'phone_masked']),
    'SuggestionInput': obj({'recipient_phone': PHONE, 'source_mode': string(enum=['suggestion']),
                            'category': string(minLength=1, maxLength=32), 'text': TEXT, 'message_tone': TONE},
                           ['recipient_phone', 'source_mode', 'category', 'text'], closed=True),
    'FreeformInput': obj({'recipient_phone': PHONE, 'source_mode': string(enum=['freeform']), 'text': TEXT, 'message_tone': TONE},
                         ['recipient_phone', 'source_mode', 'text'], closed=True),
    'AlternativeInput': obj({'recipient_phone': PHONE, 'source_mode': string(enum=['reviewed_alternative']),
                             'alternative_token': TOKEN, 'message_tone': TONE},
                            ['recipient_phone', 'source_mode', 'alternative_token'], closed=True),
    'PreviewInput': {'oneOf': [ref('SuggestionInput'), ref('FreeformInput'), ref('AlternativeInput')]},
    'Preview': obj({'preview_id': UUID, 'payment_method': string(), 'wallet_terms_version': string(),
                    'rewritten_text': string(), 'price_toman': integer(), 'is_free': BOOL, 'message_tone': TONE,
                    'expires_at': DATE, 'moderation_mode': string(), 'terms_version': string(),
                    'full_sms': string(), 'sms_segments': integer()},
                   ['preview_id', 'full_sms', 'terms_version', 'expires_at', 'price_toman', 'is_free']),
    'MessageInput': obj({'preview_id': UUID, 'recipient_phone': PHONE, 'consent': CONSENT,
                         'terms_version': string(minLength=1, maxLength=40)},
                        ['preview_id', 'recipient_phone', 'consent', 'terms_version'], closed=True),
    'Message': obj({'id': UUID, 'status': STATUS, 'financial_status': string(), 'payment_method': string(),
                    'uses_purchased_credit': BOOL, 'status_reason': {**obj({'code': string(), 'message': string()}), 'nullable': True}, 'delivery_status': string(),
                    'amount_toman': integer(), 'payment_mode': string(), 'recipient_masked': string(),
                    'is_free': BOOL, 'text': string(), 'category': string(), 'paid_at': NULL_DATE,
                    'created_at': DATE, 'payment_expires_at': DATE},
                   ['id', 'status', 'delivery_status', 'recipient_masked', 'text', 'amount_toman', 'created_at']),
    'PreferencesInput': obj({'blocked': BOOL}, ['blocked'], closed=True),
    'Preferences': obj({'blocked': BOOL}, ['blocked']),
    'Deletion': obj({'requested': BOOL, 'redaction_within_days': integer()}, ['requested', 'redaction_within_days']),
    'PurchaseInput': obj({'package_id': integer(minimum=1), 'package_revision': integer(minimum=0),
                          'payment_method': string(enum=['wallet', 'gateway', 'card']), 'wallet_consent': CONSENT,
                          'wallet_terms_version': string(minLength=1)},
                         ['package_id', 'package_revision', 'payment_method', 'wallet_consent', 'wallet_terms_version'], closed=True),
    'Purchase': obj({'id': UUID, 'package_id': integer(), 'name': string(), 'message_count': integer(),
                     'amount_toman': integer(), 'environment': string(), 'payment_method': string(), 'status': string(),
                     'created_at': DATE, 'redirect_url': NULL_STRING, 'receipt_channels': array(ref('Channel')),
                     'manual_payment_id': UUID, 'card': obj({'number': string(), 'holder': string(), 'bank_name': string()}),
                     'receipt_submitted_at': NULL_DATE, 'review_note': string()},
                    ['id', 'status', 'amount_toman', 'message_count', 'redirect_url']),
    'ReceiptInput': obj({'receipt_sent': CONSENT, 'reference': string(maxLength=100)}, ['receipt_sent'], closed=True),
    'TopupInput': obj({'amount_toman': integer(minimum=1, maximum=2147483647), 'consent': CONSENT,
                       'terms_version': string(minLength=1)}, ['amount_toman', 'consent', 'terms_version'], closed=True),
    'Topup': obj({'id': UUID, 'amount_toman': integer(), 'status': string(), 'created_at': DATE, 'redirect_url': NULL_STRING},
                 ['id', 'amount_toman', 'status', 'created_at', 'redirect_url']),
    'Wallet': obj({'balance_toman': string(pattern='^[0-9]+$'), 'withdrawable': BOOL,
                   'wallet_enabled': BOOL, 'card_enabled': BOOL, 'gateway_enabled': BOOL, 'gateway_configured': BOOL,
                   'wallet_terms_version': string(), 'receipt_channels': array(ref('Channel'))}),
    'WalletEntry': obj({'id': UUID, 'kind': string(), 'amount_toman': integer(), 'balance_after_toman': string(),
                        'created_at': DATE, 'order_id': {**UUID, 'nullable': True}, 'purchase_id': {**UUID, 'nullable': True}}),
    'CreditEntry': obj({'id': string(), 'kind': string(), 'units': integer(),
                        'created_at': DATE, 'order_id': {**UUID, 'nullable': True}, 'purchase_id': {**UUID, 'nullable': True}}),
    'InvitationInput': obj({'phone': PHONE, 'consent': CONSENT, 'consent_version': string(minLength=1)},
                           ['phone', 'consent', 'consent_version'], closed=True),
    'ReminderInput': obj({'consent': CONSENT, 'consent_version': string(minLength=1)}, ['consent', 'consent_version'], closed=True),
    'InvitationSummary': obj({'total': integer(), 'registered': integer(), 'earned_credits': integer(),
                              'daily_remaining': integer(nullable=True)}),
    'Invitation': obj({'id': UUID, 'phone_masked': string(), 'created_at': DATE, 'registered_at': NULL_DATE,
                       'status': string(enum=['registered', 'expired', 'waiting']), 'reward_credits': integer(), 'reward_pending': BOOL,
                       'send_count': integer(), 'sends_remaining': integer(nullable=True), 'can_resend': BOOL,
                       'max_sends': integer(nullable=True), 'cooldown_hours': integer(), 'validity_days': integer(nullable=True),
                       'next_send_at': DATE, 'delivery_status': string(), 'reason': NULL_STRING,
                       'sends': array(obj({'number': integer(), 'status': string(), 'created_at': DATE}))}),
    'SupportSummary': obj({'unread_count': integer(), 'staff_online': BOOL}, ['unread_count', 'staff_online']),
    'SupportThread': obj({'id': UUID, 'status': string(), 'last_sequence': integer(), 'last_customer_sequence': integer(),
                          'answered_customer_sequence': integer(), 'staff_read_sequence': integer(),
                          'customer_read_sequence': integer(), 'needs_reply': BOOL, 'updated_at': DATE, 'closed_at': NULL_DATE}),
    'SupportMessage': obj({'id': UUID, 'sequence': integer(), 'role': string(), 'text': string(),
                           'redacted': BOOL, 'created_at': DATE, 'client_key': UUID},
                          ['id', 'sequence', 'role', 'text', 'redacted', 'created_at']),
    'SupportInput': obj({'text': string(minLength=1, maxLength=2000)}, ['text'], closed=True),
    'SupportSent': obj({'thread': ref('SupportThread'), 'message': ref('SupportMessage')}, ['thread', 'message']),
    'SupportPage': obj({'thread': {'allOf': [ref('SupportThread')], 'nullable': True}, 'messages': array(ref('SupportMessage')),
                        'has_older': BOOL, 'before_cursor': integer(nullable=True), 'staff_online': BOOL}),
    'ReadInput': obj({'through_sequence': integer(minimum=0, maximum=2147483647)}, ['through_sequence'], closed=True),
    'OK': obj({'ok': BOOL}, ['ok']),
    'CapabilityInput': obj({'token': TOKEN}, ['token'], closed=True),
    'ReportInput': obj({'token': TOKEN, 'reason': string(enum=['unwanted', 'harassment', 'wrong_number', 'other']),
                        'details': string(maxLength=500)}, ['token', 'reason'], closed=True),
    'Capability': obj({'active': BOOL, 'can_report': BOOL}, ['active', 'can_report']),
    'Report': obj({'receipt': UUID, 'blocked': BOOL}, ['receipt', 'blocked']),
    'Empty': EMPTY,
}

SCHEMAS['NullableSupportThread'] = {**SCHEMAS['SupportThread'], 'nullable': True}
SCHEMAS['SupportPage']['properties']['thread'] = ref('NullableSupportThread')
SCHEMAS['SuggestionInput']['example'] = {
    'recipient_phone': '09901234567', 'source_mode': 'suggestion', 'category': 'appreciation',
    'text': 'از مهربانی و کمکی که به من کردی ممنونم', 'message_tone': 'polite',
}


def page(name):
    return obj({'results': array(ref(name)), 'next_cursor': NULL_STRING, 'has_more': BOOL},
               ['results', 'next_cursor', 'has_more'])


for _name in ('Category', 'Example', 'Package', 'Message', 'Purchase', 'Topup', 'Invitation', 'WalletEntry', 'CreditEntry'):
    SCHEMAS[_name + 'Page'] = page(_name)

PAGE_QUERY = {'limit': integer(minimum=1, maximum=50, default=20), 'cursor': string(maxLength=2048)}


def valid(value, schema):
    """Validate only the small, explicitly supported request-schema vocabulary."""
    if '$ref' in schema:
        return valid(value, SCHEMAS[schema['$ref'].rsplit('/', 1)[-1]])
    if 'oneOf' in schema:
        return sum(valid(value, choice) for choice in schema['oneOf']) == 1
    expected = {'object': dict, 'string': str, 'integer': int, 'boolean': bool}[schema['type']]
    if type(value) is not expected:
        return False
    if 'enum' in schema and value not in schema['enum']:
        return False
    if expected is dict:
        properties = schema.get('properties', {})
        return (all(key in value for key in schema.get('required', []))
                and (schema.get('additionalProperties') is not False or not set(value) - properties.keys())
                and all(valid(item, properties[key]) for key, item in value.items() if key in properties))
    if expected is str:
        if not schema.get('minLength', 0) <= len(value) <= schema.get('maxLength', 8192):
            return False
        if 'pattern' in schema and re.fullmatch(schema['pattern'], value) is None:
            return False
        if schema.get('format') == 'uuid':
            try:
                uuid.UUID(value)
            except (ValueError, AttributeError):
                return False
    if expected is int and not schema.get('minimum', -2**63) <= value <= schema.get('maximum', 2**63-1):
        return False
    return True


def operation(identifier, tag, summary, response, *, request=None, auth=True, key=False, status=200, query=None, description=''):
    return dict(identifier=identifier, tag=tag, summary=summary, response=response, request=request,
                auth=auth, key=key, status=status, query=query or {}, description=description)


def resource(**operations):
    def decorate(view):
        @wraps(view)
        def dispatch(request, *args, **kwargs):
            method = request.method.lower()
            if method not in operations:
                response = error_response(APIError('method_not_allowed', 'روش درخواست مجاز نیست.', 405))
                response['Allow'] = ', '.join(key.upper() for key in operations)
                return response
            spec = operations[method]
            if spec['auth'] and (not is_product_authenticated(request.user) or not request.user.is_active):
                raise APIError('authentication_required', 'ابتدا شمارهٔ خودت را تأیید کن.', 401)
            if spec['auth']:
                limited('api-v2-account', str(request.user.pk), 300, 60)
            if set(request.GET) - spec['query'].keys() or any(len(request.GET.getlist(key)) != 1 for key in request.GET):
                raise APIError('invalid_query', 'پارامترهای درخواست معتبر نیستند.', 422)
            request.api_query = {}
            for key, schema in spec['query'].items():
                if key not in request.GET:
                    continue
                value = request.GET[key]
                if schema['type'] == 'integer':
                    value = ascii_digits(value)
                    if not re.fullmatch('[0-9]{1,10}', value):
                        raise APIError('invalid_query', 'پارامترهای درخواست معتبر نیستند.', 422)
                    value = int(value)
                if not valid(value, schema):
                    raise APIError('invalid_query', 'پارامترهای درخواست معتبر نیستند.', 422)
                request.api_query[key] = value
            if spec['request']:
                request.api_data = body(request)
                if not valid(request.api_data, ref(spec['request'])):
                    raise APIError('invalid_input', 'فیلدها و نوع مقادیر درخواست را بررسی کن.', 422)
            if spec['key']:
                try:
                    request.api_key = uuid.UUID(request.headers.get('Idempotency-Key', ''))
                except (ValueError, AttributeError):
                    raise APIError('idempotency_key_required', 'کلید یکتای UUID برای این اقدام لازم است.', 422) from None
            result = view(request, *args, **kwargs)
            if isinstance(result, dict):
                return JsonResponse(result, status=spec['status'], json_dumps_params={'ensure_ascii': False})
            return result
        wrapped = api(['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'])(dispatch)
        wrapped.api_operations = operations
        return wrapped
    return decorate
