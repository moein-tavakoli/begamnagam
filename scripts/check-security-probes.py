#!/usr/bin/env python3
"""Bounded unauthenticated web probes; no credentials, provider calls or user data.

Use only against an authorized deployment. Responses and cookies are never logged.
The only POST is an empty, cookieless preferences request that must fail CSRF.
This is a finite set of probes, not an exhaustive penetration test.
"""
import argparse
import ipaddress
import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def allowed_document_redirect(base_url, path, location):
    if path not in {'/api/v2/document/openapi.json', '/api/v2/document/client.py'}:
        return False
    origin = urllib.parse.urlsplit(base_url)
    destination = urllib.parse.urlsplit(urllib.parse.urljoin(base_url, location))
    return (destination.scheme == origin.scheme and destination.hostname == origin.hostname
            and (destination.port or 443) == (origin.port or 443)
            and not destination.username and not destination.password
            and destination.path == '/api/v2/document/login')


def image_refused_before_fetch(body):
    # A generic 400 can also mean that a fetched internal document is not an image.
    return body.strip() == b'"url" parameter is not allowed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--connect-ip', help='Optional owned edge IP; TLS still verifies the URL hostname')
    parser.add_argument('--output', required=True, help='Sanitized JSON evidence only')
    args = parser.parse_args()
    origin = urllib.parse.urlsplit(args.base_url)
    if (origin.scheme != 'https' or not origin.hostname or origin.username or origin.password
            or origin.path not in {'', '/'} or origin.query or origin.fragment):
        parser.error('Use an HTTPS origin without credentials, path, query or fragment')
    if args.connect_ip:
        ipaddress.ip_address(args.connect_ip)
        resolver = socket.getaddrinfo
        socket.getaddrinfo = lambda host, *a, **kw: resolver(
            args.connect_ip if host == origin.hostname else host, *a, **kw)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    cases = []
    zero = '00000000-0000-0000-0000-000000000000'

    def add(name, path, statuses, headers=None, method='GET', check=None):
        cases.append((name, path, set(statuses), headers or {}, method, check))

    for path in ['messages', 'orders/' + zero, 'wallet', 'preferences', 'invitations',
                 'support/messages', 'credit-purchases/' + zero]:
        add('anonymous_private_api', '/api/v1/' + path, [401])
    for path in ['me', 'messages', 'messages/' + zero, 'message-previews/' + zero,
                 'invitations', 'support/messages', 'wallet/entries']:
        add('anonymous_private_api_v2', '/api/v2/' + path, [401])
    for path in ['dashboard', 'users/2147483647', 'changelog',
                 'staff/employees', 'staff/roles', 'monitoring/settings', 'sms-template/kavenegar-key']:
        add('anonymous_staff_api', '/api/v1/manage/' + path, [401])
    add('records_get_method_rejected', '/api/v1/manage/records/orders', [405])
    for path in ['/.env', '/.env.internal', '/.git/config', '/backup.sql', '/db.sqlite3',
                 '/config/settings.py', '/_next/server/app/page.js', '/package-lock.json']:
        add('private_file', path, [403, 404])
    for path in ['/api/v2/document/openapi.json', '/api/v2/document/client.py']:
        add('private_document', path, [302, 303, 403, 404])
    for path in ['/api/v1/messages/..%2f..%2f.env', '/%2e%2e/%2e%2e/etc/passwd',
                 '/api/v1/messages%00', '/api/v1/messages%3fadmin=true', '/api/v1/messages%3b']:
        add('encoded_path_boundary', path, [400, 401, 403, 404])
    for path in ['/public/..;x/api/v1/manage/dashboard', '/public/..%3bx/api/v1/messages']:
        add('path_parameter_boundary', path, [400, 401, 403, 404])
    for header, value in [('X-Forwarded-For', '127.0.0.1'), ('X-Real-IP', '127.0.0.1'),
                          ('Forwarded', 'for=127.0.0.1;host=localhost;proto=https'),
                          ('X-Original-URL', '/api/v1/manage/dashboard'),
                          ('X-Rewrite-URL', '/api/v1/manage/dashboard'),
                          ('X-Middleware-Subrequest', 'middleware:middleware:middleware:middleware:middleware')]:
        add('forged_header_' + header.lower(), '/api/v1/messages', [401], {header: value})
    add('forged_monitoring_ip', '/api/v1/manage/monitoring', [401],
        {'X-Forwarded-For': '127.0.0.1', 'X-Real-IP': '127.0.0.1'})
    add('cross_origin_private_api', '/api/v1/messages', [401],
        {'Origin': 'https://audit.invalid'}, check='no_cors')
    add('csrf_missing_preferences', '/api/v1/preferences', [403],
        {'Origin': 'https://audit.invalid'}, method='POST')
    add('image_optimizer_loopback', '/_next/image?url=http%3A%2F%2F127.0.0.1%3A8000%2Fhealthz&w=64&q=75', [400], check='image_pre_fetch')
    add('image_optimizer_external', '/_next/image?url=https%3A%2F%2Faudit.invalid%2Fimage.png&w=64&q=75', [400], check='image_pre_fetch')
    add('untrusted_host', '/', [400, 403, 404, 421], {'Host': 'audit.invalid'})
    add('forged_forwarded_host', '/', [200], {'X-Forwarded-Host': 'audit.invalid'}, check='no_host_reflection')
    add('forged_nonce', '/', [200], {'X-Nonce': 'audit-controlled', 'Content-Security-Policy': "script-src * 'unsafe-inline'"}, check='no_nonce_reflection')

    results = []
    health = []
    halted = None
    def fetch(path, headers=None, method='GET'):
        time.sleep(1)
        request = urllib.request.Request(args.base_url.rstrip('/') + path,
            data=b'{}' if method == 'POST' else None, method=method,
            headers={'User-Agent': 'BegamNagam-Authorized-Security-Probes/1.0',
                     'Content-Type': 'application/json', **(headers or {})})
        started = time.monotonic()
        try:
            response = opener.open(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read(262144), round(time.monotonic() - started, 3)

    for index, (name, path, statuses, headers, method, check) in enumerate(cases):
        try:
            if index % 10 == 0:
                status, _, _, latency = fetch('/healthz')
                health.append({'status': status, 'seconds': latency})
                if status != 200 or latency > 5:
                    halted = 'health_guard'; break
            status, response_headers, body, latency = fetch(path, headers, method)
            passed = status in statuses
            if check == 'no_cors':
                passed &= not response_headers.get('Access-Control-Allow-Origin')
            elif check == 'no_host_reflection':
                passed &= b'audit.invalid' not in body and 'audit.invalid' not in response_headers.get('Location', '')
            elif check == 'no_nonce_reflection':
                csp = response_headers.get('Content-Security-Policy', '')
                passed &= "'nonce-" in csp and 'audit-controlled' not in csp and 'script-src *' not in csp
            elif check == 'image_pre_fetch':
                passed &= image_refused_before_fetch(body)
            location = response_headers.get('Location', '')
            if location:
                passed &= allowed_document_redirect(args.base_url, path, location)
            results.append({'probe': name, 'path': path, 'method': method, 'status': status,
                            'expected': sorted(statuses), 'passed': bool(passed), 'seconds': latency})
        except (OSError, urllib.error.URLError):
            halted = 'network_error'; break
    if not halted:
        try:
            status, _, _, latency = fetch('/healthz')
            health.append({'status': status, 'seconds': latency})
            if status != 200 or latency > 5:
                halted = 'health_guard'
        except (OSError, urllib.error.URLError):
            halted = 'network_error'
    evidence = {'target': args.base_url, 'connect_ip_override': args.connect_ip,
                'tls_verified': True, 'rate_limit_seconds': 1, 'cookies_sent': False,
                'response_bodies_stored': False, 'provider_calls_intended': False,
                'planned_probes': len(cases), 'completed_probes': len(results), 'halted': halted,
                'health': health, 'results': results}
    with open(args.output, 'w') as out:
        json.dump(evidence, out, indent=2)
    failures = [r for r in results if not r['passed']]
    print(json.dumps({'completed': len(results), 'planned': len(cases), 'halted': halted,
                      'failures': failures, 'health': health}, indent=2))
    return 1 if halted or failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
