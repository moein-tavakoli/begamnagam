"""REST resources. Dispatch, billing, moderation and privacy stay in core."""
import json

from django.conf import settings
from django.middleware.csrf import get_token
from django.utils import timezone

from core import invitations as invitation_service, services, views as legacy
from core import manual_payment_views, package_views, support_views, wallet_views
from core.ai_config import current as ai_configuration
from core.freeform import available as freeform_available
from core.limits import policy
from core.message_examples import public_catalog
from core.message_tones import choices as tone_choices, resolve as resolve_tone
from core.models import Account, CreditEntry, Invitation, InvitationSend, MessagePackage, Order, Preview, WalletEntry, WalletTopup
from core.otp import OTP_LENGTH
from core.packages import balance_field, checkout_enabled, credit_environment, package_data, purchase_data
from core.payment_options import options as payment_options
from core.privacy import digest, mask, normalize_phone
from core.services import APIError, is_product_authenticated
from core.wallet import balance_field as wallet_balance_field, summary as wallet_summary, topup_data

from .contracts import PAGE_QUERY, STATUS, integer, operation as op, resource
from .pagination import paginate


def delegate(request, view, *, method=None, **kwargs):
    """Adapt HTTP verbs while preserving all legacy service guards and errors."""
    original = request.method
    try:
        request.method = method or original
        response = view(request, **kwargs)
    finally:
        request.method = original
    return response if response.status_code >= 400 else json.loads(response.content)


def recent_auth(request):
    return 0 <= timezone.now().timestamp() - request.session.get('phone_verified_at', 0) <= 300


def session_data(request):
    authenticated = is_product_authenticated(request.user) and request.user.is_active
    return {'authenticated': authenticated, 'csrf_token': get_token(request),
            'recent_auth': bool(authenticated and recent_auth(request)),
            'expires_in': request.session.get_expiry_age(), 'otp_length': OTP_LENGTH,
            'demo_mode': settings.DEMO_MODE, 'otp_is_real': legacy.otp_is_real()}


def me_data(request):
    account = Account.objects.get(user=request.user)
    return {'id': str(account.pk), 'phone_masked': account.phone_masked, 'suspended': account.suspended,
            'deletion_requested_at': account.deletion_requested_at.isoformat() if account.deletion_requested_at else None,
            'recent_auth': recent_auth(request)}


def credit_data(request):
    account = Account.objects.get(user=request.user)
    purchased = getattr(account, balance_field())
    return {'gift_remaining': account.free_sends_remaining, 'gift_total': 3 + account.free_sends_earned_total,
            'invitation_rewards_total': account.free_sends_earned_total, 'purchased_remaining': purchased,
            'total_remaining': account.free_sends_remaining + purchased,
            'wallet_balance_toman': str(getattr(account, wallet_balance_field())), 'environment': credit_environment()}


def catalog_data():
    config, limits = ai_configuration(), policy()
    freeform = freeform_available(config)
    catalog = public_catalog(freeform=freeform)
    return {'categories': catalog['category_groups'],
            'examples': [{'id': int(item['key']), 'category_id': item['group_id'], 'topic': item['id'],
                          'label': item['label'], 'description': item['description'], 'text': item['example']}
                         for item in catalog['categories']],
            'message_tones': tone_choices(config), 'default_message_tone': resolve_tone(None, config),
            'rewrite_mode': config.provider if freeform else 'template', 'freeform_enabled': freeform,
            'message_packages': [package_data(item) for item in MessagePackage.objects.filter(active=True)],
            'package_checkout_enabled': checkout_enabled(), 'payment_options': payment_options(),
            'terms_version': settings.TERMS_VERSION, 'support_contact': settings.SUPPORT_CONTACT,
            'invitation_policy': {'consent_version': invitation_service.CONSENT_VERSION,
                                  'max_sends': limits.invitation_max_sends or None,
                                  'cooldown_hours': limits.invitation_cooldown_hours,
                                  'validity_days': limits.invitation_validity_days or None,
                                  'window_hours': limits.invitation_window_hours,
                                  'window_limit': limits.invitation_limit if limits.invitation_window_hours and limits.invitation_limit else None}}


@resource(get=op('getSession', 'Authentication', 'Get session and CSRF token', 'Session', auth=False),
          delete=op('deleteSession', 'Authentication', 'Log out this session', 'Session', request='Empty'))
def session(request):
    if request.method == 'DELETE':
        result = delegate(request, legacy.logout_view, method='POST')
        if not isinstance(result, dict):
            return result
    else:
        legacy.session_key(request)
    return session_data(request)


@resource(get=op('getBootstrap', 'Catalog', 'Get all startup data in one request', 'Bootstrap', auth=False,
                 description='Anonymous responses omit me and credits. No history or private recipient state is included.'))
def bootstrap(request):
    legacy.session_key(request)
    value = {'session': session_data(request), 'catalog': catalog_data()}
    if value['session']['authenticated']:
        value.update(me=me_data(request), credits=credit_data(request))
    return value


@resource(post=op('createOTPChallenge', 'Authentication', 'Send a phone verification code', 'OTPChallenge',
                  request='OTPInput', auth=False, status=201,
                  description='Bound to this cookie jar. A timeout is not permission to resend automatically. Real provider failures stay failures.'))
def otp_challenges(request):
    return delegate(request, legacy.request_otp)


@resource(post=op('createSession', 'Authentication', 'Verify OTP and start a product session', 'Session',
                  request='LoginInput', auth=False, status=201,
                  description='The returned csrf_token replaces the previous token. A messenger contact alone does not authenticate.'))
def sessions(request):
    result = delegate(request, legacy.verify_otp)
    return session_data(request) if isinstance(result, dict) else result


@resource(get=op('getMe', 'Account', 'Get the verified account (getMe)', 'Me'))
def me(request):
    return me_data(request)


@resource(get=op('getCredits', 'Account', 'Get gift, purchased and wallet balances', 'Credits'))
def credits(request):
    return credit_data(request)


@resource(get=op('getCatalog', 'Catalog', 'Get current categories, examples, tones, packages and capabilities', 'Catalog', auth=False))
def catalog(request):
    return catalog_data()


def static_page(values):
    # Small configuration lists are returned in full; histories use keyset pages.
    return {'results': values, 'next_cursor': None, 'has_more': False}


@resource(get=op('listCategories', 'Catalog', 'List active example categories', 'CategoryPage', auth=False))
def categories(request):
    return static_page(catalog_data()['categories'])


@resource(get=op('listCategoryExamples', 'Catalog', 'List active examples in a category', 'ExamplePage', auth=False))
def examples(request, category_id):
    data = catalog_data()
    if not any(item['id'] == category_id for item in data['categories']):
        raise APIError('not_found', 'دسته‌بندی پیدا نشد.', 404)
    return static_page([item for item in data['examples'] if item['category_id'] == category_id])


@resource(get=op('listPackages', 'Credits and payments', 'List available message packages', 'PackagePage', auth=False))
def packages(request):
    return static_page([package_data(item) for item in MessagePackage.objects.filter(active=True)])


@resource(post=op('validateRecipient', 'Messages', 'Normalize the entered destination phone', 'RecipientValidation',
                  request='OTPInput', description='Syntax and self-recipient validation only. Never checks membership, opt-out or availability. No SMS is sent.'))
def recipient_validations(request):
    phone = normalize_phone(request.api_data['phone'])
    if digest(phone) == request.user.account.phone_hash:
        raise APIError('self_recipient', 'شمارهٔ گیرنده باید با شمارهٔ خودت متفاوت باشد.', 422)
    return {'valid': True, 'phone': phone, 'phone_masked': mask(phone)}


@resource(post=op('createMessagePreview', 'Messages', 'Review and seal an exact recipient-bound SMS preview', 'Preview',
                  request='PreviewInput', status=201,
                  description='Show full_sms and obtain explicit consent. Freeform never silently falls back. Changing the phone or text requires a new preview.'))
def previews(request):
    return delegate(request, legacy.preview)


@resource(get=op('getMessagePreview', 'Messages', 'Retrieve your unexpired sealed preview', 'Preview',
                 description='Reads the stored snapshot without another AI call. Expired previews require a new review and consent.'))
def preview(request, preview_id):
    item = Preview.objects.filter(owner=request.user, pk=preview_id).first()
    if not item:
        raise APIError('not_found', 'پیش‌نمایش پیدا نشد.', 404)
    if item.expires_at <= timezone.now():
        raise APIError('preview_expired', 'پیش‌نمایش منقضی شده است؛ دوباره متن را آماده کن.', 409)
    units = len(item.full_sms.encode('utf-16-le')) // 2
    return {'preview_id': str(item.pk), 'payment_method': item.payment_method,
            'wallet_terms_version': item.wallet_policy_version,
            'rewritten_text': item.generated_body if item.moderation_mode in {'gapgpt', 'ollama'} else item.text,
            'price_toman': item.price_toman, 'is_free': item.is_free, 'message_tone': item.message_tone,
            'expires_at': item.expires_at.isoformat(), 'moderation_mode': item.moderation_mode,
            'terms_version': item.terms_version, 'full_sms': item.full_sms,
            'sms_segments': 1 if units <= 70 else (units + 66) // 67}


@resource(get=op('listMessages', 'Messages', 'List the current account’s message history', 'MessagePage',
                 query={**PAGE_QUERY, 'status': STATUS}),
          post=op('createMessage', 'Messages', 'Reserve one credit for a reviewed message', 'Message', request='MessageInput', key=True,
                  description='Does not send yet. Store the returned id, then PUT its submission resource. Retries return the same message and never reserve a second credit.'))
def messages(request):
    if request.method == 'POST':
        return delegate(request, legacy.create_order)
    rows = Order.objects.filter(owner=request.user)
    status = request.api_query.get('status')
    if status:
        rows = rows.filter(status=status)
    return paginate(request, rows, services.serialize_order, 'messages:' + (status or '*'), serialize_many=services.serialize_orders)


@resource(get=op('getMessage', 'Messages', 'Get receipt and delivery status', 'Message'))
def message(request, message_id):
    return services.serialize_order(services.get_owned_order(request.user, message_id))


@resource(put=op('submitMessage', 'Messages', 'Authorize delivery of the reserved message', 'Message', request='Empty',
                 description='Idempotent by message id. accepted means provider acceptance; delivered is a receipt. Never resend unknown/accepted messages as a new order.'))
def submission(request, message_id):
    return delegate(request, legacy.confirm_free, method='POST', order_id=message_id)


@resource(get=op('getPreferences', 'Account', 'Get receiving preference for your own phone', 'Preferences'),
          patch=op('updatePreferences', 'Account', 'Change receiving preference for your own phone', 'Preferences', request='PreferencesInput',
                   description='Unblocking requires a phone verification in the last five minutes. A destination phone cannot be supplied.'))
def preferences(request):
    return delegate(request, legacy.preferences, method='POST' if request.method == 'PATCH' else 'GET')


@resource(post=op('requestAccountDeletion', 'Account', 'Request account redaction', 'Deletion', request='Empty',
                  description='Requires phone verification in the last five minutes; suspends sending immediately.'))
def deletion_requests(request):
    return delegate(request, legacy.request_deletion)


def current_environment(rows):
    return rows.exclude(environment='live') if settings.DEMO_MODE else rows.filter(environment='live')


@resource(get=op('getWallet', 'Credits and payments', 'Get wallet balance and payment capabilities', 'Wallet'))
def wallet(request):
    return wallet_summary(request.user)


@resource(get=op('listWalletEntries', 'Credits and payments', 'List wallet ledger movements', 'WalletEntryPage', query=PAGE_QUERY))
def wallet_entries(request):
    def serialize(row):
        return {'id': str(row.pk), 'kind': row.kind, 'amount_toman': row.amount_toman,
                'balance_after_toman': str(row.balance_after_toman), 'created_at': row.created_at.isoformat(),
                'order_id': str(row.order_id) if row.order_id else None,
                'purchase_id': str(row.purchase_id) if row.purchase_id else None}
    return paginate(request, current_environment(WalletEntry.objects.filter(account__user=request.user)), serialize, 'wallet-entries')


@resource(get=op('listCreditEntries', 'Credits and payments', 'List purchased-message credit movements', 'CreditEntryPage', query=PAGE_QUERY,
                 description='Gift/reward balances are in GET /me/credits; this ledger records purchased units only.'))
def credit_entries(request):
    def serialize(row):
        return {'id': str(row.pk), 'kind': row.kind, 'units': row.units, 'created_at': row.created_at.isoformat(),
                'order_id': str(row.order_id) if row.order_id else None,
                'purchase_id': str(row.purchase_id) if row.purchase_id else None}
    return paginate(request, current_environment(CreditEntry.objects.filter(account__user=request.user)), serialize, 'credit-entries')


@resource(get=op('listCreditPurchases', 'Credits and payments', 'List package purchases', 'PurchasePage', query=PAGE_QUERY),
          post=op('createCreditPurchase', 'Credits and payments', 'Buy a package using an enabled payment method', 'Purchase', request='PurchaseInput', key=True,
                  description='Uses server package/revision snapshots. Disabled paid checkout stays disabled. Send redirect_url as an external button; verify server-side only.'))
def purchases(request):
    if request.method == 'POST':
        return delegate(request, package_views.purchases)
    return paginate(request, package_views.own_purchases(request.user), purchase_data, 'purchases')


@resource(get=op('getCreditPurchase', 'Credits and payments', 'Get a purchase and its verified credit status', 'Purchase'),
          delete=op('cancelCardPurchase', 'Credits and payments', 'Cancel an unreviewed card-transfer purchase', 'Purchase', request='Empty',
                    description='Card purchases only; never cancels a captured gateway payment.'))
def purchase(request, purchase_id):
    if request.method == 'DELETE':
        return delegate(request, manual_payment_views.cancel, method='POST', purchase_id=purchase_id)
    return delegate(request, package_views.purchase_detail, purchase_id=purchase_id)


@resource(put=op('submitCardReceipt', 'Credits and payments', 'Acknowledge sending a transfer receipt to support', 'Purchase', request='ReceiptInput',
                 description='No file upload. Send the receipt through receipt_channels, then acknowledge it here. Credit requires staff review.'))
def receipt(request, purchase_id):
    return delegate(request, manual_payment_views.receipt, method='POST', purchase_id=purchase_id)


@resource(get=op('listWalletTopups', 'Credits and payments', 'List wallet topups', 'TopupPage', query=PAGE_QUERY),
          post=op('createWalletTopup', 'Credits and payments', 'Create a wallet topup checkout', 'Topup', request='TopupInput', key=True))
def topups(request):
    if request.method == 'POST':
        return delegate(request, wallet_views.topups)
    return paginate(request, current_environment(WalletTopup.objects.filter(owner=request.user)), topup_data, 'topups')


@resource(get=op('getWalletTopup', 'Credits and payments', 'Get independently verified topup status', 'Topup'))
def topup(request, topup_id):
    return delegate(request, wallet_views.topup, topup_id=topup_id)


@resource(get=op('listInvitations', 'Invitations', 'List your invitations and signup rewards', 'InvitationPage', query=PAGE_QUERY),
          post=op('createInvitation', 'Invitations', 'Invite a willing contact by phone', 'Invitation', request='InvitationInput', key=True,
                  description='This explicit invitation flow alone may report existing membership. Never exposes opt-out or another inviter.'))
def invitations(request):
    if request.method == 'POST':
        return delegate(request, invitation_service.invitations_view)
    rows = Invitation.objects.filter(inviter=request.user).prefetch_related('sends')
    return paginate(request, rows, invitation_service.serialize, 'invitations')


@resource(get=op('getInvitationSummary', 'Invitations', 'Get invitation totals, rewards and remaining request quota', 'InvitationSummary'))
def invitation_summary(request):
    from datetime import timedelta
    from django.db.models import Count, Q
    limits = policy()
    counts = Invitation.objects.filter(inviter=request.user).aggregate(
        total=Count('pk'), registered=Count('pk', filter=Q(registered_at__isnull=False)),
        rewarded=Count('pk', filter=Q(reward_awarded_at__isnull=False)))
    limit = limits.invitation_limit if limits.invitation_window_hours else 0
    used = InvitationSend.objects.filter(invitation__inviter=request.user,
        created_at__gt=timezone.now() - timedelta(hours=limits.invitation_window_hours)).count() if limit else 0
    return {'total': counts['total'], 'registered': counts['registered'], 'earned_credits': counts['rewarded'] * 3,
            'daily_remaining': max(0, limit - used) if limit else None}


@resource(get=op('getInvitation', 'Invitations', 'Get your invitation and resend eligibility', 'Invitation'))
def invitation(request, invitation_id):
    item = Invitation.objects.filter(inviter=request.user, pk=invitation_id).prefetch_related('sends').first()
    if not item:
        raise APIError('not_found', 'دعوت پیدا نشد.', 404)
    return invitation_service.serialize(item)


@resource(post=op('createInvitationReminder', 'Invitations', 'Request an explicit invitation reminder', 'Invitation', request='ReminderInput', key=True,
                  description='Only when can_resend permits. Store one idempotency key per confirmed reminder; no automatic replay of uncertain sends.'))
def reminders(request, invitation_id):
    return delegate(request, invitation_service.resend_view, invitation_id=invitation_id)


@resource(get=op('getSupportSummary', 'Support', 'Get unread support count and staff presence', 'SupportSummary'))
def support_summary(request):
    return delegate(request, support_views.summary)


@resource(get=op('listSupportMessages', 'Support', 'Get the private support conversation', 'SupportPage',
                 query={'before': integer(minimum=1, maximum=2147483647)},
                 description='Up to 50 messages, chronological within a page. Use before_cursor for older messages; has_older=false ends pagination.'),
          post=op('createSupportMessage', 'Support', 'Send a private text to support', 'SupportSent', request='SupportInput', key=True))
def support_messages(request):
    # The legacy parser accepts ASCII integers. Use the already validated value.
    if request.method == 'GET' and 'before' in request.api_query:
        from core import support
        from core.models import SupportConversation
        services.limited('support-customer-read', str(request.user.pk), 120, 60)
        return support.page_messages(request.user, SupportConversation.objects.filter(account__user=request.user).first(), request.api_query['before'])
    return delegate(request, support_views.messages)


@resource(put=op('updateSupportReadMarker', 'Support', 'Acknowledge displayed support messages', 'OK', request='ReadInput'))
def support_read(request):
    return delegate(request, support_views.read, method='POST')


@resource(post=op('inspectRecipientCapability', 'Recipient controls', 'Inspect a received private link', 'Capability', request='CapabilityInput', auth=False))
def capability(request):
    return delegate(request, legacy.recipient_action, action='inspect')


@resource(put=op('stopRecipientMessages', 'Recipient controls', 'Stop receiving using a received private link', 'Preferences', request='CapabilityInput', auth=False))
def recipient_preferences(request):
    return delegate(request, legacy.recipient_action, method='POST', action='stop')


@resource(post=op('createRecipientReport', 'Recipient controls', 'Report a received message and stop receiving', 'Report', request='ReportInput', auth=False))
def recipient_reports(request):
    return delegate(request, legacy.recipient_action, action='report')
