"""Runtime switches cannot replace server-owned provider activation controls."""
import uuid
from django.conf import settings

WALLET_TERMS_VERSION = 'wallet-credit-v1'


def gateway_problem():
    if not settings.ZARINPAL_MERCHANT_ID:
        return 'مرچنت زرین‌پال در env خصوصی تنظیم نشده است.'
    try:
        uuid.UUID(settings.ZARINPAL_MERCHANT_ID)
    except (ValueError, TypeError, AttributeError):
        return 'شناسهٔ مرچنت زرین‌پال معتبر نیست.'
    if (settings.DEMO_MODE or settings.PAYMENT_BACKEND != 'zarinpal'
            or settings.PROVIDER_NETWORK_MODE != 'external' or not settings.LIVE_PROVIDERS_ENABLED
            or settings.PROVIDER_ENVIRONMENT != 'live'):
        return 'پروفایل پرداخت واقعی سرور هنوز آماده نشده است.'
    if (settings.ZARINPAL_BASE_URL not in {'https://payment.zarinpal.com', 'https://api.zarinpal.com'}
            or settings.ZARINPAL_REDIRECT_BASE != 'https://www.zarinpal.com'):
        return 'نشانی درگاه واقعی معتبر نیست.'
    if not all([settings.OPERATIONS_OWNER, settings.PROVIDER_CONTRACT_APPROVED,
                settings.REFUND_PROCESS_APPROVED, settings.SUPPORT_CONTACT,
                settings.PILOT_RECIPIENT_HASHES, settings.SMS_RECIPIENT_POLICY == 'pilot',
                getattr(settings, 'PROVIDER_DAILY_BUDGET_RIAL', 0) > 0,
                not settings.PROVIDER_DAILY_BUDGET_UNLIMITED]):
        return 'تنظیمات انتشار پرداخت و بودجهٔ مجاز روی سرور کامل نیست.'
    return ''


def options():
    from .limits import policy
    current = policy()
    problem = gateway_problem()
    return {'wallet_enabled': current.wallet_enabled,
        'gateway_enabled': current.gateway_enabled and not problem,
        'gateway_configured': not problem, 'wallet_terms_version': WALLET_TERMS_VERSION}
