"""Staff-only JSON API for the Next console. No generic model write endpoint."""
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import CharField, Q
from django.db.models.functions import Cast
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from . import models as m
from .account_options import update_account_options
from .limit_defaults import REQUEST_LIMITS
from .limit_services import LIMIT_SECTIONS, editable_values, update_limits, validate_reason
from .limits import policy, request_limit
from .privacy import digest, normalize_phone
from .safety import operator_action, snapshot
from .services import APIError, api, limited
from .views import body, session_key


def staff_api(methods, permission=None):
    def decorate(view):
        @api(methods)
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise APIError("management_login_required", "برای مدیریت وارد شوید.", 401)
            if not request.user.is_active or not request.user.is_staff or (permission and not request.user.has_perm(permission)):
                raise APIError("forbidden", "مجوز دسترسی به این بخش را ندارید.", 403)
            try:
                return view(request, *args, **kwargs)
            except (ObjectDoesNotExist, ValidationError):
                raise APIError("not_found", "رکورد پیدا نشد.", 404) from None
        return wrapped
    return decorate


# Every exposed field is reviewed explicitly. Phones, message bodies, provider
# references, recipient hashes, credentials and idempotency keys are excluded.
RESOURCES = {
    'manual-payments': (m.ManualPayment, 'رسیدهای کارت‌به‌کارت', 'created_at', 'status', [
        ('id','شناسهٔ درخواست','id'), ('purchase_id','شناسهٔ خرید','id'),
        ('purchase__owner__account__id','حساب','id'), ('purchase__owner__account__phone_masked','موبایل','text'),
        ('purchase__package_name','بسته','text'), ('purchase__message_count','تعداد پیام','number'),
        ('purchase__amount_toman','مبلغ (تومان)','number'), ('purchase__environment','محیط','text'), ('status','وضعیت','status'),
        ('receipt_submitted_at','ثبت رسید','date'), ('reviewed_at','بررسی','date'), ('created_at','ثبت','date')]),
    'wallet-entries': (m.WalletEntry, 'گردش کیف پول', 'created_at', 'kind', [
        ('id', 'شناسه', 'id'), ('account_id', 'حساب', 'id'), ('kind', 'نوع', 'status'),
        ('amount_toman', 'مبلغ (تومان)', 'number'), ('balance_after_toman', 'مانده (تومان)', 'money'),
        ('environment', 'محیط', 'text'), ('created_at', 'ثبت', 'date')]),
    'wallet-topups': (m.WalletTopup, 'شارژهای کیف پول', 'created_at', None, [
        ('id', 'شناسه', 'id'), ('amount_toman', 'مبلغ (تومان)', 'number'),
        ('payment__status', 'وضعیت', 'status'), ('environment', 'محیط', 'text'),
        ('credited_at', 'افزودن به موجودی', 'date'), ('created_at', 'ثبت', 'date')]),
    'credit-purchases': (m.CreditPurchase, 'خرید بسته‌ها', 'created_at', None, [
        ('id', 'شناسه', 'id'), ('package_name', 'بسته', 'text'), ('message_count', 'تعداد پیام', 'number'),
        ('amount_toman', 'مبلغ (تومان)', 'number'), ('environment', 'محیط', 'text'), ('credited_at', 'اعطای اعتبار', 'date'), ('created_at', 'ثبت', 'date')]),
    'credit-entries': (m.CreditEntry, 'دفتر اعتبار پیام', 'created_at', 'kind', [
        ('id', 'شناسه', 'id'), ('account_id', 'حساب', 'id'), ('kind', 'نوع', 'status'), ('units', 'تعداد', 'number'),
        ('environment', 'محیط', 'text'), ('created_at', 'ثبت', 'date')]),
    "accounts": (m.Account, "حساب‌ها", "created_at", None, [
        ("id", "شناسه", "id"), ("phone_masked", "موبایل", "text"),
        ("wallet_balance_toman", "موجودی کیف پول", "money"),
        ('sender_daily_limit', 'سقف اختصاصی ارسال / ۲۴ ساعت', 'number'),
        ('rewrite_daily_limit', 'سقف اختصاصی بازنویسی / روز', 'number'),
        ("suspended", "تعلیق", "bool"), ("free_sends_remaining", "هدیهٔ باقی‌مانده", "number"),
        ("free_sends_earned_total", "جایزهٔ دعوت", "number"), ("purchased_sends_remaining", "اعتبار خریداری‌شده", "number"), ("direct_message_tone", "لحن صریح", "bool"),
        ("deletion_requested_at", "درخواست حذف", "date"), ("created_at", "عضویت", "date")]),
    "orders": (m.Order, "پیام‌ها و سفارش‌ها", "created_at", "status", [
        ("id", "شناسه", "id"), ("status", "وضعیت", "status"), ("category", "موضوع", "text"),
        ("amount_toman", "مبلغ (تومان)", "number"), ("is_free", "هدیه", "bool"),
        ("payment_mode", "روش پرداخت", "text"), ("created_at", "ثبت", "date")]),
    "invitations": (m.Invitation, "دعوت‌ها", "created_at", None, [
        ("id", "شناسه", "id"), ("phone_masked", "مخاطب", "text"),
        ("registered_at", "ثبت‌نام مخاطب", "date"), ("reward_awarded_at", "اعطای جایزه", "date"), ("created_at", "ثبت", "date")]),
    "invitation-sends": (m.InvitationSend, "ارسال دعوت", "created_at", "status", [
        ("id", "شناسه", "id"), ("ordinal", "نوبت", "number"), ("status", "وضعیت", "status"),
        ("provider", "سرویس", "text"), ("last_error_code", "علت اخیر", "text"), ("created_at", "ثبت", "date")]),
    "deliveries": (m.MessageDelivery, "تحویل پیامک", "created_at", "status", [
        ("id", "شناسه", "id"), ("order_id", "سفارش", "id"), ("status", "وضعیت", "status"),
        ("attempts", "تلاش", "number"), ("environment", "محیط", "text"), ("last_error_code", "علت اخیر", "text"), ("updated_at", "به‌روزرسانی", "date")]),
    "outbox": (m.Outbox, "صف ارسال", "created_at", "state", [
        ("id", "شناسه", "id"), ("order_id", "سفارش", "id"), ("state", "وضعیت", "status"),
        ("attempts", "تلاش", "number"), ("last_error_code", "علت اخیر", "text"), ("available_at", "نوبت بررسی", "date")]),
    "reports": (m.AbuseReport, "گزارش‌های کاربران", "created_at", "status", [
        ("id", "پرونده", "id"), ("reason", "موضوع گزارش", "text"), ("status", "وضعیت", "status"),
        ("created_at", "ثبت", "date"), ("hold_until", "نگهداری تا", "date"), ("closed_at", "بسته‌شدن", "date")]),
    "moderation": (m.ModerationAudit, "بررسی محتوا", "created_at", "outcome", [
        ("event_id", "شناسه", "id"), ("category", "موضوع", "text"), ("outcome", "نتیجه", "status"),
        ("reason_code", "علت", "text"), ("created_at", "ثبت", "date")]),
    "payments": (m.PaymentAttempt, "پرداخت‌ها", "created_at", "status", [
        ('purchase_id', 'خرید بسته', 'id'),
        ("id", "شناسه", "id"), ("order_id", "سفارش", "id"), ("status", "وضعیت", "status"),
        ("amount_toman", "مبلغ (تومان)", "number"), ("provider", "سرویس", "text"), ("environment", "محیط", "text"), ("created_at", "ثبت", "date")]),
    "refunds": (m.Refund, "بازپرداخت‌ها", "created_at", "status", [
        ("id", "شناسه", "id"), ("status", "وضعیت", "status"), ("amount_toman", "مبلغ (تومان)", "number"),
        ("reason_code", "علت", "text"), ("created_at", "ثبت", "date")]),
    "financial-events": (m.FinancialEvent, "دفتر مالی", "created_at", "kind", [
        ("id", "شناسه", "id"), ("kind", "نوع", "status"), ("amount_toman", "مبلغ (تومان)", "number"), ("created_at", "ثبت", "date")]),
    "budgets": (m.SpendBudget, "هزینهٔ درگاه پیامک", "day", None, [
        ("day", "روز", "date"), ("reserved_rial", "هزینهٔ رزروشده (ریال)", "number"), ("limit_rial", "سقف ثبت‌شده (ریال)", "number")]),
    "alerts": (m.OperationalAlert, "هشدارهای عملیات", "updated_at", None, [
        ("id", "شناسه", "id"), ("code", "هشدار", "text"), ("severity", "شدت", "status"),
        ("active", "فعال", "bool"), ("count", "تعداد", "number"), ("acknowledged_by_id", "مدیر بررسی‌کننده", "id"), ("updated_at", "به‌روزرسانی", "date")]),
    "audit": (m.OperatorAudit, "سوابق مدیران", "created_at", None, [
        ("id", "شناسه", "id"), ("actor_id", "شناسهٔ مدیر", "id"), ("action", "اقدام", "text"),
        ("object_id", "رکورد", "text"), ("reason", "دلیل", "text"), ("before", "پیش از تغییر", "json"),
        ("after", "پس از تغییر", "json"), ("created_at", "ثبت", "date")]),
}


def resource_permission(spec):
    if spec[0] == m.ManualPayment:
        return 'core.approve_manual_payments'
    return "core.view_" + spec[0]._meta.model_name


def context(user):
    return {"authenticated": True, "session_identity": digest("staff-session-actor:"+str(user.pk)), "username": "مدیر" if hasattr(user, "account") else user.get_username(),
        "permissions": ["support_chat"] + [name for name in ("view_operations", "manage_site_limits", "manage_account_limits", "manage_manual_payments", "approve_manual_payments", "manage_ai", "manage_message_packages", "manage_message_examples", "view_private_message_text", "operate_safety", "suspend_account", "manage_message_tone", "triage_report", "confirm_refund") if user.has_perm("core." + name)],
        "resources": [{"key": key, "title": spec[1]} for key, spec in RESOURCES.items() if user.has_perm(resource_permission(spec))]}


@ensure_csrf_cookie
@api(["GET"])
def session(request):
    session_key(request)
    if request.user.is_authenticated and request.user.is_active and request.user.is_staff:
        return context(request.user)
    return {"authenticated": False}


@api(["POST"])
def login_view(request):
    data = body(request)
    limited("manage-login-ip", request.META.get("REMOTE_ADDR", "unknown"), 20, 600)
    limited("manage-login-session", session_key(request), 8, 600)
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not isinstance(password, str) or len(username) > 150 or len(password) > 512:
        raise APIError("invalid_credentials", "نام کاربری یا رمز عبور معتبر نیست.", 401)
    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_staff or not user.is_active:
        raise APIError("invalid_credentials", "نام کاربری یا رمز عبور معتبر نیست.", 401)
    login(request, user)
    return context(user)


@staff_api(["POST"])
def logout_view(request):
    logout(request)
    return {"ok": True}


@staff_api(["GET"], "core.view_operations")
def dashboard(request):
    return {"operations": snapshot(), "totals": {
        "accounts": m.Account.objects.count(), "orders": m.Order.objects.count(),
        "invitations": m.Invitation.objects.count(), "registered_invitations": m.Invitation.objects.filter(registered_at__isnull=False).count(),
        "delivered": m.MessageDelivery.objects.filter(status="delivered").count(),
        "active_alerts": m.OperationalAlert.objects.filter(active=True).count()},
        "environment": {"demo": settings.DEMO_MODE, "sms": settings.SMS_BACKEND,
            "otp": settings.OTP_BACKEND, "payment": settings.PAYMENT_BACKEND,
            "paid_enabled": not settings.DEMO_MODE and settings.PAYMENT_BACKEND == "zarinpal"},
        "updated_at": timezone.now()}


@staff_api(["POST"])
def records(request, resource):
    spec = RESOURCES.get(resource)
    if not spec:
        raise APIError("not_found", "بخش پیدا نشد.", 404)
    if not request.user.has_perm(resource_permission(spec)):
        raise APIError("forbidden", "مجوز مشاهدهٔ این بخش را ندارید.", 403)
    data = body(request)
    page, query, status = data.get("page", 1), data.get("query", ""), data.get("status", "")
    if type(page) is not int or not 1 <= page <= 100000 or not isinstance(query, str) or len(query) > 100 or not isinstance(status, str) or len(status) > 40:
        raise APIError("invalid_input", "فیلتر جست‌وجو معتبر نیست.", 422)
    model, title, ordering, status_field, columns = spec
    rows = model.objects.all()
    if status and status_field:
        rows = rows.filter(**{status_field: status})
    query = query.strip()
    if query:
        if resource in {"accounts", "invitations"}:
            try:
                rows = rows.filter(phone_hash=digest(normalize_phone(query)))
            except ValueError:
                rows = rows.annotate(search_id=Cast("pk", CharField())).filter(search_id=query)
        else:
            condition = Q(search_id__icontains=query)
            for field, _, kind in columns:
                if kind in {"status", "text"} and field not in {"reason", "object_id"}:
                    condition |= Q(**{field + "__icontains": query})
            rows = rows.annotate(search_id=Cast("pk", CharField())).filter(condition)
    total = rows.count()
    fields = list(dict.fromkeys([model._meta.pk.name] + [col[0] for col in columns]))
    values = list(rows.order_by("-" + ordering, "-pk").values(*fields)[(page-1)*25:page*25])
    for value in values:
        for money_field in ('balance_after_toman', 'wallet_balance_toman'):
            if money_field in value:
                value[money_field] = str(value[money_field])
        value["record_id"] = str(value[model._meta.pk.name])
    choices = []
    if status_field:
        field = model._meta.get_field(status_field)
        choices = list(field.flatchoices) if field.choices else [(v, v) for v in {
            "invitation-sends": ["pending", "submitting", "accepted", "delivered", "delivered_demo", "failed", "unknown", "suppressed", "expired", "cancelled"],
            "outbox": ["pending", "submitting", "sent", "failed", "cancelled", "unknown"],
            "reports": ["open", "closed"], "moderation": ["accepted", "rejected"]}.get(resource, [])]
    return {"title": title, "columns": [{"key": k, "label": label, "type": kind} for k, label, kind in columns],
        "rows": values, "total": total, "page": page, "page_size": 25, "statuses": choices}


def limits_payload():
    from .payment_options import gateway_problem
    current = policy()
    fields = []
    for title, names in LIMIT_SECTIONS:
        fields.append({"title": title, "fields": [{"key": name, "label": str(m.SiteLimits._meta.get_field(name).verbose_name),
            "help": str(m.SiteLimits._meta.get_field(name).help_text), "type": "bool" if isinstance(m.SiteLimits._meta.get_field(name), m.models.BooleanField) else "number",
            "min": 0, "max": None} for name in names]})
    rules = []
    for scope, (label, maximum, seconds, protected) in REQUEST_LIMITS.items():
        rule = request_limit(scope, maximum, seconds)
        rules.append({"scope": scope, "label": label, "protected": protected, "enabled": rule.enabled,
            "maximum": rule.maximum, "window_seconds": rule.window_seconds, "revision": rule.revision})
    return {"values": editable_values(current), "revision": current.revision, "sections": fields, "requests": rules,
        "gateway_problem": gateway_problem()}


@staff_api(["GET", "POST"], "core.manage_site_limits")
def limits(request):
    if request.method == "POST":
        data = body(request)
        update_limits(request.user, "site", data.get("values"), data.get("revision"), data.get("reason"))
    return limits_payload()


@staff_api(["POST"], "core.manage_site_limits")
def request_limits(request, scope):
    data = body(request)
    update_limits(request.user, "request", data.get("values"), data.get("revision"), data.get("reason"), scope=scope)
    return limits_payload()


@staff_api(["POST"])
def action(request):
    data = body(request)
    name, identifier = data.get("action"), data.get("object_id", "")
    if not isinstance(name, str) or not isinstance(identifier, str) or len(identifier) > 100:
        raise APIError("invalid_input", "اقدام معتبر نیست.", 422)
    if name == 'account_limits':
        values = data.get('values')
        if not isinstance(values, dict) or not values or set(values)-{'sender_daily_limit', 'rewrite_daily_limit'}:
            raise APIError('invalid_input', 'تنظیمات سقف حساب معتبر نیست.', 422)
        update_account_options(request.user, identifier, values, data.get('reason'))
    elif name == "tone":
        value = data.get("value")
        if type(value) is not bool:
            raise APIError("invalid_input", "مقدار لحن معتبر نیست.", 422)
        update_account_options(request.user, identifier, {"direct_message_tone": value}, data.get("reason"))
    else:
        operator_action(request.user, name, identifier, data.get("reason"), data.get("reference", ""))
    return {"ok": True}


@staff_api(["POST"], "core.view_abusereport")
def review_report(request, report_id):
    reason = validate_reason(body(request).get("reason"))
    report = m.AbuseReport.objects.select_related("grant__preview").get(pk=report_id)
    grant = report.grant
    if grant.preview_id:
        text = grant.preview.generated_body or grant.preview.text
    elif grant.invitation_send_id:
        from .invitations import INVITE_BODY
        text = INVITE_BODY
    else:
        text = "متن طبق سیاست نگهداری حذف شده است."
    m.OperatorAudit.objects.create(actor=request.user, action="report_viewed", object_id=str(report.pk), reason=reason)
    return {"id": str(report.pk), "details": report.details, "reviewed_text": text, "reason": report.reason, "status": report.status}


@staff_api(["POST"], "core.view_private_message_text")
def review_message(request, order_id):
    from .message_review import may_review_messages, message_texts, audit_review
    if not may_review_messages(request.user):
        raise APIError("forbidden", "مجوز مشاهدهٔ متن پیام را ندارید.", 403)
    reason = validate_reason(body(request).get("reason"))
    order = m.Order.objects.select_related("preview").get(pk=order_id)
    result = message_texts(order)
    audit_review(request.user, order, reason)
    return result
