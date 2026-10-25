import assert from "node:assert/strict";
import { test } from "node:test";
import config from "../next.config.ts";
import { helpQuestions } from "../lib/help-content.ts";
import {
  getSeoConfig,
  pageJsonLd,
  privateMetadata,
  publicMetadata,
  robotsRules,
  serializeJsonLd,
  sitemapEntries,
} from "../lib/seo.ts";

const publicEnvironment = {
  APP_BASE_URL: "https://begamnagam.ir",
  SEO_INDEXABLE: "1",
};
const expectedPublicUrls = [
  "https://begamnagam.ir/",
  "https://begamnagam.ir/help",
  "https://begamnagam.ir/privacy",
];

test("default and internal demo environments cannot advertise indexable pages", () => {
  for (const environment of [
    {},
    { APP_BASE_URL: "https://192.168.1.123" },
    { APP_BASE_URL: "https://begamnagam.ir", SEO_INDEXABLE: "0" },
    { APP_BASE_URL: "https://begamnagam.ir", SEO_INDEXABLE: "true" },
  ]) {
    assert.equal(getSeoConfig(environment).indexable, false);
    assert.deepEqual(sitemapEntries(environment), []);
    for (const path of ["/", "/help", "/privacy"] as const) {
      assert.deepEqual(publicMetadata(path, environment).robots, {
        index: false,
        follow: false,
      });
    }
    assert.equal(robotsRules(environment).sitemap, undefined);
  }
  assert.equal(getSeoConfig({}).baseUrl.href, "http://localhost:3000/");
  assert.equal(getSeoConfig({ APP_BASE_URL: "https://begamnagam.ir." }).baseUrl.href, "https://begamnagam.ir/");
});

test("public indexing exposes exactly three clean canonical pages with matching social metadata", () => {
  assert.equal(getSeoConfig(publicEnvironment).indexable, true);
  const entries = sitemapEntries(publicEnvironment);
  assert.deepEqual(entries.map(entry => entry.url), expectedPublicUrls);
  assert.equal(new Set(entries.map(entry => entry.url)).size, 3);
  const titles = new Set();
  const descriptions = new Set();
  for (const [index, path] of (["/", "/help", "/privacy"] as const).entries()) {
    const metadata = publicMetadata(path, publicEnvironment);
    assert.equal(metadata.alternates?.canonical, expectedPublicUrls[index]);
    assert.equal(metadata.openGraph?.url, expectedPublicUrls[index]);
    assert.equal(metadata.openGraph?.locale, "fa_IR");
    assert.deepEqual(metadata.openGraph?.title, metadata.title?.absolute);
    assert.deepEqual(metadata.twitter?.title, metadata.title?.absolute);
    assert.equal(metadata.twitter?.card, "summary_large_image");
    assert.equal(metadata.openGraph?.description, metadata.description);
    assert.equal(metadata.twitter?.description, metadata.description);
    assert.equal(metadata.robots?.index, true);
    assert.equal(metadata.robots?.follow, true);
    assert.equal(metadata.robots?.googleBot?.["max-image-preview"], "large");
    const images = metadata.openGraph?.images;
    assert.ok(Array.isArray(images) && images.length > 0);
    assert.equal(images[0].url, "https://begamnagam.ir/images/social-card.png");
    assert.equal(images[0].width, 1200);
    assert.equal(images[0].height, 630);
    assert.ok(images[0].alt);
    assert.equal(metadata.twitter?.images?.[0].url, images[0].url);
    assert.ok(metadata.description);
    titles.add(metadata.title?.absolute);
    descriptions.add(metadata.description);
  }
  assert.equal(titles.size, 3);
  assert.equal(descriptions.size, 3);
});

test("canonical origins reject credentials, non-origin components and unsafe protocols", () => {
  for (const origin of [
    "not a URL",
    "//begamnagam.ir",
    "javascript:alert(1)",
    "ftp://begamnagam.ir",
    "https://user:secret@begamnagam.ir",
    "https://begamnagam.ir/path",
    "https://begamnagam.ir/?private=token",
    "https://begamnagam.ir/#private-token",
  ]) {
    assert.throws(() => getSeoConfig({ APP_BASE_URL: origin }), origin);
  }
});

test("indexing requires an explicitly enabled public HTTPS domain", () => {
  for (const origin of [
    "http://begamnagam.ir",
    "https://localhost:3000",
    "https://localhost.",
    "https://frontend",
    "https://127.0.0.1",
    "https://192.168.1.123",
    "https://8.8.8.8",
    "https://[::1]",
    "https://begamnagam.localhost",
    "https://begamnagam.local",
    "https://begamnagam.internal",
    "https://begamnagam.internal.",
    "https://begamnagam.test",
    "https://begamnagam.test.",
    "https://begamnagam.example",
    "https://begamnagam.invalid",
  ]) {
    assert.throws(
      () => getSeoConfig({ APP_BASE_URL: origin, SEO_INDEXABLE: "1" }),
      /public HTTPS domain/,
      origin,
    );
  }
});

test("private page metadata cannot emit a public canonical or social preview", () => {
  for (const title of ["پیام‌های من", "قطع دریافت پیام", "انتخاب دریافت‌کننده"]) {
    const metadata = privateMetadata(title);
    assert.equal(metadata.title, title);
    assert.deepEqual(metadata.robots, {
      index: false,
      follow: false,
      noarchive: true,
      nosnippet: true,
    });
    assert.equal(metadata.referrer, "no-referrer");
    assert.equal(metadata.alternates, undefined);
    assert.equal(metadata.openGraph, undefined);
    assert.equal(metadata.twitter, undefined);
  }
});

test("robots allows HTML crawlers to read noindex while excluding administrative and API routes", () => {
  for (const environment of [{}, publicEnvironment]) {
    const robots = robotsRules(environment);
    assert.equal(robots.rules.userAgent, "*");
    assert.equal(robots.rules.allow, "/");
    assert.deepEqual(robots.rules.disallow, ["/api/", "/admin/", "/static/admin/"]);
    for (const path of ["/history", "/preferences", "/r"]) {
      assert.ok(!robots.rules.disallow.some(prefix => path.startsWith(prefix)));
    }
    assert.equal(
      robots.sitemap,
      environment.SEO_INDEXABLE === "1" ? "https://begamnagam.ir/sitemap.xml" : undefined,
    );
  }
});

test("homepage structured data connects the website, page and application using canonical IDs", () => {
  const data = pageJsonLd("/", [], publicEnvironment);
  assert.equal(data["@context"], "https://schema.org");
  const website = data["@graph"].find(node => node["@type"] === "WebSite");
  const page = data["@graph"].find(node => node["@type"] === "WebPage");
  const application = data["@graph"].find(node => node["@type"] === "WebApplication");
  assert.ok(website && page && application);
  assert.equal(website["@id"], "https://begamnagam.ir/#website");
  assert.equal(page["@id"], "https://begamnagam.ir/#webpage");
  assert.equal(application["@id"], "https://begamnagam.ir/#application");
  assert.deepEqual(page.isPartOf, { "@id": website["@id"] });
  assert.deepEqual(page.mainEntity, { "@id": application["@id"] });
  for (const node of [website, page, application]) {
    assert.equal(node.url, expectedPublicUrls[0]);
    assert.equal(node.inLanguage, "fa-IR");
    assert.equal(node.offers, undefined);
    assert.equal(node.aggregateRating, undefined);
  }
});

test("help FAQ and public breadcrumbs describe the canonical page and shared visible answers", () => {
  for (const path of ["/help", "/privacy"] as const) {
    const questions = path === "/help" ? helpQuestions : [];
    const data = pageJsonLd(path, questions, publicEnvironment);
    const page = data["@graph"].find(node => node["@type"] === (path === "/help" ? "FAQPage" : "WebPage"));
    const breadcrumb = data["@graph"].find(node => node["@type"] === "BreadcrumbList");
    assert.ok(page && breadcrumb);
    assert.equal(page["@id"], `https://begamnagam.ir${path}#webpage`);
    assert.deepEqual(page.isPartOf, { "@id": "https://begamnagam.ir/#website" });
    assert.deepEqual(page.breadcrumb, { "@id": breadcrumb["@id"] });
    assert.equal(breadcrumb["@id"], `https://begamnagam.ir${path}#breadcrumb`);
    assert.deepEqual(breadcrumb.itemListElement.map(item => [item.position, item.item]), [
      [1, "https://begamnagam.ir/"],
      [2, `https://begamnagam.ir${path}`],
    ]);
    assert.equal(data["@graph"].some(node => node["@type"] === "WebApplication"), false);
    if (path === "/help") {
      assert.ok(helpQuestions.length > 0);
      assert.deepEqual(page.mainEntity, helpQuestions.map(question => ({
        "@type": "Question",
        name: question.question,
        acceptedAnswer: { "@type": "Answer", text: question.answer },
      })));
    }
  }
});

test("JSON-LD serialization cannot close its script element and preserves Persian content", () => {
  const malicious = { text: '</script><script>alert("private")</script>', persian: "یک پیام محترمانه" };
  const serialized = serializeJsonLd(malicious);
  assert.ok(!serialized.includes("<"));
  assert.ok(!serialized.toLowerCase().includes("</script"));
  assert.deepEqual(JSON.parse(serialized), malicious);
  assert.deepEqual(
    JSON.parse(serializeJsonLd(pageJsonLd("/help", helpQuestions, publicEnvironment))),
    pageJsonLd("/help", helpQuestions, publicEnvironment),
  );
});

test("private, administrative and offline HTTP responses are protected against indexing", async () => {
  assert.ok(config.headers);
  const rules = await config.headers();
  for (const source of ["/r", "/history", "/preferences", "/api/:path*", "/admin/:path*", "/offline.html"]) {
    const headers = rules.filter(rule => rule.source === source).flatMap(rule => rule.headers);
    const robots = headers.find(header => header.key.toLowerCase() === "x-robots-tag");
    assert.ok(robots, source);
    assert.ok(robots.value.split(/,\s*/).includes("noindex"), source);
    assert.ok(robots.value.split(/,\s*/).includes("nofollow"), source);
  }
  const recipientHeaders = rules.filter(rule => rule.source === "/r").flatMap(rule => rule.headers);
  assert.ok(recipientHeaders.some(header => header.key === "Cache-Control" && header.value === "no-store"));
  assert.ok(recipientHeaders.some(header => header.key === "Referrer-Policy" && header.value === "no-referrer"));
});
