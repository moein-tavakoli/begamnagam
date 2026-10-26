"""Default private demo profile; live sending uses a separate explicit profile."""
from .trusted_proxy_settings import *  # noqa: F403

if not DEMO_MODE or PROVIDER_NETWORK_MODE != "disabled" or LIVE_PROVIDERS_ENABLED or SMS_BACKEND != "console" or PAYMENT_BACKEND != "demo":
    raise ImproperlyConfigured("Internal deployment keeps payments/messages simulated")
