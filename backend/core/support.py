"""Private text-only support. Reading and answering are separate acknowledgements."""
import unicodedata
import uuid
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from .models import Account, OperatorAudit, SupportConversation, SupportMessage
from .privacy import DIGITS, digest, normalize_phone
from .services import APIError, limited

PAGE_SIZE = 50
MAX_TEXT = 2000
PRESENCE_KEY = 'support:staff-present:v1'


def staff_required(actor):
    if not actor.is_active or not actor.is_staff:
        raise APIError('forbidden', 'فقط ادمین واردشده می‌تواند به پشتیبانی دسترسی داشته باشد.', 403)


def normalize_text(value):
    if not isinstance(value, str):
        raise APIError('invalid_support_text', 'پیام متنی وارد کن؛ ارسال فایل مجاز نیست.', 422)
    if len(value) > 4000:
        raise APIError('invalid_support_text', 'هر پیام حداکثر ۲۰۰۰ نویسه دارد.', 422)
    value = unicodedata.normalize('NFC', value.replace('\r\n', '\n').replace('\r', '\n')).strip()
    if not value or len(value) > MAX_TEXT or not any(not c.isspace() and unicodedata.category(c) not in {'Cf','Cc'} for c in value):
        raise APIError('invalid_support_text', 'پیام باید بین ۱ تا ۲۰۰۰ نویسه باشد.', 422)
    if any((unicodedata.category(c) == 'Cc' and c not in '\n\t') or c in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069' for c in value):
        raise APIError('invalid_support_text', 'نویسهٔ کنترلی نامعتبر را از پیام حذف کن.', 422)
    return value


def client_key(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise APIError('invalid_input', 'کلید یکتای پیام معتبر نیست.', 422) from None


def presence(active=False):
    try:
        if active:
            cache.set(PRESENCE_KEY, True, timeout=45)
        return bool(cache.get(PRESENCE_KEY))
    except Exception:
        return False


def thread_data(thread, *, staff=False):
    if not thread:
        return None
    value = {'id': str(thread.pk), 'status': thread.status, 'last_sequence': thread.last_sequence,
        'last_customer_sequence': thread.last_customer_sequence, 'answered_customer_sequence': thread.answered_customer_sequence,
        'staff_read_sequence': thread.staff_read_sequence, 'customer_read_sequence': thread.customer_read_sequence,
        'needs_reply': thread.last_customer_sequence > thread.answered_customer_sequence,
        'updated_at': thread.updated_at.isoformat(), 'closed_at': thread.closed_at.isoformat() if thread.closed_at else None}
    if staff:
        value.update(account_id=thread.account_id, phone_masked=thread.account.phone_masked)
    return value


def message_data(message, actor):
    return {'id': str(message.pk), 'sequence': message.sequence, 'role': message.role,
        'text': message.text, 'redacted': bool(message.redacted_at), 'created_at': message.created_at.isoformat(),
        **({'client_key': str(message.client_key)} if message.author_id == actor.pk else {})}


def staff_summary(actor):
    staff_required(actor)
    rows = SupportConversation.objects.all()
    return {'attention_count': rows.filter(Q(last_customer_sequence__gt=F('answered_customer_sequence')) |
        Q(last_customer_sequence__gt=F('staff_read_sequence'))).count(),
        'waiting_count': rows.filter(last_customer_sequence__gt=F('answered_customer_sequence')).count()}


def customer_summary(actor):
    thread = SupportConversation.objects.filter(account__user=actor).first()
    return {'unread_count': thread.messages.filter(role='staff', sequence__gt=thread.customer_read_sequence).count() if thread else 0,
        'staff_online': presence()}


def conversation_for_staff(actor, identifier, *, lock=False):
    staff_required(actor)
    query = SupportConversation.objects.select_for_update() if lock else SupportConversation.objects.select_related('account')
    thread = query.filter(pk=identifier).first()
    if not thread:
        raise APIError('not_found', 'گفت‌وگو پیدا نشد.', 404)
    return thread


def page_messages(actor, thread, before=None, *, staff=False):
    if before is not None and (type(before) is not int or before < 1):
        raise APIError('invalid_input', 'نشان صفحه معتبر نیست.', 422)
    rows = thread.messages.all() if thread else SupportMessage.objects.none()
    if before is not None:
        rows = rows.filter(sequence__lt=before)
    values = list(rows.order_by('-sequence')[:PAGE_SIZE+1])
    has_older = len(values) > PAGE_SIZE
    values = list(reversed(values[:PAGE_SIZE]))
    return {'thread': thread_data(thread, staff=staff), 'messages': [message_data(m, actor) for m in values],
        'has_older': has_older, 'before_cursor': values[0].sequence if has_older else None, 'staff_online': presence(active=staff)}


def inbox(actor, data):
    staff_required(actor)
    if not isinstance(data,dict) or set(data)-{'query','page','filter'}:
        raise APIError('invalid_input', 'فیلتر پشتیبانی معتبر نیست.', 422)
    page, query, kind = data.get('page',1), data.get('query',''), data.get('filter','waiting')
    if type(page) is not int or not 1 <= page <= 100000 or not isinstance(query,str) or len(query)>100 or not isinstance(kind,str) or kind not in {'waiting','all','closed'}:
        raise APIError('invalid_input', 'فیلتر پشتیبانی معتبر نیست.', 422)
    rows = SupportConversation.objects.select_related('account')
    if kind == 'waiting':
        rows = rows.filter(Q(last_customer_sequence__gt=F('answered_customer_sequence')) | Q(last_customer_sequence__gt=F('staff_read_sequence')))
    elif kind == 'closed':
        rows = rows.filter(status='closed')
    query = query.translate(DIGITS).strip()
    if query:
        try:
            rows = rows.filter(account__phone_hash=digest(normalize_phone(query.strip())))
        except ValueError:
            rows = rows.filter(account_id=int(query)) if query.isascii() and query.isdigit() and len(query)<12 else rows.none()
    total = rows.count()
    rows = rows.annotate(unread_count=Count('messages',filter=Q(messages__role='customer',messages__sequence__gt=F('staff_read_sequence'))))
    items = [{**thread_data(t,staff=True), 'unread_count':t.unread_count} for t in rows.order_by('-updated_at','-pk')[(page-1)*25:page*25]]
    return {'conversations':items, 'total':total, 'page':page, 'page_size':25, **staff_summary(actor), 'staff_online':presence(active=True)}


def send(actor, data, key, *, thread_id=None, staff=False):
    if staff:
        staff_required(actor)
    allowed = {'text', 'reply_to_sequence'} if staff else {'text'}
    if not isinstance(data,dict) or set(data) != allowed:
        raise APIError('invalid_input', 'فقط متن پیام را بفرست؛ ارسال فایل و تغییر فرستنده مجاز نیست.', 422)
    text, key = normalize_text(data.get('text')), client_key(key)
    text_hash = digest('support-text-v1:'+text)
    with transaction.atomic():
        if staff:
            thread = conversation_for_staff(actor,thread_id,lock=True)
        else:
            account = Account.objects.filter(user=actor).first()
            if not account:
                raise APIError('authentication_required','ابتدا شمارهٔ خودت را تأیید کن.',401)
            thread, _ = SupportConversation.objects.get_or_create(account=account)
            thread = SupportConversation.objects.select_for_update().get(pk=thread.pk)
        previous = thread.messages.filter(author=actor,client_key=key).first()
        if previous:
            if previous.text_digest != text_hash or previous.role != ('staff' if staff else 'customer'):
                raise APIError('idempotency_conflict','این کلید برای پیام دیگری ثبت شده است.',409)
            return {'thread':thread_data(thread), 'message':message_data(previous,actor)}
        if staff:
            reply_to = data.get('reply_to_sequence')
            if type(reply_to) is not int or reply_to<1 or not thread.messages.filter(sequence=reply_to,role='customer').exists():
                raise APIError('invalid_reply','پاسخ باید به یکی از پیام‌های کاربر در همین گفت‌وگو مربوط باشد.',422)
            limited('support-staff-send',str(actor.pk),30,60)
        else:
            limited('support-customer-send',str(actor.pk),10,60)
            limited('support-customer-day',str(actor.pk),100,86400)
        if thread.last_sequence >= 2147483646:
            raise APIError('support_capacity','این گفت‌وگو نیازمند بررسی پشتیبانی است.',409)
        thread.last_sequence += 1
        message = SupportMessage.objects.create(conversation=thread,author=actor,role='staff' if staff else 'customer',
            sequence=thread.last_sequence,client_key=key,text=text,text_digest=text_hash)
        if staff:
            thread.answered_customer_sequence = max(thread.answered_customer_sequence,reply_to)
            OperatorAudit.objects.create(actor=actor,action='support_reply',object_id=str(thread.pk),reason='پاسخ متنی پشتیبانی',
                after={'message_id':str(message.pk),'sequence':message.sequence,'reply_to_sequence':reply_to})
        else:
            thread.last_customer_sequence = message.sequence
        thread.status, thread.closed_at, thread.updated_at = 'open', None, timezone.now()
        thread.save()
        return {'thread':thread_data(thread),'message':message_data(message,actor)}


@transaction.atomic
def mark_read(actor, data, *, thread_id=None, staff=False):
    if not isinstance(data,dict) or set(data)!={'through_sequence'} or type(data.get('through_sequence')) is not int or data['through_sequence']<0:
        raise APIError('invalid_input','نشان خواندن پیام معتبر نیست.',422)
    if staff:
        thread = conversation_for_staff(actor,thread_id,lock=True)
    else:
        thread = SupportConversation.objects.select_for_update().filter(account__user=actor).first()
        if not thread:
            if data['through_sequence']==0:return {'ok':True}
            raise APIError('not_found','گفت‌وگو پیدا نشد.',404)
    if data['through_sequence']>thread.last_sequence:
        raise APIError('invalid_input','نمی‌توان پیام آینده را خوانده‌شده ثبت کرد.',422)
    field = 'staff_read_sequence' if staff else 'customer_read_sequence'
    if data['through_sequence']>getattr(thread,field):
        setattr(thread,field,data['through_sequence']);thread.save(update_fields=[field])
    return {'ok':True}


@transaction.atomic
def close(actor, identifier, data):
    if not isinstance(data,dict) or set(data)!={'last_sequence'} or type(data.get('last_sequence')) is not int:
        raise APIError('invalid_input','نسخهٔ گفت‌وگو معتبر نیست.',422)
    thread = conversation_for_staff(actor,identifier,lock=True)
    if data['last_sequence']!=thread.last_sequence:
        raise APIError('support_changed','پیام تازه‌ای رسیده؛ ابتدا گفت‌وگو را تازه‌سازی کن.',409)
    if thread.last_customer_sequence>thread.answered_customer_sequence:
        raise APIError('support_unanswered','پیش از بستن گفت‌وگو به پیام کاربر پاسخ بده.',409)
    if thread.status!='closed':
        thread.status,thread.closed_at = 'closed',timezone.now();thread.save(update_fields=['status','closed_at'])
        OperatorAudit.objects.create(actor=actor,action='support_close',object_id=str(thread.pk),reason='بستن گفت‌وگوی پاسخ‌داده‌شده')
    return {'thread':thread_data(thread)}
