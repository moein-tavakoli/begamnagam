"""Private, read-only product monitoring; no provider probes or alert refreshes."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Case, Count, Exists, F, IntegerField, Min, OuterRef, Q, Value, When
from django.db.models.functions import TruncHour
from django.utils import timezone
from django.views.decorators.vary import vary_on_cookie

from . import models as m
from .limits import daily_budget_limit, policy
from .monitoring_access import require_monitoring
from .packages import credit_environment
from .services import api


TEHRAN = ZoneInfo('Asia/Tehran')
ACTIVE_QUEUE = ('pending', 'submitting', 'unknown')


def _hourly_counts(rows):
    return {row['hour']: row['count'] for row in rows.order_by().annotate(
        hour=TruncHour('created_at', tzinfo=TEHRAN)).values('hour').annotate(count=Count('pk'))}


def _partition(rows, field):
    return [{'status': row[field], 'count': row['count']} for row in
            rows.order_by(field).values(field).annotate(count=Count('pk'))]


def _account_metrics(now, today_start):
    source = m.Account.SignupSource
    today = Q(created_at__gte=today_start, created_at__lt=now)
    environment = credit_environment()
    # Preserve recorded acceptance while reconciliation is inconclusive.
    sent_status = Q(status=m.Order.Status.DELIVERED_DEMO) if settings.DEMO_MODE else (
        Q(status__in=(m.Order.Status.ACCEPTED, m.Order.Status.DELIVERED)) |
        Q(status=m.Order.Status.UNKNOWN, delivery__accepted_at__isnull=False))
    sent = m.Order.objects.filter(sent_status, owner_id=OuterRef('user_id'),
                                  delivery__environment=environment, created_at__lt=now)
    sent_three_gifts = Exists(
        sent.filter(is_free=True, is_sponsored=False, free_credit_released_at__isnull=True)
        .order_by().values('owner_id').annotate(gift_count=Count('pk')).filter(gift_count__gte=3)
    )
    bought_package = Exists(m.CreditPurchase.objects.filter(
        owner_id=OuterRef('user_id'), environment=environment, credited_at__lt=now))
    counts = m.Account.objects.aggregate(
        accounts_today=Count('pk', filter=today),
        accounts_total=Count('pk'),
        bots_today=Count('pk', filter=today & Q(signup_source__in=(source.TELEGRAM, source.BALE))),
        api_today=Count('pk', filter=today & Q(signup_source=source.API)),
        telegram_total=Count('pk', filter=Q(signup_source=source.TELEGRAM)),
        bale_total=Count('pk', filter=Q(signup_source=source.BALE)),
        unknown_sources=Count('pk', filter=Q(signup_source=source.UNKNOWN)),
        without_successful_send=Count('pk', filter=~Exists(sent)),
        sent_three_gifts=Count('pk', filter=sent_three_gifts),
        sent_three_gifts_without_package=Count('pk', filter=sent_three_gifts & ~bought_package),
    )
    accounts_today = counts.pop('accounts_today')
    accounts_total = counts.pop('accounts_total')
    return accounts_today, accounts_total, counts


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
    accounts_today, accounts_total, activity = _account_metrics(now, end.replace(hour=0, minute=0, second=0, microsecond=0))
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
            'accounts_today': accounts_today,
            'accounts_total': accounts_total,
            'blacklist_total': m.RecipientState.objects.filter(blocked=True).count(),
            'requests': sum(requests.values()),
            # This is a delivery-creation cohort, not a resolution-time event count.
            'delivered': next((row['count'] for row in delivery if row['status'] == 'delivered'), 0),
            'support_unanswered': m.SupportConversation.objects.filter(
                last_customer_sequence__gt=F('answered_customer_sequence')).count(),
        },
        'account_activity': activity,
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
