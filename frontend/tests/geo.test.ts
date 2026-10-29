import assert from "node:assert/strict";
import { test } from "node:test";
import { aiPrivatePaths, aiSearchAgents, aiTrainingAgents, llmsText, pageJsonLd, publicPages, robotsRules, serviceFacts } from "../lib/seo.ts";

const publicEnvironment = { APP_BASE_URL: "https://begamnagam.ir", SEO_INDEXABLE: "1" };

test("search and user retrieval agents inherit private exclusions while known training crawls are denied", () => {
  const rules = robotsRules(publicEnvironment).rules;
  assert.ok(Array.isArray(rules));
  for (const agent of aiSearchAgents) {
    const rule = rules.find(rule => Array.isArray(rule.userAgent) && rule.userAgent.includes(agent))!;
    assert.equal(rule.allow, "/", agent);
    assert.deepEqual(rule.disallow, [...aiPrivatePaths], agent);
  }
  for (const agent of aiTrainingAgents) {
    const rule = rules.find(rule => Array.isArray(rule.userAgent) && rule.userAgent.includes(agent))!;
    assert.equal(rule.disallow, "/", agent);
    assert.equal(rule.allow, undefined, agent);
  }
  assert.ok(!aiTrainingAgents.some(agent => ["Googlebot", "bingbot", "Applebot"].includes(agent)));
});

test("local and non-indexable deployments never publish an agent content index or opt in AI crawling", () => {
  for (const env of [{}, { APP_BASE_URL: "https://begamnagam.ir", SEO_INDEXABLE: "0" }]) {
    assert.equal(llmsText(env), null);
    const rules = robotsRules(env).rules;
    assert.ok(Array.isArray(rules));
    for (const agent of [...aiSearchAgents, ...aiTrainingAgents]) {
      const rule = rules.find(rule => Array.isArray(rule.userAgent) && rule.userAgent.includes(agent))!;
      assert.equal(rule.disallow, "/");
      assert.equal(rule.allow, undefined);
    }
  }
});

test("the optional agent index uses the same public facts and only canonical public links", () => {
  const text = llmsText(publicEnvironment)!;
  assert.ok(text.startsWith("# بگم نگم (BegamNagam)\n"));
  for (const fact of serviceFacts.slice(1)) assert.ok(text.includes(fact.text), fact.id);
  const links = [...text.matchAll(/\]\(([^)]+)\)/g)].map(match => new URL(match[1]));
  assert.equal(links.length, Object.keys(publicPages).length);
  assert.equal(new Set(links.map(link => link.pathname)).size, Object.keys(publicPages).length);
  for (const link of links) {
    assert.equal(link.origin, publicEnvironment.APP_BASE_URL);
    assert.ok(Object.hasOwn(publicPages, link.pathname));
    assert.equal(link.search, "");
    assert.equal(link.hash, "");
  }
});

test("the about page identifies the brand with an AboutPage and preserves the canonical entity graph", () => {
  const graph = pageJsonLd("/about", [], publicEnvironment)["@graph"];
  const page = graph.find(node => node["@type"] === "AboutPage")!;
  const organization = graph.find(node => node["@type"] === "Organization")!;
  assert.equal(page.url, "https://begamnagam.ir/about");
  assert.deepEqual(page.mainEntity, { "@id": organization["@id"] });
  assert.equal(organization.legalName, undefined);
  assert.equal(organization.address, undefined);
  assert.equal(organization.sameAs, undefined);
  assert.equal(new Set(serviceFacts.map(fact => fact.id)).size, serviceFacts.length);
});
