import assert from "node:assert/strict";
import { test } from "node:test";
import { contentSecurityPolicy, isMonitoringTvRequest } from "../lib/security.ts";
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
  assert.deepEqual(directives["img-src"], ["'self'", "data:", "blob:", "https://trustseal.enamad.ir"]);
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

test("the LAN monitoring document permits only the two TV Studio player origins", () => {
  const policy = contentSecurityPolicy(nonce, false, true, { monitoringTv: true });
  assert.ok(policy.includes("frame-ancestors http://tv.ir http://192.168.1.117:8080"));
  assert.ok(!policy.includes("upgrade-insecure-requests"));
  assert.ok(policy.includes("form-action 'none'"));
  assert.ok(contentSecurityPolicy(nonce, false, true).includes("frame-ancestors 'none'"));
});

test("the framed monitoring policy needs the exact private GET route and enabled gateway", () => {
  const path = "/manage/monitoring/tv";
  assert.ok(isMonitoringTvRequest(path, "GET", "1", "1"));
  assert.ok(isMonitoringTvRequest(path, "HEAD", "1", "1"));
  assert.ok(!isMonitoringTvRequest(path, "POST", "1", "1"));
  assert.ok(!isMonitoringTvRequest(path, "GET", "0", "1"));
  assert.ok(!isMonitoringTvRequest(path, "GET", "1", null));
  assert.ok(!isMonitoringTvRequest("/manage/monitoring", "GET", "1", "1"));
});
