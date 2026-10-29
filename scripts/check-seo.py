#!/usr/bin/env python3
"""Read-only checks of rendered SEO, share-crawler HTML and private exclusions.

Uses no session cookies, API calls, OTP requests or SMS sends. Asset requests
always use the transport origin, even when testing a public build locally.
"""
import argparse
from collections import defaultdict
from html.parser import HTMLParser
import json
import re
import ssl
import struct
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


PUBLIC = ("/", "/help", "/privacy", "/links", "/pricing", "/about")
PRIVATE = ("/profile", "/history", "/invitations", "/preferences", "/r", "/manage", "/credits", "/wallet")
SHARE_CRAWLERS = ("TelegramBot", "WhatsApp/2.24", "facebookexternalhit/1.1", "Twitterbot/1.0",
                  "LinkedInBot/1.0", "Slackbot-LinkExpanding 1.0", "Discordbot/2.0")
AI_CRAWLERS = ("OAI-SearchBot", "ChatGPT-User", "Claude-SearchBot", "Claude-User", "PerplexityBot", "Perplexity-User")
TRAINING_CRAWLERS = ("GPTBot", "ClaudeBot", "Google-Extended", "Applebot-Extended", "CCBot")
CRAWLERS = (*SHARE_CRAWLERS, *AI_CRAWLERS)


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.meta = defaultdict(list)
        self.links = defaultdict(list)
        self.jsonld = []
        self.details = defaultdict(str)
        self.title = ""
        self.head = False
        self.in_title = False
        self.script_type = None
        self.script = ""
        self.detail_id = None
        self.language = None
        self.direction = None
        self.headings = 0
        self.in_main = False
        self.visible_text = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.language, self.direction = attrs.get("lang"), attrs.get("dir")
        if tag == "head":
            self.head = True
        if tag == "main":
            self.in_main = True
        if tag == "title":
            self.in_title = True
        if tag == "h1":
            self.headings += 1
        if tag == "meta" and self.head:
            self.meta[attrs.get("name", attrs.get("property"))].append(attrs.get("content", ""))
        if tag == "link" and self.head:
            self.links[attrs.get("rel")].append(attrs.get("href"))
        if tag == "script":
            self.script_type, self.script = attrs.get("type", ""), ""
        if tag == "details":
            self.detail_id = attrs.get("id")

    def handle_data(self, data):
        if self.in_main and self.script_type is None:
            self.visible_text.append(data)
        if self.in_title:
            self.title += data
        if self.script_type is not None:
            self.script += data
        elif self.detail_id:
            self.details[self.detail_id] += data

    def handle_endtag(self, tag):
        if tag == "main":
            self.in_main = False
        if tag == "head":
            self.head = False
        if tag == "title":
            self.in_title = False
        if tag == "script":
            if self.script_type == "application/ld+json":
                self.jsonld.append(json.loads(self.script))
            self.script_type = None
        if tag == "details":
            self.detail_id = None

    def one(self, name):
        values = self.meta[name]
        assert len(values) == 1 and values[0], f"Expected one nonempty head meta: {name}"
        return values[0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def origin(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or
            parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise argparse.ArgumentTypeError("Expected an HTTP(S) origin without credentials, path or query")
    return value.rstrip("/")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", type=origin, default="http://127.0.0.1:3000")
    parser.add_argument("--canonical-origin", type=origin, required=True)
    parser.add_argument("--expect-indexable", action="store_true")
    parser.add_argument("--ca-file", help="Trusted CA file for local HTTPS")
    args = parser.parse_args()
    opener = urllib.request.build_opener(
        NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=args.ca_file)))
    request_count = 0

    def get(path, status=200, agent="BegamNagam-SEO-Check/1.0"):
        nonlocal request_count
        assert path.startswith("/") and not path.startswith("//")
        request_count += 1
        request = urllib.request.Request(args.base_url + path, headers={"User-Agent": agent})
        try:
            response = opener.open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            assert response.status == status, f"{path}: expected {status}, got {response.status}"
            return response.read(), response.headers

    def page_at(path, status=200, agent="BegamNagam-SEO-Check/1.0"):
        body, headers = get(path, status, agent)
        assert headers.get_content_type() == "text/html", path
        page = Page(body.decode("utf-8"))
        assert (page.language, page.direction) == ("fa", "rtl"), path
        assert page.title and page.headings, path
        assert page.one("description"), path
        return page, headers

    graphs = []
    titles, descriptions = set(), set()
    for path in PUBLIC:
        expected = args.canonical_origin + path
        baseline_text, baseline_graph = None, None
        for agent in ("BegamNagam-SEO-Check/1.0", *CRAWLERS):
            page, headers = page_at(path + "?utm_source=seo-check", agent=agent)
            # Next normalizes the root canonical to the bare origin in HTML.
            canonical = args.canonical_origin if path == "/" else expected
            assert page.links["canonical"] == [canonical], (path, agent)
            assert page.one("og:url") == canonical
            assert page.one("og:title") == page.title == page.one("twitter:title")
            assert page.one("og:description") == page.one("description") == page.one("twitter:description")
            assert page.one("og:locale") == "fa_IR"
            assert page.one("og:site_name") == "بگم نگم"
            assert page.one("og:type") == "website"
            assert page.one("twitter:card") == "summary_large_image"
            image = args.canonical_origin + "/images/social-card.png"
            assert page.one("og:image") == image == page.one("twitter:image")
            assert page.one("og:image:type") == "image/png"
            assert (page.one("og:image:width"), page.one("og:image:height")) == ("1200", "630")
            assert page.one("og:image:alt") == page.one("twitter:image:alt")
            if args.canonical_origin.startswith("https:"):
                assert page.one("og:image:secure_url") == image
            expected_robots = "index, follow" if args.expect_indexable else "noindex, nofollow"
            assert page.one("robots") == expected_robots
            assert "noindex" not in headers.get("X-Robots-Tag", "") or not args.expect_indexable
            if args.expect_indexable:
                assert "max-image-preview:large" in page.one("googlebot")
            assert len(page.jsonld) == 1
            data = page.jsonld[0]
            assert data["@context"] == "https://schema.org"
            nodes = data["@graph"]
            assert len({node["@id"] for node in nodes}) == len(nodes)
            types = {node["@type"] for node in nodes}
            assert {"Organization", "ImageObject", "WebSite"} <= types
            expected_types = {"WebPage", "WebApplication", "Service"} if path == "/" else (
                {"FAQPage", "BreadcrumbList"} if path == "/help" else
                {"AboutPage", "BreadcrumbList"} if path == "/about" else {"WebPage", "BreadcrumbList"})
            assert expected_types <= types
            webpage = next(node for node in nodes if node["@id"] == expected + "#webpage")
            assert webpage["url"] == expected
            visible = " ".join(" ".join(page.visible_text).split())
            assert visible, (path, agent)
            if baseline_text is None:
                baseline_text, baseline_graph = visible, data
            else:
                assert visible == baseline_text and data == baseline_graph, (path, agent, "Crawler content differs")
            if path == "/":
                assert page.one("enamad") == "5251197"
            if path == "/about":
                for fact in ("ناشناس‌بودن برای گیرنده", "گیرنده چه اختیاری دارد", "هزینهٔ استفاده"):
                    assert fact in visible
            if args.expect_indexable:
                assert '</llms.txt>; rel="describedby"' in ",".join(headers.get_all("Link", []))
            if path == "/help":
                for question in webpage["mainEntity"]:
                    visible = " ".join(page.details[question["@id"].split("#")[1]].split())
                    assert question["name"] in visible
                    assert " ".join(question["acceptedAnswer"]["text"].split()) in visible
            if agent == "BegamNagam-SEO-Check/1.0":
                graphs.extend(nodes)
                titles.add(page.title)
                descriptions.add(page.one("description"))
    assert len(titles) == len(descriptions) == len(PUBLIC)

    # Resolve references across the complete set of public pages.
    definitions, references = set(), set()

    def visit(value):
        if isinstance(value, dict):
            if "@id" in value:
                (definitions if len(value) > 1 else references).add(value["@id"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(graphs)
    assert not references - definitions, f"Unresolved graph IDs: {references - definitions}"

    for path in PRIVATE:
        page, headers = page_at(path)
        assert "noindex" in page.one("robots") and "nofollow" in page.one("robots"), path
        assert "noindex" in headers.get("X-Robots-Tag", ""), path
        assert page.one("referrer") == "no-referrer"
        assert not page.links["canonical"] and not page.meta["og:url"] and not page.meta["twitter:card"]
        assert not page.jsonld
    missing, _ = page_at("/seo-check-missing-page", status=404)
    assert "noindex" in ",".join(missing.meta["robots"])
    assert not missing.links["canonical"] and not missing.jsonld
    for path in ("/r/Ab12Cd34", "/r/invalid"):
        _, headers = get(path, status=307 if path.endswith("Ab12Cd34") else 404)
        assert "noindex" in headers.get("X-Robots-Tag", "")
        assert "no-store" in headers.get("Cache-Control", "")
        if path.endswith("Ab12Cd34"):
            assert headers["Location"] == "/r#Ab12Cd34"
    offline, headers = page_at("/offline.html")
    assert "noindex" in offline.one("robots") and "noindex" in headers.get("X-Robots-Tag", "")

    for path, dimensions in (("/images/social-card.png", (1200, 630)), ("/icons/icon-512.png", (512, 512)),
                             ("/icons/apple-touch-icon.png", (180, 180))):
        body, headers = get(path)
        assert headers.get_content_type() == "image/png"
        assert body[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", body[16:24]) == dimensions
        assert len(body) < 1_000_000
    manifest, _ = get("/manifest.webmanifest")
    assert json.loads(manifest)["dir"] == "rtl"
    sitemap, _ = get("/sitemap.xml")
    urls = [node.text for node in ET.fromstring(sitemap).findall("{*}url/{*}loc")]
    assert urls == ([args.canonical_origin + path for path in PUBLIC] if args.expect_indexable else [])
    robots, _ = get("/robots.txt")
    robots = robots.decode()
    assert "Allow: /" in robots and "Disallow: /api/" in robots and "Disallow: /admin/" in robots
    assert ("Sitemap: " + args.canonical_origin + "/sitemap.xml" in robots) == args.expect_indexable
    # Check the actual emitted per-agent blocks, including private directives.
    groups, current, directives = {}, [], []
    for line in [*robots.splitlines(), ""]:
        if not line.strip():
            for agent in current:
                groups.setdefault(agent.lower(), []).extend(directives)
            current, directives = [], []
        else:
            name, _, value = line.partition(":")
            if name.lower() == "user-agent": current.append(value.strip())
            elif name.lower() in {"allow", "disallow"}: directives.append((name.lower(), value.strip()))
    for agent in AI_CRAWLERS:
        rules = groups[agent.lower()]
        if args.expect_indexable:
            assert ("allow", "/") in rules
            for path in (*PRIVATE, "/api/", "/admin/", "/r/"):
                assert ("disallow", "/r$" if path == "/r" else path) in rules, (agent, path)
        else:
            assert ("disallow", "/") in rules and ("allow", "/") not in rules
    for agent in TRAINING_CRAWLERS:
        assert groups[agent.lower()] == [("disallow", "/")]
    text, headers = get("/llms.txt", status=200 if args.expect_indexable else 404)
    assert headers.get_content_type() == "text/plain" and "noindex" in headers.get("X-Robots-Tag", "")
    if args.expect_indexable:
        text = text.decode()
        links = [urllib.parse.urlsplit(url) for url in re.findall(r"\]\(([^)]+)\)", text)]
        assert {link.path or "/" for link in links} == set(PUBLIC)
        assert len(links) == len(PUBLIC)
        assert all(f"{link.scheme}://{link.netloc}" == args.canonical_origin and not link.query and not link.fragment for link in links)
        assert "ناشناس‌بودن برای سرویس نیست" in text and "قابل برداشت بانکی نیست" in text
    print(json.dumps({"result": "PASS", "requests": request_count, "public_pages": len(PUBLIC),
                      "private_pages": len(PRIVATE), "share_crawlers": len(SHARE_CRAWLERS), "ai_crawlers": len(AI_CRAWLERS),
                      "indexable": args.expect_indexable}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
