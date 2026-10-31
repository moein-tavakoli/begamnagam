"""Durable trusted-adapter identities, sessions and bounded private checkpoints.

The adapter authenticates provider updates before resolving an identity. A chat
id alone is never a product credential. Cookies and CSRF remain mandatory.
"""
import hashlib
import hmac
import json
import re
import secrets
import uuid
from datetime import timedelta
from importlib import import_module

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user, logout
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import IntegrityError, transaction
from django.middleware.csrf import rotate_token
from django.utils import timezone

from .input_digits import ascii_digits
from .models import BotConversation, BotConversationEvent, BotIntegration, OTPChallenge, Order, Preview
from .privacy import digest, normalize_phone
from .services import APIError, error_response, is_product_authenticated, limited

SESSION_MARKER = 'bot_conversation_id'
STATE_TTL = timedelta(hours=24)


def new_credential(integration):
    secret = secrets.token_urlsafe(32)
    integration.secret_digest = hashlib.sha256(secret.encode()).hexdigest()
    return str(integration.pk) + '.' + secret


def authenticate_bot(request):
    cached = getattr(request, 'bot_integration', None)
    if cached is not None:
        return cached
    limited('bot-key-ip', request.META.get('REMOTE_ADDR', 'unknown'), 20000, 60)
    token = request.headers.get('X-Bot-Key', '')
    try:
        identifier, secret = token.split('.', 1)
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', secret):
            raise ValueError
        integration = BotIntegration.objects.get(pk=uuid.UUID(identifier), active=True)
    except (ValueError, BotIntegration.DoesNotExist):
        raise APIError('bot_authentication_required', 'کلید معتبر ربات لازم است.', 401) from None
    if not hmac.compare_digest(integration.secret_digest, hashlib.sha256(secret.encode()).hexdigest()):
        raise APIError('bot_authentication_required', 'کلید معتبر ربات لازم است.', 401)
    limited('bot-key', str(integration.pk), 10000, 60)
    request.bot_integration = integration
    return integration


def reset_state(conversation, step='start'):
    conversation.step, conversation.data = step, '{}'
    conversation.revision += 1
    conversation.state_expires_at = None


def expire_state(conversation):
    if conversation.state_expires_at and conversation.state_expires_at <= timezone.now():
        reset_state(conversation, 'menu' if conversation.account_id else 'awaiting_phone')
        conversation.save(update_fields=['step', 'data', 'revision', 'state_expires_at'])


def synchronize(request, conversation, *, touch=True):
    """Reconcile authentication and session references under the conversation lock."""
    account = request.user.account if is_product_authenticated(request.user) and request.user.is_active else None
    account_id = account.pk if account else None
    fields = []
    if account_id != conversation.account_id:
        conversation.account = account
        reset_state(conversation, 'menu' if account else 'awaiting_phone')
        fields = ['account', 'step', 'data', 'revision', 'state_expires_at']
    elif account and conversation.step == 'awaiting_otp':
        reset_state(conversation, 'menu')
        fields = ['step', 'data', 'revision', 'state_expires_at']
    if conversation.session_key != (request.session.session_key or ''):
        conversation.session_key = request.session.session_key or ''
        fields.append('session_key')
    if touch:
        conversation.last_seen_at = timezone.now()
        fields.append('last_seen_at')
    if fields:
        conversation.save(update_fields=fields)


def authenticate_saved_session(request, conversation):
    """Invalidated authentication cannot come back when an account is re-enabled."""
    previous = request.session.session_key
    had_login = bool(request.session.get(SESSION_KEY))
    request.user = get_user(request)
    request._cached_user = request.user
    if had_login and (not is_product_authenticated(request.user) or not request.user.is_active):
        request.session.flush()
        conversation.account = None
        reset_state(conversation, 'awaiting_phone')
        conversation.save(update_fields=['account', 'step', 'data', 'revision', 'state_expires_at'])
    request.session[SESSION_MARKER] = str(conversation.pk)
    return previous == request.session.session_key


class BotSessionMiddleware(SessionMiddleware):
    """Serialize bot-owned requests through session save, including login rotation.

Regular web sessions retain Django's normal handling. A bot-owned cookie can
only be used on operational v2 routes and with its current adapter credential.
"""
    def __call__(self, request):
        self.process_request(request)
        identifier = request.session.get(SESSION_MARKER)
        if not identifier:
            if request.path == '/api/v2/bot/conversations/resolutions':
                # Keep resolution's row lock until SessionMiddleware has saved
                # Set-Cookie. Another process must never restore half a login.
                with transaction.atomic():
                    response = self.get_response(request)
                    response = self.process_response(request, response)
                    if response.status_code >= 500:
                        transaction.set_rollback(True)
                    elif hasattr(request, 'bot_conversation'):
                        synchronize(request, request.bot_conversation)
                    return response
            response = self.get_response(request)
            return self.process_response(request, response)
        try:
            integration = authenticate_bot(request)
            if not request.path.startswith('/api/v2/') or request.path.startswith('/api/v2/document'):
                raise APIError('bot_session_scope', 'نشست ربات فقط برای API محصول معتبر است.', 403)
            with transaction.atomic():
                try:
                    conversation = BotConversation.objects.select_for_update().get(pk=identifier, integration=integration)
                except (BotConversation.DoesNotExist, ValueError):
                    raise APIError('not_found', 'مکالمه پیدا نشد.', 404) from None
                if conversation.session_key != request.session.session_key:
                    raise APIError('stale_bot_session', 'نشست مکالمه را دوباره بازیابی کن.', 409)
                limited('bot-conversation', str(conversation.pk), 300, 60)
                conversation.integration = integration
                request.bot_conversation = conversation
                if not authenticate_saved_session(request, conversation):
                    request.session.save()
                synchronize(request, conversation, touch=False)
                response = self.get_response(request)
                # logout/login may flush the marker. Keep this isolated session
                # attached to its identity, without restoring old authentication.
                request.session[SESSION_MARKER] = str(conversation.pk)
                response = self.process_response(request, response)
                # Handled provider errors can deliberately return 503 after
                # recording spend/unknown outcomes. Preserve those records.
                if response.status_code < 500:
                    synchronize(request, conversation)
                return response
        except APIError as error:
            return error_response(error)


def conversation_data(conversation):
    expire_state(conversation)
    data = json.loads(conversation.data)
    action = 'continue' if conversation.account_id else 'authenticate'
    if not conversation.account_id and conversation.step == 'awaiting_otp' and OTPChallenge.objects.filter(
            pk=data.get('challenge_id'), session_key=conversation.session_key,
            consumed_at__isnull=True, expires_at__gt=timezone.now()).exists():
        action = 'enter_otp'
    elif conversation.account_id:
        if data.get('message_id') or conversation.step == 'submitting':
            action = 'reconcile_message'
        elif data.get('preview_id') and not Preview.objects.filter(pk=data['preview_id'],
                owner__account__pk=conversation.account_id, session_key=conversation.session_key,
                expires_at__gt=timezone.now()).exists():
            action = 'refresh_preview'
    return {'id': str(conversation.pk), 'platform': conversation.integration.platform,
            'bot_id': conversation.integration.bot_id, 'user_id': conversation.user_id,
            'chat_id': conversation.chat_id, 'account_id': str(conversation.account_id) if conversation.account_id else None,
            'step': conversation.step, 'data': data, 'revision': conversation.revision, 'resume_action': action,
            'state_expires_at': conversation.state_expires_at.isoformat() if conversation.state_expires_at else None}


def resolve_conversation(request, data):
    integration = request.bot_integration
    current = getattr(request, 'bot_conversation', None)
    if current is not None and (current.user_id != data['user_id'] or current.chat_id != data['chat_id']):
        raise APIError('conversation_conflict', 'برای هر هویت، کلاینت و نشست جدا بساز.', 409)
    # The unique user constraint also serializes first-contact races on Postgres.
    with transaction.atomic():
        user_hash = digest('bot-user:' + str(integration.pk) + ':' + data['user_id'])
        chat_hash = digest('bot-chat:' + str(integration.pk) + ':' + data['chat_id'])
        if BotConversation.objects.filter(integration=integration, chat_hash=chat_hash).exclude(user_hash=user_hash).exists():
            raise APIError('identity_conflict', 'هویت گفت‌وگوی خصوصی سازگار نیست.', 409)
        try:
            with transaction.atomic():
                conversation, _ = BotConversation.objects.get_or_create(integration=integration, user_hash=user_hash,
                    defaults={'chat_hash': chat_hash, 'user_id': data['user_id'], 'chat_id': data['chat_id']})
        except IntegrityError:
            raise APIError('identity_conflict', 'هویت گفت‌وگوی خصوصی سازگار نیست.', 409) from None
        conversation = BotConversation.objects.select_for_update().get(pk=conversation.pk)
        conversation.integration = integration
        if conversation.chat_hash != chat_hash:
            raise APIError('identity_conflict', 'شناسهٔ گفت‌وگوی خصوصی تغییر کرده است.', 409)
        store = import_module(settings.SESSION_ENGINE).SessionStore
        session = store(session_key=conversation.session_key or None)
        restored = session.get(SESSION_MARKER) == str(conversation.pk)
        if not restored:
            session = store()
        request.session = session
        request.__dict__.pop('_cached_user', None)
        restored = authenticate_saved_session(request, conversation) and restored
        request.session.save()
        # A new CSRF cookie/header pair is issued on every explicit resume.
        rotate_token(request)
        synchronize(request, conversation, touch=False)
        request.bot_conversation = conversation
        return conversation, restored


def owned_conversation(request, identifier):
    conversation = getattr(request, 'bot_conversation', None)
    if conversation is None or conversation.pk != identifier or conversation.integration_id != request.bot_integration.pk:
        raise APIError('not_found', 'مکالمه پیدا نشد.', 404)
    return conversation


def validate_flow(request, data):
    values = dict(data)
    if 'text' in values:
        values['text'] = ascii_digits(values['text'])
    if 'recipient_phone' in values:
        values['recipient_phone'] = normalize_phone(values['recipient_phone'])
    for field, model in [('preview_id', Preview), ('message_id', Order)]:
        if field not in values:
            continue
        if not is_product_authenticated(request.user):
            raise APIError('authentication_required', 'ابتدا شمارهٔ خودت را تأیید کن.', 401)
        query = model.objects.filter(pk=values[field], owner=request.user)
        if model is Preview:
            query = query.filter(session_key=request.session.session_key, expires_at__gt=timezone.now())
        if not query.exists():
            raise APIError('invalid_flow_resource', 'منبع مرحله معتبر یا متعلق به این نشست نیست.', 409)
    if 'challenge_id' in values and not OTPChallenge.objects.filter(pk=values['challenge_id'],
            session_key=request.session.session_key, consumed_at__isnull=True, expires_at__gt=timezone.now()).exists():
        raise APIError('invalid_flow_resource', 'چالش ورود معتبر نیست.', 409)
    return values


def checkpoint(request, conversation, payload, *, reset=False):
    """The caller holds the conversation lock through response/session save."""
    expire_state(conversation)
    event_hash = digest('bot-event:' + payload['event_id'])
    payload_digest = digest(json.dumps({'reset': reset, **payload}, sort_keys=True, separators=(',', ':'), ensure_ascii=False))
    event = conversation.events.filter(event_hash=event_hash).first()
    if event:
        if not hmac.compare_digest(event.payload_digest, payload_digest):
            raise APIError('event_conflict', 'شناسهٔ رویداد قبلاً با دادهٔ دیگری استفاده شده است.', 409)
        return False
    if conversation.revision != payload['expected_revision']:
        raise APIError('conversation_conflict', 'مرحله تغییر کرده؛ وضعیت تازه را بگیر.', 409)
    values = {} if reset else validate_flow(request, payload['data'])
    if not reset:
        required = {'awaiting_otp': {'challenge_id'},
                    'awaiting_confirmation': {'preview_id', 'recipient_phone'},
                    'submitting': {'preview_id', 'recipient_phone', 'idempotency_key'},
                    'receipt': {'message_id'}}.get(payload['step'], set())
        if not required.issubset(values):
            raise APIError('invalid_flow_state', 'اطلاعات لازم برای این مرحله کامل نیست.', 422)
    conversation.step = ('menu' if conversation.account_id else 'start') if reset else payload['step']
    conversation.data = json.dumps(values, ensure_ascii=False, separators=(',', ':'))
    conversation.revision += 1
    conversation.state_expires_at = timezone.now() + STATE_TTL
    conversation.save(update_fields=['step', 'data', 'revision', 'state_expires_at'])
    BotConversationEvent.objects.create(conversation=conversation, event_hash=event_hash, payload_digest=payload_digest)
    return True


def unlink_account(request, conversation):
    logout(request)
    rotate_token(request)
    request.session[SESSION_MARKER] = str(conversation.pk)
    request.session.save()
    synchronize(request, conversation)
    # Even an anonymous draft must be removed on explicit unlink.
    reset_state(conversation, 'awaiting_phone')
    conversation.save(update_fields=['step', 'data', 'revision', 'state_expires_at'])
