import json
import urllib.error
import urllib.parse
import urllib.request
from django.conf import settings


class ProviderDisabled(RuntimeError):
    pass


class ProviderUnknown(RuntimeError):
    """A request may have been accepted. Never blindly repeat a mutation."""
    pass


class ProviderRejected(RuntimeError):
    """A documented, definite provider rejection; no raw response is exposed."""
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def endpoint(base, path, allowed_hosts):
    parsed = urllib.parse.urlparse(base)
    mode = settings.PROVIDER_NETWORK_MODE
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProviderDisabled('unsafe_endpoint')
    if mode == 'local':
        if not settings.DEMO_MODE or parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}:
            raise ProviderDisabled('local_contract_only')
    elif mode == 'external':
        if settings.DEMO_MODE or not settings.LIVE_PROVIDERS_ENABLED or parsed.scheme != 'https' or parsed.hostname not in allowed_hosts or parsed.port not in {None, 443}:
            raise ProviderDisabled('external_not_activated')
    else:
        raise ProviderDisabled('provider_network_disabled')
    return base.rstrip('/') + path


def post(base, path, payload, allowed_hosts, form=False):
    url = endpoint(base, path, allowed_hosts)
    body = urllib.parse.urlencode(payload).encode() if form else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json',
        'Accept': 'application/json',
    }, method='POST')
    try:
        opener = urllib.request.build_opener(NoRedirect())
        try:
            response = opener.open(request, timeout=settings.PROVIDER_TIMEOUT_SECONDS)
        except urllib.error.HTTPError as exc:
            if exc.code >= 500 or 300 <= exc.code < 400:
                exc.close()
                raise ProviderUnknown('http_uncertain') from None
            response = exc
        with response:
            data = response.read(32769)
            if len(data) > 32768:
                raise ProviderUnknown('oversized_response')
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ProviderUnknown('invalid_response')
            return result
    except (OSError, ValueError, TypeError) as exc:
        # HTTP errors include request URLs (Kavenegar embeds its key). Discard them.
        raise ProviderUnknown('transport_or_format') from None
