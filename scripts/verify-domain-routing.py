#!/usr/bin/env python3
"""Probe the deployed HTTPS app without SMS or payment; keep TLS/CSRF checks on."""
import argparse
import http.cookiejar
import ipaddress
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "script" and values.get("src"):
            self.urls.add(values["src"])
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.urls.add(values["href"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://begamnagam.ir")
    parser.add_argument("--connect-ip", help="Reach the edge directly while preserving HTTPS hostname verification")
    parser.add_argument("--ca-file", help="Optional trusted CA bundle; certificate verification stays enabled")
    parser.add_argument("--admin-credentials", help="Optional private JSON with username/password; never logged")
    parser.add_argument("--product-session", help="Optional private JSON containing a synthetic diagnostic session")
    parser.add_argument("--expect-live-gifts", action="store_true", help="Expect real SMS/OTP and disabled paid checkout")
    parser.add_argument("--expect-plain-recipient-links", action="store_true", help="Check plain alphanumeric SMS links without using a real recipient code")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    origin = args.base_url.rstrip("/")
    parsed = urllib.parse.urlparse(origin)
    assert parsed.scheme == "https" and parsed.hostname and parsed.path in {"", "/"}
    assert not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
    if args.connect_ip:
        address = str(ipaddress.ip_address(args.connect_ip))
        original_resolver = socket.getaddrinfo

        def resolver(host, port, *rest, **kwargs):
            return original_resolver(address if host == parsed.hostname else host, port, *rest, **kwargs)

        socket.getaddrinfo = resolver
    context = ssl.create_default_context(cafile=args.ca_file)
    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
        urllib.request.HTTPSHandler(context=context), urllib.request.HTTPCookieProcessor(cookies))
    results = {"origin": origin, "connect_ip": args.connect_ip, "tls_verification": True, "routes": [], "checks": {}}

    def request(path, expected=200, data=None, headers=None):
        req = urllib.request.Request(origin + path, data=data, headers=headers or {})
        try:
            response = opener.open(req, timeout=15)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            body = response.read()
            results["routes"].append({"path": path, "method": req.get_method(), "status": response.code, "bytes": len(body)})
            assert response.code == expected, (path, response.code, expected)
            assert not response.headers.get("Location", "").startswith("http://"), path
            return body, response.headers

    body, _ = request("/")
    html = body.decode()
    assert len(body) > 1024 and 'lang="fa"' in html and "بگم" in html
    assets = Assets()
    assets.feed(html)
    assert any(".js" in url for url in assets.urls) and any(".css" in url for url in assets.urls)
    for asset in sorted(assets.urls):
        absolute = urllib.parse.urljoin(origin, asset)
        url = urllib.parse.urlparse(absolute)
        assert url.scheme == "https" and url.netloc == parsed.netloc, asset
        request(url.path + ("?" + url.query if url.query else ""))
    results["checks"]["html_and_assets"] = True
    if args.expect_plain_recipient_links:
        body, link_headers = request("/r/Ab12Cd34", 307)
        assert not body and link_headers.get("Location") == "/r#Ab12Cd34"
        for path, status in [("/r/too-short", 404), ("/r", 200)]:
            _, private_headers = request(path, status)
            assert "no-store" in private_headers.get("Cache-Control", "")
            assert private_headers.get("Referrer-Policy") == "no-referrer"
            assert "noindex" in private_headers.get("X-Robots-Tag", "")
        assert "no-store" in link_headers.get("Cache-Control", "")
        assert link_headers.get("Referrer-Policy") == "no-referrer"
        assert "noindex" in link_headers.get("X-Robots-Tag", "")
        results["checks"]["plain_recipient_link_redirect_and_privacy"] = True
    for path in ["/history", "/preferences", "/help"]:
        page, page_headers = request(path)
        assert len(page) > 1024 and 'lang="fa"' in page.decode(), path
        if args.expect_live_gifts and path != "/help":
            assert "noindex" in page_headers.get("X-Robots-Tag", "")
    bootstrap, headers = request("/api/v1/bootstrap")
    config = json.loads(bootstrap)
    if args.expect_plain_recipient_links:
        assert len(config["categories"]) == 18
    assert config["demo_mode"] is (not args.expect_live_gifts) and "no-store" in headers.get("Cache-Control", "")
    if args.expect_live_gifts:
        assert config["otp_is_real"] and config["payment_backend"] == "disabled"
        assert any('rel="canonical" href="' + url + '"' in html for url in [origin, origin + '/'])
        assert 'application/ld+json' in html and 'WebApplication' in html
        sitemap, _ = request("/sitemap.xml")
        assert all((origin + path).encode() in sitemap for path in ["/", "/help", "/privacy"])
        assert b"/history" not in sitemap and b"/preferences" not in sitemap
        robots, _ = request("/robots.txt")
        assert ("Sitemap: " + origin + "/sitemap.xml").encode() in robots
        results["checks"]["live_gifts_and_public_seo"] = True
    request("/healthz")
    request("/api/v1/messages", 401)
    request("/api/v1/preferences", 401)
    request("/api/v1/does-not-exist", 404)
    request("/admin", 301)
    request("/admin/", 302)
    request("/admin/login/?next=/admin/")
    request("/static/admin/css/base.css")
    _, sw_headers = request("/sw.js")
    assert sw_headers.get("Service-Worker-Allowed") == "/"
    manifest, _ = request("/manifest.webmanifest")
    assert json.loads(manifest)["display"] == "standalone"
    request("/offline.html")
    results["checks"]["routes_and_pwa_files"] = True
    by_name = {cookie.name: cookie for cookie in cookies}
    for name in ["csrftoken", "sessionid"]:
        cookie = by_name[name]
        assert cookie.secure and not cookie.domain_specified
        assert cookie.get_nonstandard_attr("SameSite", "").lower() == "lax"
    assert by_name["sessionid"].has_nonstandard_attr("HttpOnly")
    results["checks"]["secure_host_only_cookies"] = True
    payload = json.dumps({"phone": "invalid"}).encode()
    request("/api/v1/auth/request-otp", 403, payload, {"Content-Type": "application/json"})
    request("/api/v1/auth/request-otp", 400, payload, {"Content-Type": "application/json",
        "Origin": origin, "X-CSRFToken": by_name["csrftoken"].value})
    request("/api/v1/auth/request-otp", 403, payload, {"Content-Type": "application/json",
        "Origin": "https://untrusted.invalid", "X-CSRFToken": by_name["csrftoken"].value})
    results["checks"]["csrf_and_https_origin"] = True
    if args.admin_credentials:
        credentials = json.loads(Path(args.admin_credentials).read_text())
        data = urllib.parse.urlencode({"username": credentials["username"], "password": credentials["password"],
            "csrfmiddlewaretoken": by_name["csrftoken"].value, "next": "/admin/"}).encode()
        request("/admin/login/?next=/admin/", 302, data,
            {"Content-Type": "application/x-www-form-urlencoded", "Origin": origin, "Referer": origin + "/admin/login/"})
        admin, _ = request("/admin/")
        assert b"logout" in admin
        request("/admin/core/account/test-limits/")
        results["checks"]["admin_login"] = True
    if args.product_session:
        session = json.loads(Path(args.product_session).read_text())
        data, _ = request("/api/v1/bootstrap", headers={"Cookie": "sessionid=" + session["sessionid"]})
        assert json.loads(data)["authenticated"]
        request("/api/v1/messages", headers={"Cookie": "sessionid=" + session["sessionid"]})
        results["checks"]["product_session"] = True
    results["result"] = "PASS"
    results["real_sms_sent"] = 0
    results["payments_created"] = 0
    serialized = json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized)
    print(serialized)


if __name__ == "__main__":
    main()
