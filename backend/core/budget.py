from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import SafetyControl, SpendBudget, SpendReservation
from .providers import ProviderDisabled


def lock_dispatch_control():
    control, _ = SafetyControl.objects.select_for_update().get_or_create(
        pk=1, defaults={'halted': not settings.DEMO_MODE})
    return control


def reserve_cost(operation_key, kind, amount_rial):
    """Gross cost ledger: unknowns and successful calls both retain reserve.

    Retrying the same logical operation does not reserve twice. Refunds never
    reopen a bounded provider budget. An explicit live-gift flag bypasses only
    the aggregate daily ceiling; per-call ceilings and cost-overrun halts remain.
    A shared locked day row serializes callers in either mode.
    """
    from .models import OperationalAlert
    from .limits import policy, daily_budget_limit
    limits = policy()
    if OperationalAlert.objects.filter(code='provider_cost_exceeded', active=True).exists():
        raise ProviderDisabled('provider_cost_halt')
    if type(amount_rial) is not int or amount_rial <= 0:
        raise ProviderDisabled('cost_ceiling_missing')
    with transaction.atomic():
        day = timezone.localdate()
        SpendBudget.objects.get_or_create(day=day, defaults={'limit_rial': limits.provider_daily_budget_rial})
        budget = SpendBudget.objects.select_for_update().get(day=day)
        previous = SpendReservation.objects.filter(operation_key=operation_key).first()
        if previous:
            return previous
        limit = daily_budget_limit(budget)
        if not limits.provider_budget_unlimited and budget.reserved_rial + amount_rial > limit:
            raise ProviderDisabled('daily_budget_exhausted')
        budget.reserved_rial += amount_rial
        budget.save(update_fields=['reserved_rial'])
        return SpendReservation.objects.create(operation_key=operation_key, budget=budget, amount_rial=amount_rial, kind=kind)


def observe_cost(operation_key, cost_rial):
    from .models import OperatorAudit, OperationalAlert
    if type(cost_rial) is not int or cost_rial <= 0:
        return
    pending = SpendReservation.objects.filter(operation_key=operation_key, actual_rial__isnull=True)
    # The ledger already includes the reserve. Record ordinary charges once
    # without taking the day or dispatch locks.
    if pending.filter(amount_rial__gte=cost_rial).update(actual_rial=cost_rial, state='charged'):
        return
    meta = pending.values('budget_id').first()
    if not meta:
        return
    with transaction.atomic():
        # Live SMS submission may already hold this lock. Every overrun must
        # acquire it before locking the day budget.
        control = lock_dispatch_control()
        budget = SpendBudget.objects.select_for_update().get(pk=meta['budget_id'])
        reservation = SpendReservation.objects.select_for_update().get(operation_key=operation_key)
        if reservation.actual_rial is not None:
            return
        reservation.actual_rial = cost_rial
        reservation.state = 'charged'
        if cost_rial > reservation.amount_rial:
            budget.reserved_rial += cost_rial - reservation.amount_rial
            budget.save(update_fields=['reserved_rial'])
            reservation.amount_rial = cost_rial
            control.halted = True
            control.save(update_fields=['halted', 'updated_at'])
            OperationalAlert.objects.update_or_create(code='provider_cost_exceeded', defaults={'severity':'critical','active':True,'count':1})
            OperatorAudit.objects.create(action='automatic_cost_halt',object_id='global',reason='provider_cost_above_reserved_ceiling',after={'halted':True})
        reservation.save(update_fields=['actual_rial','state','amount_rial'])
