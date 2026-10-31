"""REST resources for the trusted Telegram and Bale adapters."""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from core import bot_conversations as service
from core.models import BotConversation

from .contracts import BOT_STEP, PAGE_QUERY, operation as op, resource
from .pagination import paginate
from .views import session_data


@resource(get=op('listBotConversations', 'Bot conversations', 'Discover this adapter’s saved conversations after restart',
    'BotConversationSummaryPage', auth=False, bot=True, query={**PAGE_QUERY, 'step': BOT_STEP},
    description='Server-to-server only. X-Bot-Key scopes this bounded keyset page to one bot/platform. '
                'A cookie is not needed. Includes identities active in the past 30 days; never returns draft '
                'text, phone, session credentials or another adapter’s identities. Resume each identity '
                'separately before reading state or reconciling a receipt. Listing does not send messages.'))
def conversations(request):
    rows = BotConversation.objects.filter(integration=request.bot_integration,
        last_seen_at__gt=timezone.now()-timedelta(days=30))
    step = request.api_query.get('step')
    if step:
        rows = rows.filter(step=step).filter(Q(state_expires_at__isnull=True) | Q(state_expires_at__gt=timezone.now()))
    def summary(item):
        return {'id': str(item.pk), 'user_id': item.user_id, 'chat_id': item.chat_id,
            'account_id': str(item.account_id) if item.account_id else None, 'step': item.step,
            'revision': item.revision, 'state_expires_at': item.state_expires_at.isoformat() if item.state_expires_at else None,
            'created_at': item.created_at.isoformat(), 'last_seen_at': item.last_seen_at.isoformat()}
    return paginate(request, rows, summary, 'bot-conversations:' + (step or '*'),
        owner_identity='bot:' + str(request.bot_integration.pk))


@resource(post=op('resolveBotConversation', 'Bot conversations', 'Create or resume a private bot conversation',
    'BotResume', request='BotIdentityInput', auth=False, bot=True,
    description='Server-to-server only. X-Bot-Key selects the platform/bot. Obtain anonymous CSRF first. '
                'Accept identity only from a provider-authenticated private update. Restores the saved session '
                'using Set-Cookie and returns a fresh CSRF token; never accepts an account id or phone as proof. '
                'Use a separate cookie jar per identity, including before login. Expired authentication requires OTP.'))
def resolve(request):
    conversation, restored = service.resolve_conversation(request, request.api_data)
    return {'conversation': service.conversation_data(conversation), 'session': session_data(request),
            'session_restored': restored}


@resource(get=op('getBotConversation', 'Bot conversations', 'Read the current identity, account link and saved stage',
    'BotConversation', auth=False, bot=True,
    description='Requires X-Bot-Key and the cookie jar returned by resolution for this exact conversation. '
                'Private data has a 24-hour TTL; account linkage does not bypass session expiry or OTP.'))
def conversation(request, conversation_id):
    return service.conversation_data(service.owned_conversation(request, conversation_id))


@resource(put=op('putBotConversationState', 'Bot conversations', 'Atomically save a resumable conversation checkpoint',
    'BotCheckpoint', request='BotStateInput', auth=False, bot=True,
    description='Compare expected_revision, and reuse event_id with the exact same payload on retries. '
                'Duplicate checkpoints return applied:false without overwriting newer state. A conflicting '
                'revision or reused event with changed data returns 409. Data is encrypted and expires in 24 hours. '
                'A saved stage is not consent, a delivery request or an authentication credential.'),
    delete=op('deleteBotConversationState', 'Bot conversations', 'Reset the saved stage without unlinking the account',
    'BotCheckpoint', request='BotResetInput', auth=False, bot=True))
def state(request, conversation_id):
    conversation = service.owned_conversation(request, conversation_id)
    applied = service.checkpoint(request, conversation, request.api_data, reset=request.method == 'DELETE')
    return {'conversation': service.conversation_data(conversation), 'applied': applied}


@resource(delete=op('unlinkBotConversationAccount', 'Bot conversations', 'Log out and remove the account link and private draft',
    'BotResume', request='Empty', auth=False, bot=True,
    description='Only affects this adapter identity. Other bots and the website keep their own sessions. '
                'No account id is accepted. Linking happens automatically only after successful OTP in this session.'))
def account(request, conversation_id):
    conversation = service.owned_conversation(request, conversation_id)
    service.unlink_account(request, conversation)
    return {'conversation': service.conversation_data(conversation), 'session': session_data(request),
            'session_restored': False}
