"""Only behind the private, header-overwriting release proxy; never exposed directly."""
from .settings import *  # noqa: F403

if not flag('TRUST_RELEASE_PROXY') or DEMO_MODE or DEBUG:
    raise ImproperlyConfigured('Release settings require private trusted proxy, non-demo and DEBUG=false')
if urlparse(APP_BASE_URL).scheme != 'https':
    raise ImproperlyConfigured('Release settings require an HTTPS application origin')
if not TERMS_VERSION.strip() or TERMS_VERSION != TERMS_VERSION.strip():
    raise ImproperlyConfigured('Release settings require a nonempty, stable terms version')

# compose.release.yaml publishes only Caddy. It overwrites this header rather
# than trusting a client-supplied value. Never publish the backend port.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
