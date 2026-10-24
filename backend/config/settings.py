import base64
import hashlib
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from cryptography.fernet import Fernet
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
PRICE_TOMAN = int(os.getenv("PRICE_TOMAN", "2000"))
SENDER_DAILY_LIMIT = int(os.getenv("SENDER_DAILY_LIMIT", "3"))
RECIPIENT_COOLDOWN_HOURS = int(os.getenv("RECIPIENT_COOLDOWN_HOURS", "168"))
AI_MODE = os.getenv("AI_MODE", "template")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
if not OLLAMA_URL.endswith("/api/generate"):
    OLLAMA_URL += "/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
SMS_BACKEND = os.getenv("SMS_BACKEND", "console")
PAYMENT_BACKEND = os.getenv("PAYMENT_BACKEND", "demo")

if SMS_BACKEND not in {"console", "disabled"} or PAYMENT_BACKEND not in {"demo", "disabled"}:
    raise ImproperlyConfigured("Only local demo or disabled adapters are supported")

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
    if SMS_BACKEND != "disabled" or PAYMENT_BACKEND != "disabled":
        raise ImproperlyConfigured("Live SMS and payments are not implemented; select disabled adapters")
    if "*" in ALLOWED_HOSTS or any(x.startswith("http:") for x in CSRF_TRUSTED_ORIGINS):
        raise ImproperlyConfigured("Non-demo requires explicit hosts and HTTPS CSRF origins")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "core",
]
MIDDLEWARE = [
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
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
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
