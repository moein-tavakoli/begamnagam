import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";
import config from "../next.config.ts";
import { GET as recipientRedirect, HEAD as recipientHead } from "../app/r/[code]/route.ts";
import { helpQuestions } from "../lib/help-content.ts";
import {
  getSeoConfig,
  pageJsonLd,
  privateMetadata,
  privatePages,
  publicPages,
  publicMetadata,
  rootMetadata,
  robotsRules,
  serializeJsonLd,
  sitemapEntries,
  siteLogo,
  socialImage,
} from "../lib/seo.ts";

const publicEnvironment = {
  APP_BASE_URL: "https://begamnagam.ir",
  SEO_INDEXABLE: "1",
};
const expectedPublicUrls = [
  "https://begamnagam.ir/",
  "https://begamnagam.ir/help",
  "https://begamnagam.ir/privacy",
  "https://begamnagam.ir/links",
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
    for (const path of ["/", "/help", "/privacy", "/links"] as const) {
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

test("public indexing exposes exactly four clean canonical pages with matching social metadata", () => {
  assert.equal(getSeoConfig(publicEnvironment).indexable, true);
  const entries = sitemapEntries(publicEnvironment);
  assert.deepEqual(entries.map(entry => entry.url), expectedPublicUrls);
  assert.equal(new Set(entries.map(entry => entry.url)).size, 4);
  const titles = new Set();
  const descriptions = new Set();
  for (const [index, path] of (["/", "/help", "/privacy", "/links"] as const).entries()) {
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
    assert.equal(images[0].type, "image/png");
    assert.equal(images[0].secureUrl, images[0].url);
    assert.ok(images[0].alt);
    assert.equal(metadata.twitter?.images?.[0].url, images[0].url);
    assert.ok(metadata.description);
    titles.add(metadata.title?.absolute);
    descriptions.add(metadata.description);
  }
  assert.equal(titles.size, 4);
  assert.equal(descriptions.size, 4);
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
  for (const path of Object.keys(privatePages) as (keyof typeof privatePages)[]) {
    const metadata = privateMetadata(path);
    assert.equal(metadata.title, privatePages[path].title);
    assert.equal(metadata.description, privatePages[path].description);
    assert.deepEqual(metadata.robots, {
      index: false,
      follow: false,
      noarchive: true,
      nosnippet: true,
      googleBot: { index: false, follow: false, noimageindex: true, nosnippet: true },
    });
    assert.equal(metadata.referrer, "no-referrer");
    assert.equal(metadata.alternates, null);
    assert.equal(metadata.openGraph, null);
    assert.equal(metadata.twitter, null);
  }
});

test("robots allows HTML crawlers to read noindex while excluding administrative and API routes", () => {
  for (const environment of [{}, publicEnvironment]) {
    const robots = robotsRules(environment);
    assert.equal(robots.rules.userAgent, "*");
    assert.equal(robots.rules.allow, "/");
    assert.deepEqual(robots.rules.disallow, ["/api/", "/admin/", "/manage", "/static/admin/"]);
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
  for (const path of ["/help", "/privacy", "/links"] as const) {
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
        "@id": `https://begamnagam.ir/help#${question.id}`,
        name: question.question,
        acceptedAnswer: { "@type": "Answer", "@id": `https://begamnagam.ir/help#${question.id}-answer`, text: question.answer },
      })));
    }
  }
});

test("root metadata remains safe for unknown and private routes and declares real PWA assets", () => {
  const metadata = rootMetadata(publicEnvironment);
  assert.equal(metadata.metadataBase?.href, "https://begamnagam.ir/");
  assert.deepEqual(metadata.robots, { index: false, follow: false });
  assert.equal(metadata.openGraph, undefined);
  assert.equal(metadata.twitter, undefined);
  assert.equal(metadata.alternates, undefined);
  assert.equal(metadata.manifest, "/manifest.webmanifest");
  assert.deepEqual(metadata.formatDetection, { telephone: false, email: false, address: false });
  const assets = [
    { ...siteLogo, type: "image/png" },
    socialImage,
    { url: "/icons/icon-192.png", width: 192, height: 192, type: "image/png" },
    { url: "/icons/apple-touch-icon.png", width: 180, height: 180, type: "image/png" },
  ];
  for (const asset of assets) {
    const data = readFileSync(new URL(`../public${asset.url}`, import.meta.url));
    assert.equal(data.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
    assert.equal(data.readUInt32BE(16), asset.width, asset.url);
    assert.equal(data.readUInt32BE(20), asset.height, asset.url);
    assert.ok(data.length < 1_000_000, "social and icon assets should remain small");
  }
});

test("all page routes opt into public or private metadata and all public routes reach the sitemap", () => {
  const root = new URL("../app/", import.meta.url);
  const routes = readdirSync(root, { recursive: true })
    .filter((file): file is string => typeof file === "string" && /(^|\/)page\.tsx$/.test(file))
    .map(file => ({ path: `/${file.replace(/(^|\/)page\.tsx$/, "")}`, source: readFileSync(new URL(file, root), "utf8") }));
  assert.deepEqual(routes.map(route => route.path).sort(), [...Object.keys(publicPages), ...Object.keys(privatePages)].sort());
  for (const { path, source } of routes) {
    const isPublic = path in publicPages;
    const factory = isPublic ? "publicMetadata" : "privateMetadata";
    // Public pages may extend their metadata with an approved verification tag.
    assert.match(source, new RegExp(`export const metadata = (?:\\{\\s*\\.\\.\\.)?${factory}\\(`), path);
    assert.equal(source.includes("<StructuredData"), isPublic, path);
  }
});

test("public graphs connect brand, website, images and page without inventing business details", () => {
  for (const path of Object.keys(publicPages) as (keyof typeof publicPages)[]) {
    const data = pageJsonLd(path, path === "/help" ? helpQuestions : [], publicEnvironment);
    const graph = data["@graph"];
    const ids = new Set(graph.map(node => node["@id"]));
    assert.equal(ids.size, graph.length);
    const organization = graph.find(node => node["@type"] === "Organization");
    const website = graph.find(node => node["@type"] === "WebSite");
    const page = graph.find(node => ["WebPage", "FAQPage"].includes(node["@type"] as string));
    assert.ok(organization && website && page);
    assert.equal(organization.name, "بگم نگم");
    assert.equal(organization.url, "https://begamnagam.ir/");
    assert.deepEqual(website.publisher, { "@id": organization["@id"] });
    assert.deepEqual(page.publisher, { "@id": organization["@id"] });
    for (const reference of [organization.logo, organization.image, page.primaryImageOfPage]) {
      const asset = graph.find(node => node["@id"] === reference["@id"]);
      assert.equal(asset?.["@type"], "ImageObject");
      assert.equal(asset?.encodingFormat, "image/png");
      assert.ok(asset?.width && asset?.height);
    }
    for (const node of graph) {
      for (const forbidden of ["address", "telephone", "email", "contactPoint", "legalName", "sameAs", "aggregateRating", "review", "offers", "price", "dateModified", "datePublished", "potentialAction"]) {
        assert.equal(node[forbidden], undefined, `${path}: ${forbidden}`);
      }
    }
    const service = graph.find(node => node["@type"] === "Service");
    if (path === "/") {
      assert.ok(service);
      assert.deepEqual(service.provider, { "@id": organization["@id"] });
      assert.deepEqual(page.about, { "@id": service["@id"] });
    } else assert.equal(service, undefined);
  }
  assert.equal(pageJsonLd("/", helpQuestions, publicEnvironment)["@graph"].some(node => node["@type"] === "FAQPage"), false);
  assert.equal(new Set(helpQuestions.map(question => question.id)).size, helpQuestions.length);
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
  for (const source of ["/r", "/r/:path*", "/credits", "/profile", "/history", "/invitations", "/preferences", "/api/:path*", "/admin/:path*", "/offline.html"]) {
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

test("admin forms retain same-origin context for CSRF while private links omit referrers", async () => {
  const rules = await config.headers!();
  const policies = rules.filter(rule => ["/:path*", "/admin/:path*"].includes(rule.source))
    .flatMap(rule => rule.headers).filter(header => header.key === "Referrer-Policy");
  assert.equal(policies.at(-1)?.value, "same-origin");
  assert.equal(rules.filter(rule => rule.source === "/r").flatMap(rule => rule.headers)
    .find(header => header.key === "Referrer-Policy")?.value, "no-referrer");
});

test("plain SMS links accept only eight English letters or digits and keep the recipient screen private", async () => {
  const request = new Request('https://begamnagam.ir/r/Ab12Cd34?untrusted=ignored');
  for (const method of [recipientRedirect, recipientHead]) {
    const response = await method(request, { params: Promise.resolve({ code: 'Ab12Cd34' }) });
    assert.equal(response.status, 307);
    assert.equal(response.headers.get('location'), '/r#Ab12Cd34');
    assert.ok(response.headers.get('cache-control')?.includes('no-store'));
    assert.equal(response.headers.get('referrer-policy'), 'no-referrer');
    assert.ok(response.headers.get('x-robots-tag')?.includes('noindex'));
    assert.equal(await response.text(), '');
  }
  for (const code of ['abc', 'Abcd_123', 'Abcd-123', 'AB۱۲cd34', 'A'.repeat(43), 'Ab12Cd34/extra']) {
    const response = await recipientRedirect(request, { params: Promise.resolve({ code }) });
    assert.equal(response.status, 404);
    assert.equal(response.headers.get('location'), null);
  }
  const headers = (await config.headers!()).filter(item => item.source === '/r/:path*').flatMap(item => item.headers);
  assert.ok(headers.some(item => item.key === 'Cache-Control' && item.value === 'no-store'));
  assert.ok(headers.some(item => item.key === 'Referrer-Policy' && item.value === 'no-referrer'));
});
