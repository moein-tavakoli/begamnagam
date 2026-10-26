"""Shared HTTPS and exact trusted-proxy validation for the CT deployment."""
from .settings import *  # noqa: F403
import ipaddress

if not flag("TRUST_INTERNAL_PROXY") or DEBUG:
    raise ImproperlyConfigured("CT deployment requires an explicit trusted proxy and DEBUG=false")
if (not INTERNAL_DEMO_HOST or not local_otp_origin_allowed(
        "https://" + INTERNAL_DEMO_HOST, INTERNAL_DEMO_HOST)):
    raise ImproperlyConfigured("Internal deployment requires an explicit RFC1918 HTTPS origin")
if PUBLIC_DEMO_HOST:
    if (not TRUST_DOMAIN_PROXY or APP_BASE_URL != "https://" + PUBLIC_DEMO_HOST
            or not local_otp_origin_allowed(APP_BASE_URL, INTERNAL_DEMO_HOST, PUBLIC_DEMO_HOST)):
        raise ImproperlyConfigured("Domain demo requires an explicit HTTPS host and trusted edge proxy")
    try:
        edge = ipaddress.ip_address(os.getenv("CENTRAL_NGINX_IP", ""))
        if not any(edge in ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")):
            raise ValueError()
    except ValueError:
        raise ImproperlyConfigured("Domain demo requires the exact private Nginx address") from None
    if (PUBLIC_DEMO_HOST not in ALLOWED_HOSTS or INTERNAL_DEMO_HOST not in ALLOWED_HOSTS
            or any(not h or "*" in h or h.startswith(".") for h in ALLOWED_HOSTS)
            or APP_BASE_URL not in CSRF_TRUSTED_ORIGINS
            or any(not o.startswith("https://") or "*" in o for o in CSRF_TRUSTED_ORIGINS)):
        raise ImproperlyConfigured("Domain demo requires explicit hosts and HTTPS CSRF origins")
elif APP_BASE_URL != "https://" + INTERNAL_DEMO_HOST or TRUST_DOMAIN_PROXY:
    raise ImproperlyConfigured("Internal deployment requires its private HTTPS application origin")
if (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("local-demo")
        or len(PHONE_HASH_KEY) < 32 or not os.getenv("PHONE_ENCRYPTION_KEY")):
    raise ImproperlyConfigured("Internal deployment requires independent private secrets")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

# Only the local proxy may supply XFF. Walk from the nearest trusted hop.
TRUSTED_CLIENT_PROXY_IPS = {"127.0.0.1", "::1"}
if PUBLIC_DEMO_HOST:
    TRUSTED_CLIENT_PROXY_IPS.add(str(edge))
MIDDLEWARE = ["core.middleware.TrustedProxyClientIP", *MIDDLEWARE]
