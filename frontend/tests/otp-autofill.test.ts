import assert from "node:assert/strict";
import { test, type TestContext } from "node:test";
import { listenForSmsCode } from "../lib/otp-autofill.ts";
import { getServiceWorkerContainer, openSessionChannel } from "../lib/browser-capabilities.ts";

const originals = new WeakMap<TestContext, Map<string, PropertyDescriptor | undefined>>();
function replace(t: TestContext, name: string, value: unknown) {
  if (!originals.has(t)) {
    const saved = new Map<string, PropertyDescriptor | undefined>();
    originals.set(t, saved);
    t.after(() => {
      for (const [key, descriptor] of saved) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor);
        else Reflect.deleteProperty(globalThis, key);
      }
    });
  }
  const saved = originals.get(t)!;
  if (!saved.has(name)) saved.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
  Object.defineProperty(globalThis, name, { value, configurable: true });
}

function browser(t: TestContext, get: (options: CredentialRequestOptions) => unknown) {
  const timers = new Map<number, () => void>();
  const target = Object.assign(new EventTarget(), {
    isSecureContext: true, OTPCredential: class {},
    setTimeout: (fn: () => void) => { timers.set(1, fn); return 1; },
    clearTimeout: (id: number) => { timers.delete(id); },
  });
  replace(t, "window", target);
  replace(t, "navigator", { credentials: { get } });
  return { target, timers };
}

test("WebOTP fills only a valid received code and releases the listener", async t => {
  let options: CredentialRequestOptions | undefined;
  let receive!: (value: unknown) => void;
  const { timers } = browser(t, value => { options = value; return new Promise(resolve => { receive = resolve; }); });
  const codes: string[] = [];
  listenForSmsCode(code => codes.push(code));
  assert.equal(options?.signal?.aborted, false);
  assert.deepEqual((options as CredentialRequestOptions & { otp: unknown }).otp, { transport: ["sms"] });
  receive({ code: "012345" });
  await Promise.resolve();
  assert.deepEqual(codes, ["012345"]);
  assert.equal(options?.signal?.aborted, true);
  assert.equal(timers.size, 0);
});

test("cancelled or expired listeners never overwrite manual input with a late code", async t => {
  for (const cause of ["cancel", "timeout", "pagehide"]) {
    let receive!: (value: unknown) => void;
    let signal: AbortSignal | undefined;
    const { target, timers } = browser(t, options => {
      signal = options.signal;
      return new Promise(resolve => { receive = resolve; });
    });
    let value = "manual";
    const cancel = listenForSmsCode(code => { value = code; });
    if (cause === "cancel") cancel();
    if (cause === "timeout") timers.get(1)?.();
    if (cause === "pagehide") target.dispatchEvent(new Event("pagehide"));
    receive({ code: "012345" });
    await Promise.resolve();
    assert.equal(signal?.aborted, true, cause);
    assert.equal(value, "manual", cause);
    assert.equal(timers.size, 0, cause);
  }
});

test("denied, unavailable and invalid SMS credentials leave manual verification usable", async t => {
  const { target, timers } = browser(t, () => { throw new DOMException("Denied", "SecurityError"); });
  assert.doesNotThrow(() => listenForSmsCode(() => assert.fail("Unexpected code"))());
  assert.equal(timers.size, 0);
  target.isSecureContext = false;
  assert.doesNotThrow(() => listenForSmsCode(() => assert.fail("Unexpected code"))());
  assert.equal(timers.size, 0);
  target.isSecureContext = true;
  replace(t, "navigator", { credentials: { get: () => Promise.reject(new DOMException("Denied", "NotAllowedError")) } });
  listenForSmsCode(() => assert.fail("Unexpected code"));
  await Promise.resolve(); await Promise.resolve();
  assert.equal(timers.size, 0);
  replace(t, "navigator", { credentials: { get: () => Promise.resolve({ code: "12345<script>" }) } });
  listenForSmsCode(() => assert.fail("Unexpected code"));
  await Promise.resolve();
  assert.equal(timers.size, 0);
});

test("blocked optional browser APIs cannot throw during app startup", t => {
  replace(t, "navigator", Object.defineProperty({}, "serviceWorker", {
    get() { throw new DOMException("Blocked", "SecurityError"); },
  }));
  replace(t, "BroadcastChannel", class { constructor() { throw new DOMException("Blocked", "SecurityError"); } });
  assert.equal(getServiceWorkerContainer(), null);
  assert.equal(openSessionChannel(), null);
  replace(t, "navigator", {});
  replace(t, "BroadcastChannel", undefined);
  assert.equal(getServiceWorkerContainer(), null);
  assert.equal(openSessionChannel(), null);
});
