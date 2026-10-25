import base64
import hashlib
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from cryptography.fernet import Fernet
from config.origins import local_otp_origin_allowed
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def flag(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes"}


TESTING = flag("DJANGO_TESTING")
DEBUG = flag("DEBUG", True)
DEMO_MODE = flag("DEMO_MODE", True)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-demo-only-change-this-secret-before-deployment")
PHONE_HASH_KEY = os.getenv("PHONE_HASH_KEY", "local-demo-phone-hash-only")
PHONE_ENCRYPTION_KEY = os.getenv("PHONE_ENCRYPTION_KEY") or base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()).decode()
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,backend,testserver").split(",")
CSRF_TRUSTED_ORIGINS = [x for x in os.getenv("CSRF_TRUSTED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if x]
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000").rstrip("/")
INTERNAL_DEMO_HOST = os.getenv("INTERNAL_DEMO_HOST", "")
PUBLIC_DEMO_HOST = os.getenv("PUBLIC_DEMO_HOST", "")
TRUST_DOMAIN_PROXY = flag("TRUST_DOMAIN_PROXY")


PRICE_TOMAN = int(os.getenv("PRICE_TOMAN", "2000"))
SENDER_DAILY_LIMIT = int(os.getenv("SENDER_DAILY_LIMIT", "5"))
RECIPIENT_COOLDOWN_HOURS = int(os.getenv("RECIPIENT_COOLDOWN_HOURS", "24"))
SENDER_RECIPIENT_COOLDOWN_HOURS = int(os.getenv("SENDER_RECIPIENT_COOLDOWN_HOURS", "24"))
DEMO_TEST_TOOLS_ENABLED = flag("DEMO_TEST_TOOLS_ENABLED")
if min(SENDER_DAILY_LIMIT, RECIPIENT_COOLDOWN_HOURS, SENDER_RECIPIENT_COOLDOWN_HOURS) < 1:
    raise ImproperlyConfigured("Sending limits must be positive")
AI_MODE = os.getenv("AI_MODE", "template")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
if not OLLAMA_URL.endswith("/api/generate"):
    OLLAMA_URL += "/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
SMS_BACKEND = os.getenv("SMS_BACKEND", "console")
PAYMENT_BACKEND = os.getenv("PAYMENT_BACKEND", "demo")

if SMS_BACKEND not in {"console", "disabled", "kavenegar"} or PAYMENT_BACKEND not in {"demo", "disabled", "zarinpal"}:
    raise ImproperlyConfigured("Unknown provider backend")

if AI_MODE not in {"template", "ollama"} or PRICE_TOMAN < 1:
    raise ImproperlyConfigured("Invalid AI_MODE or PRICE_TOMAN")
try:
    Fernet(PHONE_ENCRYPTION_KEY.encode())
except (ValueError, TypeError) as exc:
    raise ImproperlyConfigured("PHONE_ENCRYPTION_KEY must be a valid Fernet key") from exc
if not DEMO_MODE:
    if DEBUG or len(SECRET_KEY) < 50 or SECRET_KEY.startswith("local-demo"):
        raise ImproperlyConfigured("Non-demo requires DEBUG=false and a strong DJANGO_SECRET_KEY")
    if not os.getenv("PHONE_ENCRYPTION_KEY") or len(PHONE_HASH_KEY) < 32:
        raise ImproperlyConfigured("Non-demo requires independent phone encryption and hashing keys")
    if (SMS_BACKEND != "disabled" or PAYMENT_BACKEND != "disabled") and not flag("LIVE_PROVIDERS_ENABLED"):
        raise ImproperlyConfigured("Provider activation requires LIVE_PROVIDERS_ENABLED")
    if "*" in ALLOWED_HOSTS or any(x.startswith("http:") for x in CSRF_TRUSTED_ORIGINS):
        raise ImproperlyConfigured("Non-demo requires explicit hosts and HTTPS CSRF origins")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "core",
]
MIDDLEWARE = [
    "core.middleware.PrivateResponses",
    "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    db = urlparse(DATABASE_URL)
    if db.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must use PostgreSQL")
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": unquote(db.path[1:]),
        "USER": unquote(db.username or ""), "PASSWORD": unquote(db.password or ""),
        "HOST": db.hostname, "PORT": db.port or 5432, "CONN_MAX_AGE": 60}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3", "OPTIONS": {"timeout": 20}}}
if not DEMO_MODE and not DATABASE_URL:
    raise ImproperlyConfigured("Non-demo requires PostgreSQL DATABASE_URL")

REDIS_URL = os.getenv("REDIS_URL", "")
if REDIS_URL:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL, "KEY_PREFIX": os.getenv("CACHE_KEY_PREFIX", "")}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "begamnagam"}}
if not DEMO_MODE and not REDIS_URL:
    raise ImproperlyConfigured("Non-demo requires REDIS_URL")

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "memory://")
CELERY_TASK_ALWAYS_EAGER = TESTING or flag("CELERY_TASK_ALWAYS_EAGER", not bool(os.getenv("CELERY_BROKER_URL")))
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "reconcile-providers": {"task": "core.tasks.reconcile_providers", "schedule": 30.0},
    "reconcile-outbox": {"task": "core.tasks.reconcile_outbox", "schedule": 30.0},
    "expire-unpaid": {"task": "core.tasks.expire_unpaid_orders", "schedule": 60.0},
    "prune-private-data": {"task": "core.tasks.prune_private_data", "schedule": 86400.0},
}

LANGUAGE_CODE = "fa-ir"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"}, {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"}, {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"}]
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEMO_MODE
CSRF_COOKIE_SECURE = not DEMO_MODE
SECURE_SSL_REDIRECT = not DEMO_MODE
SECURE_HSTS_SECONDS = 31536000 if not DEMO_MODE else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEMO_MODE
SECURE_HSTS_PRELOAD = not DEMO_MODE
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_FAILURE_VIEW = "core.views.csrf_failure"
DATA_UPLOAD_MAX_MEMORY_SIZE = 8192
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
LOGGING = {"version": 1, "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"}}

# RabbitMQ >=4.3 rejects transient non-exclusive event/control queues.
# These short-lived Celery queues belong to a single connection; task queues
# remain durable and persistent. Do not re-enable deprecated broker features.
CELERY_EVENT_QUEUE_EXCLUSIVE = True
CELERY_CONTROL_QUEUE_EXCLUSIVE = True
CELERY_TASK_DEFAULT_DELIVERY_MODE = "persistent"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# Provider network access is opt-in. Contract tests use loopback only.
PROVIDER_NETWORK_MODE = os.getenv('PROVIDER_NETWORK_MODE', 'disabled')
LIVE_PROVIDERS_ENABLED = flag('LIVE_PROVIDERS_ENABLED')
PROVIDER_TIMEOUT_SECONDS = float(os.getenv('PROVIDER_TIMEOUT_SECONDS', '8'))
KAVENEGAR_BASE_URL = os.getenv('KAVENEGAR_BASE_URL', 'https://api.kavenegar.com')
KAVENEGAR_API_KEY = os.getenv('KAVENEGAR_API_KEY', '')
KAVENEGAR_SENDER = os.getenv('KAVENEGAR_SENDER', '')
KAVENEGAR_OTP_MODE = os.getenv('KAVENEGAR_OTP_MODE', 'sms')
KAVENEGAR_OTP_TEMPLATE = os.getenv('KAVENEGAR_OTP_TEMPLATE', '')
ZARINPAL_BASE_URL = os.getenv('ZARINPAL_BASE_URL', 'https://sandbox.zarinpal.com')
ZARINPAL_REDIRECT_BASE = os.getenv('ZARINPAL_REDIRECT_BASE', 'https://sandbox.zarinpal.com')
ZARINPAL_MERCHANT_ID = os.getenv('ZARINPAL_MERCHANT_ID', '')
PROVIDER_ENVIRONMENT = os.getenv('PROVIDER_ENVIRONMENT', 'sandbox')
OTP_BACKEND = os.getenv('OTP_BACKEND', 'demo' if DEMO_MODE else 'disabled')
LOCAL_REAL_OTP_ENABLED = flag('LOCAL_REAL_OTP_ENABLED')
OTP_TEST_RECIPIENT_HASHES = set(filter(None, os.getenv('OTP_TEST_RECIPIENT_HASHES', '').split(',')))
PROVIDER_DAILY_BUDGET_RIAL = int(os.getenv('PROVIDER_DAILY_BUDGET_RIAL', '0'))
SMS_MAX_COST_RIAL = int(os.getenv('SMS_MAX_COST_RIAL', '0'))
OTP_MAX_COST_RIAL = int(os.getenv('OTP_MAX_COST_RIAL', '0'))
PILOT_RECIPIENT_HASHES = set(filter(None, os.getenv('PILOT_RECIPIENT_HASHES', '').split(',')))
OPERATIONS_OWNER = os.getenv('OPERATIONS_OWNER', '')
PROVIDER_CONTRACT_APPROVED = flag('PROVIDER_CONTRACT_APPROVED')
REFUND_PROCESS_APPROVED = flag('REFUND_PROCESS_APPROVED')
if PROVIDER_NETWORK_MODE not in {'disabled', 'local', 'external'} or PROVIDER_ENVIRONMENT not in {'sandbox', 'live'}:
    raise ImproperlyConfigured('Invalid provider mode or environment')
if not 0 < PROVIDER_TIMEOUT_SECONDS <= 15:
    raise ImproperlyConfigured('Provider timeout must be at most15 seconds')
if KAVENEGAR_OTP_MODE not in {'sms', 'lookup'}:
    raise ImproperlyConfigured('Kavenegar OTP mode must be sms or lookup')
if LOCAL_REAL_OTP_ENABLED:
    if (not DEMO_MODE or PROVIDER_NETWORK_MODE != 'disabled' or LIVE_PROVIDERS_ENABLED
            or OTP_BACKEND != 'kavenegar' or SMS_BACKEND != 'console' or PAYMENT_BACKEND != 'demo'):
        raise ImproperlyConfigured('Local real OTP requires demo payments/messages and disabled general provider network')
    if not local_otp_origin_allowed(APP_BASE_URL, INTERNAL_DEMO_HOST,
                                    PUBLIC_DEMO_HOST if TRUST_DOMAIN_PROXY else ""):
        raise ImproperlyConfigured('Real test OTP requires an explicitly authorized HTTPS demo origin')
    if KAVENEGAR_BASE_URL != 'https://api.kavenegar.com':
        raise ImproperlyConfigured('Local real OTP requires the official HTTPS Kavenegar endpoint')
    if not KAVENEGAR_API_KEY or not KAVENEGAR_SENDER or not OTP_TEST_RECIPIENT_HASHES:
        raise ImproperlyConfigured('Local real OTP requires credentials and an explicit hashed test allowlist')
    if any(len(value) != 64 or any(c not in '0123456789abcdef' for c in value) for value in OTP_TEST_RECIPIENT_HASHES):
        raise ImproperlyConfigured('Local real OTP allowlist must contain keyed phone hashes')
    if not 0 < OTP_MAX_COST_RIAL <= PROVIDER_DAILY_BUDGET_RIAL:
        raise ImproperlyConfigured('Local real OTP requires a positive per-code and daily budget')
    if KAVENEGAR_OTP_MODE == 'lookup' and not KAVENEGAR_OTP_TEMPLATE:
        raise ImproperlyConfigured('Kavenegar lookup OTP requires an approved template')
if PROVIDER_NETWORK_MODE == 'external':
    if DEMO_MODE or not LIVE_PROVIDERS_ENABLED or not OPERATIONS_OWNER or not PROVIDER_CONTRACT_APPROVED or not REFUND_PROCESS_APPROVED:
        raise ImproperlyConfigured('External providers require non-demo mode, operations/contract/refund approval')
    if not all([KAVENEGAR_API_KEY, KAVENEGAR_SENDER, ZARINPAL_MERCHANT_ID, PILOT_RECIPIENT_HASHES]):
        raise ImproperlyConfigured('External providers require credentials and an explicit pilot recipient allowlist')
    if OTP_BACKEND == 'kavenegar' and KAVENEGAR_OTP_MODE == 'lookup' and not KAVENEGAR_OTP_TEMPLATE:
        raise ImproperlyConfigured('Kavenegar lookup OTP requires an approved template')
    if min(PROVIDER_DAILY_BUDGET_RIAL, SMS_MAX_COST_RIAL, OTP_MAX_COST_RIAL) <= 0:
        raise ImproperlyConfigured('External providers require positive bounded cost configuration')

PHONE_ENCRYPTION_FALLBACK_KEYS = list(filter(None, os.getenv('PHONE_ENCRYPTION_FALLBACK_KEYS', '').split(',')))
SENDING_WINDOW_ENABLED = flag('SENDING_WINDOW_ENABLED', not DEMO_MODE)
SENDING_START_HOUR = int(os.getenv('SENDING_START_HOUR', '9'))
SENDING_END_HOUR = int(os.getenv('SENDING_END_HOUR', '21'))
PILOT_POSITIVE_ONLY = flag('PILOT_POSITIVE_ONLY', not DEMO_MODE)
SUPPORT_CONTACT = os.getenv('SUPPORT_CONTACT', '')
if not 0 <= SENDING_START_HOUR < SENDING_END_HOUR <= 24:
    raise ImproperlyConfigured('Invalid sending window')
for fallback_key in PHONE_ENCRYPTION_FALLBACK_KEYS:
    try:
        Fernet(fallback_key.encode())
    except (ValueError, TypeError):
        raise ImproperlyConfigured('Invalid fallback encryption key') from None

if PROVIDER_NETWORK_MODE == 'external' and (not SUPPORT_CONTACT or not flag('TERMS_APPROVED') or not flag('PRIVACY_POLICY_APPROVED')):
    raise ImproperlyConfigured('External activation requires support contact and reviewed terms/privacy policy')

CELERY_TASK_DEFAULT_QUEUE = os.getenv('CELERY_TASK_DEFAULT_QUEUE', 'celery')
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
BENCHMARK_RUN_ID = os.getenv('BENCHMARK_RUN_ID', '') if DEMO_MODE else ''

TERMS_VERSION = os.getenv('TERMS_VERSION', 'draft-2026-10')
if len(TERMS_VERSION) > 40 or (PROVIDER_NETWORK_MODE == 'external' and TERMS_VERSION.startswith('draft')):
    raise ImproperlyConfigured('External checkout requires a reviewed, published terms version')
if AI_MODE == 'ollama':
    model_endpoint = urlparse(OLLAMA_URL)
    if model_endpoint.hostname not in {'localhost', '127.0.0.1', '::1', 'host.docker.internal', 'ollama'} or model_endpoint.username or model_endpoint.password:
        raise ImproperlyConfigured('Only the reviewed local model endpoint is allowed')
