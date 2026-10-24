"""Read-only local foundation probe. Never sends SMS or submits a payment."""
import json
import os
import struct
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, build_opener

origin = os.getenv('APP_BASE_URL', 'http://localhost:3000').rstrip('/')
url = urlparse(origin)
if url.scheme not in {'http', 'https'} or url.hostname not in {'localhost', '127.0.0.1', '::1'}:
    raise SystemExit('Foundation verification is restricted to loopback demo origins')

class LocalRedirectsOnly(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        target = urlparse(newurl)
        if (target.scheme, target.netloc) != (url.scheme, url.netloc):
            raise ValueError('Redirect outside the local origin is forbidden')
        return super().redirect_request(request, fp, code, message, headers, newurl)

opener = build_opener(LocalRedirectsOnly())

def read(path):
    with opener.open(origin + path, timeout=15) as response:
        if urlparse(response.url).hostname != url.hostname:
            raise SystemExit('Unexpected redirect')
        return response.read(), response.headers

raw, headers = read('/api/v1/bootstrap')
assert json.loads(raw)['demo_mode'] is True, 'Only demo environments may be probed'
assert 'no-store' in headers.get('Cache-Control', '')
manifest = json.loads(read('/manifest.webmanifest')[0])
assert manifest['id'] == '/' and manifest['dir'] == 'rtl' and manifest['display'] == 'standalone'
for icon in manifest['icons']:
    content, _ = read(icon['src'])
    assert content[:8] == b'\x89PNG\r\n\x1a\n'
    dimensions = struct.unpack('>II', content[16:24])
    assert f'{dimensions[0]}x{dimensions[1]}' == icon['sizes']
_, headers = read('/sw.js')
assert 'no-store' in headers.get('Cache-Control', '')
assert headers.get('Service-Worker-Allowed') == '/'
assert 'یه مکث کوچیک'.encode() in read('/offline.html')[0]
assert 'یه حرف خوب'.encode() in read('/')[0]
print('PASS: local demo, no-store API, manifest, PNG dimensions, worker headers, public offline fallback and new UI')
