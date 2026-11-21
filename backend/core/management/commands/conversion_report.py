"""First-party, live-only purchase attribution for mature cohorts."""
import json
from datetime import date, timedelta
from decimal import Decimal
from itertools import batched

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Sum
from django.utils import timezone

from core.conversion_experiments import SURFACES
from core.models import ConversionExposure, CreditPurchase, FinancialEvent, MessageDelivery, Order, SpendReservation


def per_user(value, count):
    if not count or value is None:
        return None
    return float(round(Decimal(value) / count, 4))


def known_sms_costs(mature, window):
    """Sum reported charges on live order SMS, never substitute a reserved ceiling."""
    start = F('order__owner__account__conversionexposure__exposed_at')
    rows = MessageDelivery.objects.filter(environment='live', provider='kavenegar', attempts__gt=0,
        order__owner__account__conversionexposure__in=mature,
        order__paid_at__gte=start, order__paid_at__lt=start + window).values_list('submission_key', flat=True)
    charged_rial, missing = 0, 0
    for group in batched(rows.iterator(), 250):
        keys = ['sms:' + str(key) for key in group]
        costs = SpendReservation.objects.filter(kind='sms', operation_key__in=keys,
            actual_rial__isnull=False).values_list('actual_rial', flat=True)
        charged_rial += sum(costs)
        missing += len(keys) - len(costs)
    return charged_rial, missing


def arm_report(exposures, key, window, now, variable_cost):
    mature = exposures.filter(exposed_at__lte=now - window)
    eligible = mature.count()
    start = F('owner__account__conversionexposure__exposed_at')
    # Customer-initiated sales only. Direct staff grants and old pending
    # purchases that settle after exposure do not represent web conversions.
    sales = CreditPurchase.objects.filter(environment='live', owner__account__conversionexposure__in=mature,
        created_at__gte=start, credited_at__gte=start, credited_at__lt=start + window
    ).exclude(payment_method='card', wallet_refund_consent=False)
    first_credited = {}
    gross = 0
    mix = {}
    for user_id, credited, amount, units in sales.order_by('credited_at', 'id').values_list(
            'owner_id', 'credited_at', 'amount_toman', 'message_count').iterator():
        gross += amount
        if user_id not in first_credited:
            first_credited[user_id] = credited
            offer = f'{units}/{amount}'
            mix[offer] = mix.get(offer, 0) + 1
    buyers = len(first_credited)
    refund_start = F('payment__purchase__owner__account__conversionexposure__exposed_at')
    refunds = FinancialEvent.objects.filter(kind='refund', payment__purchase__in=sales,
        payment__purchase__owner__account__conversionexposure__in=mature,
        created_at__gte=refund_start, created_at__lt=refund_start + window
    ).aggregate(total=Sum('amount_toman'))['total'] or 0
    known_rial, missing = known_sms_costs(mature, window)
    if variable_cost is not None and (variable_cost * 10 < known_rial or (not eligible and variable_cost)):
        raise CommandError('Reconcile all-in variable costs to the mature cohort and its known order SMS charges.')
    contribution = gross - refunds - variable_cost if variable_cost is not None else None
    totals = {
        'exposed_users': exposures.count(), 'eligible_users_with_full_window': eligible,
        'awaiting_full_window': exposures.filter(exposed_at__gt=now-window).count(),
        'first_buyers': buyers, 'first_purchase_rate': per_user(buyers, eligible), 'first_purchase_mix_units_per_toman': mix,
        'credited_package_revenue_toman': gross, 'recorded_refunds_toman': refunds,
        'known_order_sms_cost_rial': known_rial, 'attempted_order_sms_without_known_cost': missing,
        'all_in_variable_cost_toman': variable_cost, 'net_contribution_toman': contribution,
        'net_contribution_per_eligible_user_toman': per_user(contribution, eligible),
    }
    if key == 'preview':
        confirmations = Order.objects.filter(owner__account__conversionexposure__in=mature,
            preview_id=F('owner__account__conversionexposure__preview_id'), uses_purchased_credit=True,
            payment_mode='credit_live', paid_at__gte=start, paid_at__lt=start + window)
        confirmed = sum(user in first_credited and paid >= first_credited[user]
                        for user, paid in confirmations.values_list('owner_id', 'paid_at'))
        totals.update(same_preview_confirmed_after_first_purchase=confirmed,
            same_preview_confirmation_per_eligible=per_user(confirmed, eligible),
            same_preview_confirmation_per_first_buyer=per_user(confirmed, buyers))
    return totals


class Command(BaseCommand):
    help = 'Compare first live purchases and contribution per exposed eligible account. Output contains aggregates only.'

    def add_arguments(self, parser):
        parser.add_argument('experiment', choices=SURFACES)
        parser.add_argument('--since', type=date.fromisoformat, help='First enrollment date, inclusive, project time zone')
        parser.add_argument('--until', type=date.fromisoformat, help='End enrollment date, exclusive, project time zone')
        parser.add_argument('--window-days', type=int, default=7)
        for variant in ('control', 'treatment'):
            parser.add_argument(f'--{variant}-cost-toman', type=int,
                help='Reconciled all-in variable costs for this arm and mature follow-up windows, excluding refunds')

    def handle(self, *args, **options):
        key, days, since, until = (options[x] for x in ('experiment', 'window_days', 'since', 'until'))
        if days < 1 or days > 365 or (since and until and since >= until):
            raise CommandError('Use an increasing date interval and a window of 1–365 days.')
        now = timezone.now()
        exposures = ConversionExposure.objects.filter(environment='live', experiment=key)
        if since:
            exposures = exposures.filter(exposed_at__date__gte=since)
        if until:
            exposures = exposures.filter(exposed_at__date__lt=until)
        result = {'environment': 'live', 'experiment': key, 'window_days': days,
                  'as_of': now.isoformat(), 'since_inclusive': since, 'until_exclusive': until, 'arms': {}}
        for variant in ('control', 'treatment'):
            cost = options[variant + '_cost_toman']
            if cost is not None and cost < 0:
                raise CommandError('Variable costs must be nonnegative integer toman.')
            result['arms'][variant] = arm_report(exposures.filter(variant=variant), key, timedelta(days=days), now, cost)
        metrics = ['first_purchase_rate', 'net_contribution_per_eligible_user_toman']
        if key == 'preview':
            metrics.append('same_preview_confirmation_per_eligible')
        result['treatment_minus_control'] = {}
        for metric in metrics:
            control, treatment = (result['arms'][arm][metric] for arm in ('control', 'treatment'))
            result['treatment_minus_control'][metric] = (
                round(treatment - control, 4) if control is not None and treatment is not None else None)
        self.stdout.write(json.dumps(result, sort_keys=True, default=str))
