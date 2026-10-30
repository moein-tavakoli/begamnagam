import { test, type TestContext } from "node:test";
import assert from "node:assert/strict";
import { api, ApiError, createIdempotencyKey, errorMessage } from "../lib/api.ts";

function otpSessionBrowser(context: TestContext) {
  const previousFetch = globalThis.fetch;
  const originals = ["window", "document"].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)] as const);
  context.after(() => {
    globalThis.fetch = previousFetch;
    for (const [key, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
  });
  const events: CustomEvent<{ settled?: Promise<void> }>[] = [];
  Object.defineProperty(globalThis, "window", { configurable: true, value: {
    dispatchEvent(event: CustomEvent<{ settled?: Promise<void> }>) { events.push(event); return true; },
  } });
  Object.defineProperty(globalThis, "document", { configurable: true, value: { cookie: "csrftoken=isolated-otp-csrf" } });
  globalThis.fetch = async () => Response.json({ authenticated: true, phone_masked: "masked-test-number" });
  return events;
}

test("API canonicalizes numeric text in the actual request and retains credentials", async t => {
  otpSessionBrowser(t);
  let sent: unknown;
  globalThis.fetch = async (_url, options) => { sent = JSON.parse(String(options?.body)); return Response.json({ ok: true }); };
  const body = { text: "رسید ۱۲", phone: "۰۹۱۲", values: { reference: "BANK٠٠١" }, amount: 1200, password: "رمز۱۲", alternative_token: "Ab۱۲" };
  await api("/numeric-input-check", { method: "POST", body });
  assert.deepEqual(sent, { text: "رسید 12", phone: "0912", values: { reference: "BANK001" }, amount: 1200, password: "رمز۱۲", alternative_token: "Ab۱۲" });
  assert.equal(body.text, "رسید ۱۲");
});

test("OTP notifies other tabs immediately while local feedback finishes", async context => {
  const events = otpSessionBrowser(context);
  let complete!: () => void;
  let notified!: () => void;
  const started = new Promise<void>(resolve => { notified = resolve; });
  const feedback = new Promise<void>(resolve => { complete = resolve; });
  let returned = false;
  const request = api<{ authenticated: boolean }>("/auth/verify-otp", {
    method: "POST", body: {},
    beforeSessionReset: async result => { assert.equal(result.authenticated, true); notified(); await feedback; },
  }).then(result => { returned = true; return result; });
  await started;
  assert.equal(events.length, 1);
  assert.equal(events[0].type, "privacy-reset");
  assert.ok(events[0].detail.settled instanceof Promise);
  assert.equal(returned, false);
  complete();
  assert.equal((await request).authenticated, true);
  await events[0].detail.settled;
});

test("rejected OTP never plays success feedback or resets the session", async context => {
  const events = otpSessionBrowser(context);
  globalThis.fetch = async () => Response.json({ error: { code: "invalid_otp", message: "کد درست نیست." } }, { status: 422 });
  await assert.rejects(() => api("/auth/verify-otp", {
    method: "POST", body: {}, beforeSessionReset: async () => { assert.fail("Unexpected success feedback"); },
  }), (error: unknown) => error instanceof ApiError && error.code === "invalid_otp");
  assert.deepEqual(events, []);
});

test("broken visual feedback cannot turn verified OTP into an authentication error", async context => {
  const events = otpSessionBrowser(context);
  const result = await api<{ authenticated: boolean }>("/auth/verify-otp", {
    method: "POST", body: {}, beforeSessionReset: async () => { throw new Error("Visual feedback unavailable"); },
  });
  assert.equal(result.authenticated, true);
  assert.equal(events.length, 1);
  await events[0].detail.settled;
});

test("unfinished OTP feedback cannot delay local session reset beyond three seconds", async context => {
  context.mock.timers.enable({ apis: ["setTimeout"] });
  const events = otpSessionBrowser(context);
  let started!: () => void;
  const waiting = new Promise<void>(resolve => { started = resolve; });
  const request = api<{ authenticated: boolean }>("/auth/verify-otp", {
    method: "POST", body: {}, beforeSessionReset: async () => { started(); await new Promise(() => {}); },
  });
  await waiting;
  context.mock.timers.tick(3000);
  assert.equal((await request).authenticated, true);
  assert.equal(events.length, 1);
  await events[0].detail.settled;
});

test("local HTTP mobile browsers get a cryptographic UUID without randomUUID", (context) => {
  const original = Object.getOwnPropertyDescriptor(globalThis, "crypto")!;
  context.after(() => Object.defineProperty(globalThis, "crypto", original));
  Object.defineProperty(globalThis, "crypto", {
    configurable: true,
    value: { getRandomValues: (bytes: Uint8Array) => bytes.fill(17) },
  });
  assert.equal(createIdempotencyKey(), "11111111-1111-4111-9111-111111111111");
});

test("mutations forward the CSRF cookie and preserve the order idempotency key", async (context) => {
  const previousFetch = globalThis.fetch;
  const previousDocument = Object.getOwnPropertyDescriptor(
    globalThis,
    "document",
  );
  context.after(() => {
    globalThis.fetch = previousFetch;
    if (previousDocument)
      Object.defineProperty(globalThis, "document", previousDocument);
    else Reflect.deleteProperty(globalThis, "document");
  });
  Object.defineProperty(globalThis, "document", {
    value: { cookie: "other=value; csrftoken=local-csrf-token" },
    configurable: true,
  });
  globalThis.fetch = async (input, init) => {
    assert.equal(input, "/api/v1/orders");
    assert.equal(init?.credentials, "same-origin");
    assert.equal(init?.cache, "no-store");
    assert.equal(
      (init?.headers as Record<string, string>)["X-CSRFToken"],
      "local-csrf-token",
    );
    assert.equal(
      (init?.headers as Record<string, string>)["Idempotency-Key"],
      "same-order-retry-key",
    );
    assert.equal(
      init?.body,
      JSON.stringify({ preview_id: "reviewed-preview" }),
    );
    return Response.json({ id: "one-order", status: "awaiting_payment" });
  };
  const result = await api<{ id: string }>("/orders", {
    method: "POST",
    body: { preview_id: "reviewed-preview" },
    idempotencyKey: "same-order-retry-key",
  });
  assert.equal(result.id, "one-order");
});

test("server moderation errors retain their Persian explanation and field details", async (context) => {
  const previousFetch = globalThis.fetch;
  context.after(() => {
    globalThis.fetch = previousFetch;
  });
  globalThis.fetch = async () =>
    Response.json(
      {
        error: {
          code: "content_rejected",
          message: "متن نیاز به اصلاح دارد.",
          fields: { text: ["از اطلاعات خصوصی استفاده نکنید."] },
        },
      },
      { status: 422 },
    );
  await assert.rejects(
    () => api("/messages/preview", { method: "POST", body: {} }),
    (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.code, "content_rejected");
      assert.equal(error.message, "متن نیاز به اصلاح دارد.");
      assert.deepEqual(error.fields?.text, ["از اطلاعات خصوصی استفاده نکنید."]);
      return true;
    },
  );
});

test("logout clears private UI only after a successful CSRF-protected request", async context => {
  const previousFetch = globalThis.fetch;
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const previousDocument = Object.getOwnPropertyDescriptor(globalThis, "document");
  context.after(() => {
    globalThis.fetch = previousFetch;
    for (const [key, descriptor] of [["window", previousWindow], ["document", previousDocument]] as const) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
  });
  const events: string[] = [];
  Object.defineProperty(globalThis, "window", {configurable: true, value: {dispatchEvent: (event: Event) => events.push(event.type)}});
  Object.defineProperty(globalThis, "document", {configurable: true, value: {cookie: "csrftoken=logout-csrf"}});
  globalThis.fetch = async (input, init) => {
    assert.equal(input, "/api/v1/auth/logout");
    assert.equal(init?.method, "POST");
    assert.equal((init?.headers as Record<string, string>)["X-CSRFToken"], "logout-csrf");
    return Response.json({error: {message: "دوباره تلاش کن."}}, {status: 503});
  };
  await assert.rejects(() => api("/auth/logout", {method: "POST", body: {}}));
  assert.deepEqual(events, []);
  globalThis.fetch = async () => Response.json({logged_out: true});
  await api("/auth/logout", {method: "POST", body: {}});
  assert.deepEqual(events, ["privacy-reset"]);
});

test("offline and non-JSON proxy failures become recoverable service errors", async (context) => {
  const previousFetch = globalThis.fetch;
  context.after(() => {
    globalThis.fetch = previousFetch;
  });
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  await assert.rejects(
    () => api("/bootstrap"),
    (error: unknown) =>
      error instanceof ApiError && error.code === "network_error",
  );
  globalThis.fetch = async () =>
    new Response("upstream unavailable", { status: 502 });
  await assert.rejects(
    () => api("/bootstrap"),
    (error: unknown) =>
      error instanceof ApiError && error.code === "service_error",
  );
});

test("business restrictions remain useful while system and provider credit details stay hidden", async context => {
  const previousFetch = globalThis.fetch;
  context.after(() => { globalThis.fetch = previousFetch; });
  for (const status of [500, 502, 503]) {
    globalThis.fetch = async () => Response.json({ error: { code: "service_unavailable", message: "provider balance empty; private internal detail", fields: { secret: "private" } } }, { status });
    await assert.rejects(() => api('/orders'), (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.equal(errorMessage(error), "درخواست فعلاً انجام نشد؛ کمی بعد دوباره تلاش کن.");
      assert.equal(error.fields, undefined);
      return true;
    });
  }
  const message = "بین ارسال‌های شما به همین شماره باید ۲۴ ساعت فاصله باشد.";
  globalThis.fetch = async () => Response.json({ error: { code: "pair_cooldown", message } }, { status: 409 });
  await assert.rejects(() => api('/orders'), (error: unknown) => errorMessage(error) === message);
  assert.equal(errorMessage(new Error('private runtime exception')), "درخواست فعلاً انجام نشد؛ کمی بعد دوباره تلاش کن.");
});


test('gateway navigation is restricted to documented HTTPS hosts or explicit demo loopback', async () => {
  const {approvedPaymentRedirect}=await import('../lib/api.ts');
  assert.throws(()=>approvedPaymentRedirect('https://sandbox.zarinpal.com/pg/StartPay/S123',false));
  assert.match(approvedPaymentRedirect('https://sandbox.zarinpal.com/pg/StartPay/S123',true),/^https:/);
  assert.match(approvedPaymentRedirect('https://www.zarinpal.com/pg/StartPay/A123',false),/^https:/);
  assert.throws(()=>approvedPaymentRedirect('https://sandbox.zarinpal.com.evil.invalid/pg/StartPay/S123',false));
  assert.throws(()=>approvedPaymentRedirect('http://www.zarinpal.com/pg/StartPay/S123',false));
  assert.throws(()=>approvedPaymentRedirect('javascript:alert(1)',true));
  assert.throws(()=>approvedPaymentRedirect('http://127.0.0.1:9999/pg/StartPay/S123',false));
  assert.match(approvedPaymentRedirect('http://127.0.0.1:9999/pg/StartPay/S123',true),/^http:/);
});
