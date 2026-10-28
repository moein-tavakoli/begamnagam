"""Local, aggregate release audit. This command never authorizes publication."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import F, Q
from django.utils.dateparse import parse_datetime

from core.models import FinancialEvent, PaymentAttempt, Refund, MessageDelivery, AbuseReport, SafetyControl


HUMAN_CHECKS = {
    'scope_freeze', 'persian_tone', 'android_standalone', 'ios_standalone',
    'mobile_accessibility', 'payment_return_devices', 'shared_device_privacy',
    'volunteer_consent', 'volunteer_pilot', 'support_drill', 'provider_acceptance',
    'post_settlement_refund', 'public_tls', 'offsite_restore', 'owner_release_decision',
}


def human_results(path=None):
    """Missing/empty/incomplete evidence cannot become approval by omission."""
    try:
        document = json.loads(Path(path).read_text()) if path else {}
        items = document.get('checks', [])
        indexed = {item['id']: item for item in items}
        if len(indexed) != len(items):
            raise ValueError('duplicate IDs')
    except (OSError, ValueError, KeyError, TypeError):
        indexed = {}
    results = {}
    for key in sorted(HUMAN_CHECKS):
        item = indexed.get(key, {})
        when = item.get('reviewed_at')
        try:
            dated = bool(isinstance(when, str) and parse_datetime(when))
        except (ValueError, TypeError):
            dated = False
        passed = (item.get('status') == 'PASS' and dated and
                  isinstance(item.get('reviewer'), str) and bool(item['reviewer'].strip()) and
                  isinstance(item.get('evidence'), str) and bool(item['evidence'].strip()))
        results[key] = 'RECORDED_PASS' if passed else 'PENDING'
    return results


def collect(path=None):
    executor = MigrationExecutor(connection)
    schema_ready = not executor.migration_plan(executor.loader.graph.leaf_nodes())
    from core.limits import policy, defaults
    limits = policy() if schema_ready else defaults()
    human = human_results(path)
    checks = {
        'postgresql': connection.vendor == 'postgresql',
        'migrations_applied': schema_ready,
        'non_demo': not settings.DEMO_MODE,
        'debug_disabled': not settings.DEBUG,
        'https_origin': urlparse(settings.APP_BASE_URL).scheme == 'https',
        'secure_cookies': settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE,
        'provider_network_external': settings.PROVIDER_NETWORK_MODE == 'external',
        'provider_credentials': all([settings.KAVENEGAR_API_KEY, settings.KAVENEGAR_SENDER, settings.KAVENEGAR_OTP_TEMPLATE, settings.ZARINPAL_MERCHANT_ID]),
        'provider_adapters_enabled': settings.LIVE_PROVIDERS_ENABLED and settings.SMS_BACKEND == 'kavenegar' and settings.OTP_BACKEND == 'kavenegar' and settings.PAYMENT_BACKEND == 'zarinpal',
        'provider_contract': settings.PROVIDER_CONTRACT_APPROVED,
        'refund_process': settings.REFUND_PROCESS_APPROVED,
        'operations_contact': bool(settings.OPERATIONS_OWNER and settings.SUPPORT_CONTACT),
        'bounded_pilot': bool(not limits.provider_budget_unlimited and settings.PILOT_RECIPIENT_HASHES and min(limits.provider_daily_budget_rial, limits.sms_max_cost_rial, limits.otp_max_cost_rial) > 0),
        'pilot_sending_window': settings.PILOT_POSITIVE_ONLY and limits.sending_window_enabled,
        'reviewed_terms': bool(settings.TERMS_VERSION.strip()) and not settings.TERMS_VERSION.startswith('draft') and all(os.getenv(k, '').lower() in {'true', 'yes', '1'} for k in ['TERMS_APPROVED', 'PRIVACY_POLICY_APPROVED']),
    }
    aggregates = {}
    if schema_ready:
        aggregates = {
            'financial_invariant_failures': FinancialEvent.objects.filter(
                ~Q(amount_toman=F('payment__amount_toman')) |
                (Q(kind='refund') & (~Q(refund__status='refunded') | ~Q(amount_toman=F('refund__amount_toman'))))).count(),
            'payments_unresolved': PaymentAttempt.objects.filter(status='unknown').count(),
            'deliveries_unresolved': MessageDelivery.objects.filter(status__in=['unknown', 'submitting']).count(),
            'refunds_open': Refund.objects.exclude(status='refunded').count(),
            'reports_open': AbuseReport.objects.filter(status='open').count(),
        }
        checks['financial_consistency'] = aggregates['financial_invariant_failures'] == 0
        checks['operational_cases_resolved'] = not any(aggregates[k] for k in aggregates if k != 'financial_invariant_failures')
        checks['dispatch_halted_for_review'] = SafetyControl.objects.filter(pk=1, halted=True).exists()
        role_names = ['support_observer', 'finance_observer', 'content_support', 'finance_operator', 'safety_operator']
        checks['roles_exist'] = Group.objects.filter(name__in=role_names).count() == len(role_names)
        checks['named_operators_assigned'] = all(Group.objects.filter(name=name, user__is_active=True, user__is_staff=True).exists() for name in ['content_support', 'finance_operator', 'safety_operator'])
    blockers = sorted([key for key, passed in checks.items() if not passed] + ['human:' + key for key, status in human.items() if status != 'RECORDED_PASS'])
    return {'kind': 'release_audit_no_publication', 'checks': checks, 'aggregates': aggregates,
            'human_evidence': human, 'live_ready': not blockers, 'blockers': blockers,
            'automatic_checks_verify_human_identity': False, 'publication_authorized': False}


class Command(BaseCommand):
    help = 'Aggregate release blockers, without printing secrets or approving a launch.'

    def add_arguments(self, parser):
        parser.add_argument('--human-checks')
        parser.add_argument('--require-live-ready', action='store_true')

    def handle(self, *args, **options):
        result = collect(options.get('human_checks'))
        self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
        if options['require_live_ready'] and not result['live_ready']:
            raise CommandError('Release remains blocked; see aggregate report above')
