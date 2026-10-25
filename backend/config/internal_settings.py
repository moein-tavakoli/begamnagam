"""Private CT demo behind the sole HTTPS proxy; no public production activation."""
from .settings import *  # noqa: F403

if not flag("TRUST_INTERNAL_PROXY") or not DEMO_MODE or DEBUG:
    raise ImproperlyConfigured("Internal deployment requires a private proxy, demo mode and DEBUG=false")
if (not INTERNAL_DEMO_HOST or not local_otp_origin_allowed(APP_BASE_URL, INTERNAL_DEMO_HOST)
        or urlparse(APP_BASE_URL).scheme != "https"
        or urlparse(APP_BASE_URL).hostname != INTERNAL_DEMO_HOST):
    raise ImproperlyConfigured("Internal deployment requires an explicit RFC1918 HTTPS origin")
if (PROVIDER_NETWORK_MODE != "disabled" or LIVE_PROVIDERS_ENABLED
        or SMS_BACKEND != "console" or PAYMENT_BACKEND != "demo"):
    raise ImproperlyConfigured("Internal deployment keeps payments/messages simulated")
if (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("local-demo")
        or len(PHONE_HASH_KEY) < 32 or not os.getenv("PHONE_ENCRYPTION_KEY")):
    raise ImproperlyConfigured("Internal deployment requires independent private secrets")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
