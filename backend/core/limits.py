"""Runtime policy: one request snapshot; workers read the committed policy afresh."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta
from django.conf import settings
from django.db.models.functions import Coalesce
from .limit_defaults import REQUEST_LIMITS

_snapshot = ContextVar("site_limits", default=None)


def fa_number(value):
    return str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


@contextmanager
def limit_scope():
    token = _snapshot.set({})
    try:
        yield
    finally:
        _snapshot.reset(token)


def defaults():
    from .models import SiteLimits
    return SiteLimits(price_toman=settings.PRICE_TOMAN, sender_limit=settings.SENDER_DAILY_LIMIT,
        recipient_cooldown_hours=settings.RECIPIENT_COOLDOWN_HOURS,
        pair_cooldown_hours=settings.SENDER_RECIPIENT_COOLDOWN_HOURS,
        sending_window_enabled=settings.SENDING_WINDOW_ENABLED,
        sending_start_hour=settings.SENDING_START_HOUR, sending_end_hour=settings.SENDING_END_HOUR,
        provider_budget_unlimited=settings.PROVIDER_DAILY_BUDGET_UNLIMITED,
        provider_daily_budget_rial=settings.PROVIDER_DAILY_BUDGET_RIAL,
        otp_max_cost_rial=settings.OTP_MAX_COST_RIAL, sms_max_cost_rial=settings.SMS_MAX_COST_RIAL,
        rewrite_daily_unlimited=settings.GAPGPT_DAILY_REQUEST_UNLIMITED,
        rewrite_daily_limit=settings.GAPGPT_DAILY_REQUEST_LIMIT, rewrite_user_limit=settings.GAPGPT_USER_DAILY_LIMIT)


def policy():
    from .models import SiteLimits
    snapshot = _snapshot.get()
    if snapshot is not None and "policy" in snapshot:
        return snapshot["policy"]
    value = SiteLimits.objects.filter(pk=1).first() or defaults()
    if not value._state.adding:
        value.clean()
    if snapshot is not None:
        snapshot["policy"] = value
    return value


def request_limit(scope, maximum=None, seconds=None):
    from .models import RequestLimit
    snapshot = _snapshot.get()
    if snapshot is None or "requests" not in snapshot:
        rows = {row.scope: row for row in RequestLimit.objects.all()}
        if snapshot is not None:
            snapshot["requests"] = rows
    else:
        rows = snapshot["requests"]
    if scope in rows:
        rows[scope].clean()
        return rows[scope]
    _, default_max, default_seconds, _ = REQUEST_LIMITS.get(scope, (scope, maximum, seconds, False))
    return RequestLimit(scope=scope, maximum=maximum or default_max, window_seconds=seconds or default_seconds)


def next_sending_time(now):
    value = policy()
    if not value.sending_window_enabled:
        return None
    start, end = value.sending_start_hour, value.sending_end_hour
    inside = start <= now.hour < end if start < end else now.hour >= start or now.hour < end
    if inside:
        return None
    next_at = now.replace(hour=start, minute=0, second=0, microsecond=0)
    return next_at if next_at > now else next_at + timedelta(days=1)


def recipient_next_allowed(state, now, *, sender=None, exclude_order=None, exclude_invitation_send=None):
    from .demo_limits import quota_start, unlimited_demo_sends
    from .models import InvitationSend, Order
    if unlimited_demo_sends(sender):
        return None
    value = policy()
    deadlines = []
    if value.recipient_cooldown_hours and state.last_sent_at and state.last_sent_at > quota_start(
            now, hours=value.recipient_cooldown_hours, recipient_hash=state.phone_hash):
        deadlines.append(state.last_sent_at + timedelta(hours=value.recipient_cooldown_hours))
    if value.recipient_limit and value.recipient_window_hours:
        window = timedelta(hours=value.recipient_window_hours)
        statuses = ["accepted", "delivered", "unknown"] + (["delivered_demo"] if settings.DEMO_MODE else [])
        orders = Order.objects.filter(recipient_hash=state.phone_hash, status__in=statuses).exclude(pk=exclude_order)
        times = list(orders.annotate(received_at=Coalesce("delivery__accepted_at", "updated_at")).filter(
            received_at__gt=now-window).values_list("received_at", flat=True))
        invites = InvitationSend.objects.filter(invitation__phone_hash=state.phone_hash,
            status__in=statuses).exclude(pk=exclude_invitation_send)
        times += list(invites.annotate(received_at=Coalesce("accepted_at", "submitted_at", "created_at")).filter(
            received_at__gt=now-window).values_list("received_at", flat=True))
        if len(times) >= value.recipient_limit:
            deadlines.append(sorted(times)[-value.recipient_limit] + window)
    return max(deadlines) if deadlines else None


def daily_budget_limit(budget):
    value = policy()
    return min(budget.limit_rial, value.provider_daily_budget_rial) if value._state.adding else value.provider_daily_budget_rial


def wake_policy_deferrals():
    from django.utils import timezone
    from .models import InvitationSend, Outbox
    reasons = ["outside_sending_window", "recipient_cooldown", "daily_budget_wait"]
    Outbox.objects.filter(state="pending", last_error_code__in=reasons).update(available_at=timezone.now())
    InvitationSend.objects.filter(status="pending", last_error_code__in=reasons).update(available_at=timezone.now())
