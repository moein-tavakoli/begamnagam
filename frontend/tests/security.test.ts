import assert from "node:assert/strict";
import { test } from "node:test";
import { contentSecurityPolicy } from "../lib/security.ts";
import nextConfig from "../next.config.ts";

const nonce = Buffer.alloc(32, 7).toString("base64");

test("browser debug indicator and production source maps are disabled and secrets are not exported", () => {
  assert.equal(nextConfig.devIndicators, false);
  assert.equal(nextConfig.productionBrowserSourceMaps, false);
  assert.deepEqual(Object.keys(nextConfig.env || {}).sort(), ["APP_BASE_URL", "SEO_INDEXABLE"]);
});

test("production CSP authorizes nonce scripts and excludes arbitrary script execution and connections", () => {
  const policy = contentSecurityPolicy(nonce, false, true);
  const directives = Object.fromEntries(policy.split("; ").map(value => {
    const [key, ...values] = value.split(" ");
    return [key, values];
  }));
  assert.ok(directives["script-src"].includes(`'nonce-${nonce}'`));
  assert.ok(directives["script-src"].includes("'strict-dynamic'"));
  assert.ok(!directives["script-src"].includes("'unsafe-inline'"));
  assert.ok(!directives["script-src"].includes("'unsafe-eval'"));
  for (const key of ["script-src-attr", "object-src", "frame-src", "base-uri", "frame-ancestors"])
    assert.deepEqual(directives[key], ["'none'"]);
  assert.deepEqual(directives["connect-src"], ["'self'"]);
  assert.deepEqual(directives["form-action"], ["'self'"]);
  assert.deepEqual(directives["worker-src"], ["'self'"]);
  assert.ok("upgrade-insecure-requests" in directives);
});

test("CSP permits development Fast Refresh without forcing HTTPS on HTTP development", () => {
  const policy = contentSecurityPolicy(nonce, true, false);
  assert.ok(policy.includes("'unsafe-eval'"));
  assert.ok(policy.includes("ws: wss:"));
  assert.ok(!policy.includes("upgrade-insecure-requests"));
  for (const invalid of ["", "attacker' ; script-src *", "x".repeat(32), nonce + "\n"]) {
    assert.throws(() => contentSecurityPolicy(invalid, false, true));
  }
});
