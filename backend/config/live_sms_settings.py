"""Explicitly authorized real gift SMS behind the existing trusted CT proxies."""
from .trusted_proxy_settings import *  # noqa: F403

if (DEMO_MODE or DEBUG or not LIVE_PROVIDERS_ENABLED or PROVIDER_NETWORK_MODE != "external"
        or PROVIDER_ENVIRONMENT != "live" or SMS_BACKEND != "kavenegar" or OTP_BACKEND != "kavenegar"
        or PAYMENT_BACKEND != "disabled" or LOCAL_REAL_OTP_ENABLED or DEMO_TEST_TOOLS_ENABLED
        or SMS_RECIPIENT_POLICY != "all" or not PUBLIC_DEMO_HOST):
    raise ImproperlyConfigured("Live gift SMS requires explicit real SMS/OTP, disabled payments and no demo tools")

# Only the apex domain has a public TLS certificate; do not advertise preload for
# unrelated subdomains while retaining HTTPS enforcement and secure cookies.
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
