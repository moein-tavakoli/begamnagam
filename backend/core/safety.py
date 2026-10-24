from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Min, Count
from django.utils import timezone
from .models import SafetyControl, OperatorAudit, OperationalAlert, Outbox, PaymentAttempt, MessageDelivery, Refund, AbuseReport, SpendBudget, Account, Order, FinancialEvent
from .services import APIError


def halted():
    value, _ = SafetyControl.objects.get_or_create(pk=1, defaults={'halted': not settings.DEMO_MODE})
    return value.halted


def ensure_open():
    if halted():
        raise APIError('sending_paused', 'ارسال فعلاً متوقف است؛ بعداً دوباره مراجعه کن.', 503)


def defer_until_open(event):
    if halted():
        event.available_at = timezone.now() + timedelta(seconds=30)
        event.save(update_fields=['available_at'])
        return True
    now = timezone.localtime()
    if settings.SENDING_WINDOW_ENABLED and not settings.SENDING_START_HOUR <= now.hour < settings.SENDING_END_HOUR:
        tomorrow = now + timedelta(days=1) if now.hour >= settings.SENDING_END_HOUR else now
        event.available_at = tomorrow.replace(hour=settings.SENDING_START_HOUR, minute=0, second=0, microsecond=0)
        event.save(update_fields=['available_at'])
        return True
    return False


def operator_action(actor, action, object_id, reason, reference=''):
    permissions = {'halt': 'operate_safety', 'resume': 'operate_safety', 'suspend': 'suspend_account', 'unsuspend': 'suspend_account', 'close_report': 'triage_report', 'hold_report': 'triage_report', 'confirm_refund': 'confirm_refund', 'ack_alert': 'view_operations'}
    permission = permissions.get(action)
    if not permission or not actor.is_active or not actor.is_staff or not actor.has_perm('core.' + permission):
        raise APIError('forbidden', 'مجوز این اقدام را ندارید.', 403)
    if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 200:
        raise APIError('reason_required', 'دلیل اقدام باید بین۳تا۲۰۰نویسه باشد.')
    with transaction.atomic():
        if action in {'halt', 'resume'}:
            SafetyControl.objects.get_or_create(pk=1, defaults={'halted': not settings.DEMO_MODE})
            obj = SafetyControl.objects.select_for_update().get(pk=1)
            before = {'halted': obj.halted}
            obj.halted = action == 'halt'
            if action == 'resume':
                budget = SpendBudget.objects.filter(day=timezone.localdate()).first()
                if budget and budget.reserved_rial >= min(budget.limit_rial, settings.PROVIDER_DAILY_BUDGET_RIAL):
                    raise APIError('budget_exhausted', 'بودجه مصرف شده؛ ازسرگیری ممکن نیست.', 409)
            obj.save()
            after = {'halted': obj.halted}
            object_id = 'global'
        elif action in {'suspend', 'unsuspend'}:
            obj = Account.objects.select_for_update().get(pk=object_id)
            before = {'suspended': obj.suspended}
            obj.suspended = action == 'suspend'
            obj.save(update_fields=['suspended'])
            after = {'suspended': obj.suspended}
        elif action in {'close_report', 'hold_report'}:
            obj = AbuseReport.objects.select_for_update().get(pk=object_id)
            before = {'status': obj.status}
            if action == 'hold_report':
                obj.hold_until = timezone.now() + timedelta(days=30)
            else:
                obj.status = 'closed'
                obj.closed_at = timezone.now()
            obj.save(update_fields=['status', 'closed_at', 'hold_until'])
            after = {'status': obj.status, 'hold_until': obj.hold_until.isoformat() if obj.hold_until else None}
        elif action == 'confirm_refund':
            if not isinstance(reference, str) or not 3 <= len(reference) <= 100:
                raise APIError('reference_required', 'مرجع مستند بازپرداخت لازم است.')
            meta = Refund.objects.get(pk=object_id)
            Order.objects.select_for_update().get(pk=meta.payment.order_id)
            payment = PaymentAttempt.objects.select_for_update().get(pk=meta.payment_id)
            obj = Refund.objects.select_for_update().get(pk=object_id)
            before = {'status': obj.status}
            if payment.status != 'verified' or obj.amount_toman != payment.amount_toman:
                raise APIError('refund_conflict', 'مبلغ یا وضعیت نیازمند تطبیق است.', 409)
            if obj.status != 'refunded':
                obj.status = 'refunded'
                obj.provider_reference = 'manual:' + reference
                obj.save(update_fields=['status', 'provider_reference', 'updated_at'])
                FinancialEvent.objects.get_or_create(refund=obj, defaults={'payment': payment, 'kind': 'refund', 'amount_toman': obj.amount_toman})
            after = {'status': obj.status}
        else:
            obj = OperationalAlert.objects.select_for_update().get(pk=object_id)
            before = {'acknowledged': obj.acknowledged_by_id is not None}
            obj.acknowledged_by = actor
            obj.save(update_fields=['acknowledged_by'])
            after = {'acknowledged': True}
        OperatorAudit.objects.create(actor=actor, action=action, object_id=str(object_id), reason=reason.strip(), before=before, after=after)
    return after


def snapshot():
    now = timezone.now()
    oldest = Outbox.objects.filter(state__in=['pending', 'submitting', 'unknown']).aggregate(value=Min('created_at'))['value']
    budget = SpendBudget.objects.filter(day=timezone.localdate()).first()
    return {'sending_halted': halted(), 'outbox_pending': Outbox.objects.filter(state='pending').count(),
        'oldest_queue_seconds': max(0, int((now-oldest).total_seconds())) if oldest else 0,
        'payment_unknown': PaymentAttempt.objects.filter(status='unknown').count(),
        'delivery_unknown': MessageDelivery.objects.filter(status__in=['unknown', 'submitting']).count(),
        'refund_open': Refund.objects.exclude(status='refunded').count(), 'reports_open': AbuseReport.objects.filter(status='open').count(),
        'provider_budget_reserved_rial': budget.reserved_rial if budget else 0,
        'provider_budget_limit_rial': min(budget.limit_rial, settings.PROVIDER_DAILY_BUDGET_RIAL) if budget else settings.PROVIDER_DAILY_BUDGET_RIAL}


def refresh_alerts():
    data = snapshot()
    limits = {'queue_age': data['oldest_queue_seconds'] if data['oldest_queue_seconds'] > 120 else 0,
        'payment_unknown': data['payment_unknown'], 'delivery_unknown': data['delivery_unknown'],
        'refund_open': data['refund_open'], 'reports_open': data['reports_open'],
        'budget_80_percent': int(data['provider_budget_limit_rial'] > 0 and data['provider_budget_reserved_rial']*100 >= data['provider_budget_limit_rial']*80)}
    for code, count in limits.items():
        OperationalAlert.objects.update_or_create(code=code, defaults={'active': bool(count), 'count': count, 'severity': 'high' if code in {'refund_open', 'payment_unknown', 'delivery_unknown'} else 'warning'})
    return data
