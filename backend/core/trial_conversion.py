"""Live purchases linked at checkout to a verified sender's reviewed text trial."""
from datetime import timedelta

from django.db.models import Count, Exists, F, Min, OuterRef, Q, Subquery

from .models import CreditPurchase, FinancialEvent, MessageAttempt


def trial_report(now, *, since=None, until=None, days=7):
    attempts = MessageAttempt.objects.filter(trial_environment='live', status='accepted', created_at__lte=now)
    # Filter the cohort dates *after* finding each person's first measured trial.
    cohorts = attempts.values('owner_id').annotate(started=Min('created_at'))
    if since:
        cohorts = cohorts.filter(started__date__gte=since)
    if until:
        cohorts = cohorts.filter(started__date__lt=until)
    window = timedelta(days=days)
    mature = cohorts.filter(started__lte=now - window)
    total, eligible = cohorts.count(), mature.count()
    first_trial = attempts.filter(owner_id=OuterRef('owner_id')).order_by('created_at').values('created_at')[:1]
    purchases = CreditPurchase.objects.filter(from_measured_text_trial=True, environment='live',
        owner_id__in=mature.values('owner_id'), creditentry__kind='purchase', creditentry__environment='live',
        creditentry__units=F('message_count'), creditentry__account__user_id=F('owner_id'),
        credited_at__gte=F('created_at')).annotate(started=Subquery(first_trial), ends=F('started') + window
        ).filter(created_at__gte=F('started'), credited_at__lt=F('ends'))
    # A real wallet debit or a matching verified customer payment and capture.
    wallet = Q(payment_method='wallet', walletentry__kind='package_debit', walletentry__environment='live',
               walletentry__account__user_id=F('owner_id'), walletentry__amount_toman=F('amount_toman'))
    payment = Q(payment__environment='live', payment__status='verified', payment__amount_toman=F('amount_toman'),
                payment__events__kind='payment', payment__events__amount_toman=F('amount_toman'))
    customer = Q(payment_method='gateway', payment__provider='zarinpal') | Q(
        payment_method='card', payment__provider='manual', wallet_refund_consent=True)
    # Each purchase has at most one payment, and each payment at most one full refund.
    # A partial refund leaves positive paid value, and a later refund belongs to a later window.
    full_refund = FinancialEvent.objects.filter(payment__purchase_id=OuterRef('pk'), payment__environment='live',
        kind='refund', amount_toman__gte=OuterRef('amount_toman'), created_at__lt=OuterRef('ends'))
    paid = purchases.filter(wallet | (customer & payment)).filter(~Exists(full_refund))
    buyers = paid.aggregate(users=Count('owner_id', distinct=True))['users']
    return {'trial_senders': total, 'eligible_senders_with_full_window': eligible, 'awaiting_full_window': total - eligible,
            'confirmed_linked_buyers': buyers, 'linked_purchase_rate': round(buyers / eligible, 4) if eligible else None}
