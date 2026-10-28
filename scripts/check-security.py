#!/usr/bin/env python3
"""Read-only HTTP checks; never logs bodies, cookies, tokens or CSP nonces."""
import argparse
from html.parser import HTMLParser
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request


class Scripts(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.scripts = []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.scripts.append(dict(attrs))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:3101")
    parser.add_argument("--ca-file")
    parser.add_argument("--expect-hsts", action="store_true")
    parser.add_argument("--full-stack", action="store_true", help="Also require Django API/admin security headers")
    args = parser.parse_args()
    origin = urllib.parse.urlsplit(args.base_url)
    if (origin.scheme not in {"http", "https"} or not origin.hostname or origin.username or origin.password
            or origin.path not in {"", "/"} or origin.query or origin.fragment):
        parser.error("Expected an HTTP(S) origin without credentials, path or query")
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(
        context=ssl.create_default_context(cafile=args.ca_file)))
    failures, requests = [], 0

    def check(condition, path, rule):
        if not condition:
            failures.append({"path": path, "check": rule})

    def get(path, forged=False):
        nonlocal requests
        requests += 1
        headers = {"User-Agent": "BegamNagam-Security-Check/1.0"}
        if forged:
            headers.update({"X-Nonce": "attacker-controlled", "Content-Security-Policy": "script-src * 'unsafe-inline'"})
        request = urllib.request.Request(args.base_url.rstrip("/") + path, headers=headers)
        try:
            response = opener.open(request, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read().decode("utf-8", errors="replace")

    nonces = set()
    for path in ["/", "/", "/help", "/privacy", "/profile", "/history", "/invitations", "/preferences", "/r", "/manage", "/security-check-not-found"]:
        status, headers, body = get(path, forged=True)
        check(status == (404 if path == "/security-check-not-found" else 200), path, "page_status")
        csp = headers.get("Content-Security-Policy", "")
        match = re.search(r"script-src [^;]*'nonce-([A-Za-z0-9+/]{43}=)'", csp)
        nonce = match.group(1) if match else None
        check(bool(nonce), path, "fresh_script_nonce")
        check(nonce not in nonces, path, "no_nonce_reuse")
        if nonce:
            nonces.add(nonce)
        check("attacker-controlled" not in csp and "script-src *" not in csp, path, "reject_forged_policy")
        directives = dict(part.strip().split(" ", 1) if " " in part.strip() else (part.strip(), "") for part in csp.split(";") if part.strip())
        check("'unsafe-inline'" not in directives.get("script-src", "") and
              "'unsafe-eval'" not in directives.get("script-src", ""), path, "production_script_restrictions")
        for directive in ["frame-ancestors", "object-src", "base-uri"]:
            check(directives.get(directive) == "'none'", path, directive)
        scripts = Scripts(body).scripts
        check(bool(scripts) and all(script.get("nonce") == nonce for script in scripts), path, "scripts_match_policy")
        check("no-store" in headers.get("Cache-Control", ""), path, "private_html_cache")
        check(headers.get("X-Content-Type-Options") == "nosniff", path, "nosniff")
        check(headers.get("X-Frame-Options") == "DENY", path, "clickjacking")
        check(headers.get("Referrer-Policy") == "no-referrer", path, "private_referrer")
        if args.expect_hsts:
            check(headers.get("Strict-Transport-Security") == "max-age=31536000", path, "hsts")
    for path in ["/.env", "/.env.internal", "/.git/config", "/db.sqlite3", "/backup.sql", "/_next/server/app/page.js", "/frontend/package.json"]:
        status, _, _ = get(path)
        check(status in {403, 404}, path, "sensitive_file_not_public")
    status, headers, _ = get("/offline.html")
    check(status == 200 and "default-src 'none'" in headers.get("Content-Security-Policy", ""), "/offline.html", "offline_policy")
    check("noindex" in headers.get("X-Robots-Tag", ""), "/offline.html", "offline_noindex")
    if args.full_stack:
        for path, expected in [("/api/v1/messages", 401), ("/api/v1/operations/status", 403), ("/admin/login/", 200)]:
            status, headers, _ = get(path)
            check(status == expected, path, "authentication_boundary")
            check("script-src 'self'" in headers.get("Content-Security-Policy", ""), path, "django_policy")
            check("no-store" in headers.get("Cache-Control", ""), path, "private_response_cache")
            check(headers.get("Referrer-Policy") == ("same-origin" if path.startswith("/admin/") else "no-referrer"), path, "referrer_boundary")
    print(json.dumps({"result": "FAIL" if failures else "PASS", "requests": requests,
                      "read_only": True, "failures": failures}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
