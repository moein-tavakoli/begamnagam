"""Private, read-only product monitoring; no provider probes or alert refreshes."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Case, Count, F, IntegerField, Min, Value, When
from django.db.models.functions import TruncHour
from django.utils import timezone
from django.views.decorators.vary import vary_on_cookie

from . import models as m
from .limits import daily_budget_limit, policy
from .monitoring_access import require_monitoring
from .services import api


TEHRAN = ZoneInfo('Asia/Tehran')
ACTIVE_QUEUE = ('pending', 'submitting', 'unknown')


def _hourly_counts(rows):
    return {row['hour']: row['count'] for row in rows.order_by().annotate(
        hour=TruncHour('created_at', tzinfo=TEHRAN)).values('hour').annotate(count=Count('pk'))}


def _partition(rows, field):
    return [{'status': row[field], 'count': row['count']} for row in
            rows.order_by(field).values(field).annotate(count=Count('pk'))]


def _operations_snapshot(now):
    """Read-only equivalent of safety.snapshot, including its unsaved defaults.

    safety.snapshot calls halted(), which initializes SafetyControl. A reporting
    request must leave even an uninitialized database unchanged.
    """
    oldest_message = m.Outbox.objects.filter(state__in=ACTIVE_QUEUE).aggregate(value=Min('created_at'))['value']
    oldest_invitation = m.InvitationSend.objects.filter(status__in=ACTIVE_QUEUE).aggregate(value=Min('created_at'))['value']
    oldest = min(filter(None, (oldest_message, oldest_invitation)), default=None)
    budget = m.SpendBudget.objects.filter(day=timezone.localdate(now)).first()
    limits = policy()
    daily_limit = daily_budget_limit(budget) if budget else limits.provider_daily_budget_rial
    control = m.SafetyControl.objects.filter(pk=1).first()
    return {
        'sending_halted': control.halted if control else not settings.DEMO_MODE,
        'outbox_pending': m.Outbox.objects.filter(state='pending').count() + m.InvitationSend.objects.filter(status='pending').count(),
        'oldest_queue_seconds': max(0, int((now - oldest).total_seconds())) if oldest else 0,
        'payment_unknown': m.PaymentAttempt.objects.filter(status='unknown').count(),
        'delivery_unknown': m.MessageDelivery.objects.filter(status__in=['unknown', 'submitting']).count() +
                            m.InvitationSend.objects.filter(status__in=['unknown', 'submitting']).count(),
        'refund_open': m.Refund.objects.exclude(status='refunded').count(),
        'reports_open': m.AbuseReport.objects.filter(status='open').count(),
        'provider_budget_reserved_rial': budget.reserved_rial if budget else 0,
        'provider_budget_unlimited': limits.provider_budget_unlimited,
        'provider_budget_limit_rial': None if limits.provider_budget_unlimited else daily_limit,
    }


@vary_on_cookie
@api(['GET'])
def monitoring(request):
    require_monitoring(request)
    now = timezone.now()
    end = now.astimezone(TEHRAN)
    start = end.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23)
    window = {'created_at__gte': start, 'created_at__lt': now}
    accounts = _hourly_counts(m.Account.objects.filter(**window))
    requests = _hourly_counts(m.Order.objects.filter(**window))
    delivery = _partition(m.MessageDelivery.objects.filter(**window), 'status')
    moderation = _partition(m.ModerationAudit.objects.filter(**window), 'outcome')
    queue = [
        {'kind': kind, **row}
        for kind, rows, field in (
            ('messages', m.Outbox.objects.filter(state__in=ACTIVE_QUEUE), 'state'),
            ('invitations', m.InvitationSend.objects.filter(status__in=ACTIVE_QUEUE), 'status'),
        )
        for row in _partition(rows, field)
    ]
    alerts = m.OperationalAlert.objects.filter(active=True).annotate(
        priority=Case(When(severity='critical', then=Value(0)), When(severity='high', then=Value(1)),
                      When(severity='warning', then=Value(2)), default=Value(3), output_field=IntegerField())
    ).order_by('priority', '-updated_at', 'code').values('code', 'severity', 'count')[:5]
    return {
        'generated_at': now,
        'window': {'start': start.isoformat(), 'end': end.isoformat(), 'timezone': 'Asia/Tehran'},
        'totals': {
            'accounts_new': sum(accounts.values()),
            'accounts_today': m.Account.objects.filter(
                created_at__gte=end.replace(hour=0, minute=0, second=0, microsecond=0),
                created_at__lt=now).count(),
            'accounts_total': m.Account.objects.count(),
            'requests': sum(requests.values()),
            # This is a delivery-creation cohort, not a resolution-time event count.
            'delivered': next((row['count'] for row in delivery if row['status'] == 'delivered'), 0),
            'support_unanswered': m.SupportConversation.objects.filter(
                last_customer_sequence__gt=F('answered_customer_sequence')).count(),
        },
        'hourly': [
            {'at': hour.isoformat(), 'accounts': accounts.get(hour, 0), 'requests': requests.get(hour, 0)}
            for hour in (start + timedelta(hours=index) for index in range(24))
        ],
        'delivery': delivery,
        'moderation': moderation,
        'queue': queue,
        'operations': _operations_snapshot(now),
        'alerts': list(alerts),
        'environment': {
            'demo': settings.DEMO_MODE, 'sms': settings.SMS_BACKEND,
            'otp': settings.OTP_BACKEND, 'payment': settings.PAYMENT_BACKEND,
            'paid_enabled': not settings.DEMO_MODE and settings.PAYMENT_BACKEND == 'zarinpal',
        },
    }
