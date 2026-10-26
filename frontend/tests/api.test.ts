import { test } from "node:test";
import assert from "node:assert/strict";
import { api, ApiError, createIdempotencyKey, errorMessage } from "../lib/api.ts";

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
  assert.match(approvedPaymentRedirect('https://sandbox.zarinpal.com/pg/StartPay/S123',false),/^https:/);
  assert.throws(()=>approvedPaymentRedirect('https://sandbox.zarinpal.com.evil.invalid/pg/StartPay/S123',false));
  assert.throws(()=>approvedPaymentRedirect('http://www.zarinpal.com/pg/StartPay/S123',false));
  assert.throws(()=>approvedPaymentRedirect('javascript:alert(1)',true));
  assert.throws(()=>approvedPaymentRedirect('http://127.0.0.1:9999/pg/StartPay/S123',false));
  assert.match(approvedPaymentRedirect('http://127.0.0.1:9999/pg/StartPay/S123',true),/^http:/);
});
