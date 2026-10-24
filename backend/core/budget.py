from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import SpendBudget, SpendReservation
from .providers import ProviderDisabled


def reserve_cost(operation_key, kind, amount_rial):
    """Conservative gross ceiling: unknowns and successful calls both retain reserve.

    Retrying the same logical operation does not reserve twice. Refunds never
    reopen the gross provider budget. A shared locked day row serializes callers.
    """
    if type(amount_rial) is not int or amount_rial <= 0:
        raise ProviderDisabled('cost_ceiling_missing')
    with transaction.atomic():
        day = timezone.localdate()
        SpendBudget.objects.get_or_create(day=day, defaults={'limit_rial': settings.PROVIDER_DAILY_BUDGET_RIAL})
        budget = SpendBudget.objects.select_for_update().get(day=day)
        previous = SpendReservation.objects.filter(operation_key=operation_key).first()
        if previous:
            return previous
        limit = min(budget.limit_rial, settings.PROVIDER_DAILY_BUDGET_RIAL)
        if budget.reserved_rial + amount_rial > limit:
            raise ProviderDisabled('daily_budget_exhausted')
        budget.reserved_rial += amount_rial
        budget.save(update_fields=['reserved_rial'])
        return SpendReservation.objects.create(operation_key=operation_key, budget=budget, amount_rial=amount_rial, kind=kind)
