"""Real product on loopback, with TLS on both native development listeners."""
from .settings import *  # noqa: F403

if (not flag("LOCAL_LIVE_PRODUCT_ENABLED") or DEMO_MODE or DEBUG
        or not LIVE_PROVIDERS_ENABLED or PROVIDER_NETWORK_MODE != "external"
        or PROVIDER_ENVIRONMENT != "live" or OTP_BACKEND != "kavenegar"
        or SMS_BACKEND != "kavenegar" or PAYMENT_BACKEND != "disabled"
        or LOCAL_REAL_OTP_ENABLED or DEMO_TEST_TOOLS_ENABLED or TESTING
        or SMS_RECIPIENT_POLICY != "all"):
    raise ImproperlyConfigured("Local product requires explicit real OTP/SMS and disabled payments")

if (APP_BASE_URL != "https://localhost:3000"
        or set(ALLOWED_HOSTS) != {"localhost", "127.0.0.1"}
        or set(CSRF_TRUSTED_ORIGINS) != {"https://localhost:3000"}
        or DATABASES["default"]["HOST"] != "127.0.0.1"
        or DATABASES["default"]["NAME"] != "begamnagam_local_product"
        or REDIS_URL != "redis://127.0.0.1:16389/8"
        or CACHES["default"].get("KEY_PREFIX") != "begamnagam-local-real-v1"
        or urlparse(CELERY_BROKER_URL).hostname != "127.0.0.1"
        or CELERY_TASK_DEFAULT_QUEUE != "begamnagam-local-real"
        or CELERY_TASK_ALWAYS_EAGER or TRUST_DOMAIN_PROXY):
    raise ImproperlyConfigured("Local product requires isolated loopback data, queue and HTTPS origin")

# Both listeners bind 127.0.0.1 and use TLS. Forwarded headers are not needed.
SESSION_COOKIE_NAME = "begamnagam_local_session"
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
