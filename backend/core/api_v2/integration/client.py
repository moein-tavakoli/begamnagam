"""Standard-library client for a single frontend/bot user; no calls at import.

Create one instance/cookie jar per (platform, bot_id, messenger_user_id). Serialize
calls for that identity. With bot_key, resume_conversation restores the server's
durable session after restart; never use one global authenticated instance.
"""
import http.cookiejar
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPCookieProcessor, Request, build_opener


class APIResponseError(Exception):
    def __init__(self, status, payload):
        self.status, self.payload = status, payload
        self.code = payload.get('error', {}).get('code', 'http_error')
        super().__init__(f'API returned HTTP {status} ({self.code})')


class TransportError(Exception):
    """Outcome may be unknown. Never generate a new send/checkout key here."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def private_update_identity(platform, update):
    """Extract routing IDs *after* the adapter has authenticated the update source.

    Only new private messages and private-message callbacks are supported. This
    parser does not verify a webhook, a phone, account ownership or consent.
    """
    if platform not in {'telegram', 'bale'} or not isinstance(update, dict):
        raise ValueError('Unsupported platform or update.')
    callback = update.get('callback_query')
    message = update.get('message')
    if callback is not None:
        if not isinstance(callback, dict) or message is not None:
            raise ValueError('Ambiguous update.')
        message, sender = callback.get('message'), callback.get('from')
    else:
        sender = message.get('from') if isinstance(message, dict) else None
    chat = message.get('chat') if isinstance(message, dict) else None
    if not isinstance(sender, dict) or not isinstance(chat, dict) or chat.get('type') != 'private' or sender.get('is_bot'):
        raise ValueError('A private user update is required.')
    values = {'user_id': sender.get('id'), 'chat_id': chat.get('id'),
              'update_id': update.get('update_id'), 'message_id': message.get('message_id')}
    for name, value in values.items():
        if type(value) is not int or value < (0 if name == 'update_id' else 1) or value >= 10**20:
            raise ValueError('Invalid canonical provider ID.')
    return {key: str(value) for key, value in values.items()}


class BotAPI:
    def __init__(self, base_url, *, cookie_jar=None, bot_key=None, require_real_otp=True, require_real_delivery=True, timeout=35):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path.rstrip('/') != '/api/v2'
                or (parsed.scheme == 'http' and parsed.hostname not in {'localhost', '127.0.0.1', '::1'})):
            raise ValueError('Use an HTTPS /api/v2 base URL (HTTP is allowed on loopback only).')
        self.base_url = base_url.rstrip('/')
        self.jar = cookie_jar if cookie_jar is not None else http.cookiejar.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.jar), NoRedirect())
        self.csrf_token = None
        self.bot_key = bot_key
        self.conversation_id = None
        self.require_real_otp = require_real_otp
        self.require_real_delivery = require_real_delivery
        self.timeout = timeout

    def call(self, method, path, data=None, *, key=None, query=None):
        if not path.startswith('/') or path.startswith('//') or '?' in path or '#' in path or '..' in path:
            raise ValueError('Pass an API resource path and a separate query mapping.')
        headers = {'Accept': 'application/json'}
        if self.bot_key:
            headers['X-Bot-Key'] = self.bot_key
        unsafe = method.upper() not in {'GET', 'HEAD', 'OPTIONS'}
        if unsafe:
            if self.csrf_token is None:
                self.refresh_session()
            headers['X-CSRFToken'] = self.csrf_token
            headers['Content-Type'] = 'application/json'
        if key is not None:
            headers['Idempotency-Key'] = str(key)
        encoded = json.dumps(data if data is not None else {}, ensure_ascii=False).encode('utf-8') if unsafe else None
        url = self.base_url + path + ('?' + urlencode(query) if query else '')
        request = Request(url, data=encoded, headers=headers, method=method.upper())
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                result = json.load(response)
                if not isinstance(result, dict):
                    raise ValueError('Expected a JSON object.')
        except HTTPError as error:
            try:
                payload = json.load(error)
                if not isinstance(payload, dict) or not isinstance(payload.get('error'), dict):
                    payload = {'error': {'code': 'http_error'}}
            except (ValueError, UnicodeDecodeError):
                payload = {'error': {'code': 'http_error'}}
            finally:
                error.close()
            raise APIResponseError(error.code, payload) from None
        except (URLError, TimeoutError, ConnectionError, ValueError, UnicodeDecodeError):
            raise TransportError('No valid API response; reconcile the existing action before retrying.') from None
        if 'csrf_token' in result:
            self.csrf_token = result['csrf_token']
        elif isinstance(result.get('session'), dict):
            self.csrf_token = result['session']['csrf_token']
        return result

    def refresh_session(self):
        return self.call('GET', '/session')

    def bootstrap(self):
        return self.call('GET', '/bootstrap')

    def resume_conversation(self, user_id, chat_id):
        if not self.bot_key:
            raise ValueError('A private adapter key is required; never use the vendor bot token.')
        result = self.call('POST', '/bot/conversations/resolutions',
            {'user_id': str(user_id), 'chat_id': str(chat_id), 'chat_type': 'private'})
        self.conversation_id = result['conversation']['id']
        return result

    def conversations(self, *, cursor=None, limit=20, step=None):
        if not self.bot_key:
            raise ValueError('A private adapter key is required.')
        query = {'limit': limit}
        query.update({name: value for name, value in {'cursor': cursor, 'step': step}.items() if value is not None})
        return self.call('GET', '/bot/conversations', query=query)

    def _conversation_path(self):
        if self.conversation_id is None:
            raise ValueError('Resume this identity first.')
        return '/bot/conversations/' + self.conversation_id

    def conversation(self):
        return self.call('GET', self._conversation_path())

    def save_state(self, *, revision, event_id, step, data):
        return self.call('PUT', self._conversation_path() + '/state',
            {'expected_revision': revision, 'event_id': str(event_id), 'step': step, 'data': data})

    def reset_state(self, *, revision, event_id):
        return self.call('DELETE', self._conversation_path() + '/state',
            {'expected_revision': revision, 'event_id': str(event_id)})

    def unlink_account(self):
        return self.call('DELETE', self._conversation_path() + '/account', {})

    def request_otp(self, phone):
        state = self.refresh_session()
        if self.require_real_otp and not state['otp_is_real']:
            raise RuntimeError('Real OTP is unavailable in this environment.')
        return self.call('POST', '/auth/otp-challenges', {'phone': phone})

    def verify_otp(self, challenge_id, code):
        return self.call('POST', '/auth/sessions', {'challenge_id': challenge_id, 'code': code})

    def getme(self):
        return self.call('GET', '/me')

    def credits(self):
        return self.call('GET', '/me/credits')

    def validate_recipient(self, phone):
        return self.call('POST', '/recipients/validations', {'phone': phone})

    def preview(self, phone, *, source_mode, text=None, category=None, message_tone=None, alternative_token=None):
        values = {'recipient_phone': phone, 'source_mode': source_mode}
        values.update({name: value for name, value in {
            'text': text, 'category': category, 'message_tone': message_tone,
            'alternative_token': alternative_token}.items() if value is not None})
        return self.call('POST', '/message-previews', values)

    def reserve_message(self, preview, phone, *, key, consent):
        if consent is not True:
            raise ValueError('An explicit user confirmation of full_sms is required.')
        return self.call('POST', '/messages', {'preview_id': preview['preview_id'], 'recipient_phone': phone,
                         'consent': True, 'terms_version': preview['terms_version']}, key=key)

    def submit_message(self, message_id):
        if self.require_real_delivery and self.refresh_session()['demo_mode']:
            raise RuntimeError('Real message delivery is unavailable in this environment.')
        return self.call('PUT', '/messages/' + str(message_id) + '/submission', {})

    def get_message(self, message_id):
        return self.call('GET', '/messages/' + str(message_id))

    def history(self, *, cursor=None, limit=20, status=None):
        query = {'limit': limit}
        query.update({name: value for name, value in {'cursor': cursor, 'status': status}.items() if value is not None})
        return self.call('GET', '/messages', query=query)

    def logout(self):
        return self.call('DELETE', '/session', {})
