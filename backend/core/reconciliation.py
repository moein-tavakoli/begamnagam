from django.db.models import Q
from django.db.models.functions import Coalesce


def due_reconciliation_ids(records, *, now, cooldown):
    """Select a bounded batch in order of time waiting for the next check."""
    return (records
        .filter(Q(lease_until__isnull=True) | Q(lease_until__lte=now))
        .filter(Q(checked_at__isnull=True) | Q(checked_at__lte=now - cooldown))
        .order_by(Coalesce('checked_at', 'created_at'), 'pk')
        .values_list('pk', flat=True)[:100])
