import assert from "node:assert/strict";
import { test } from "node:test";
import { canonicalInput, latinInputDigits } from "../lib/input-digits.ts";

test("Persian, Arabic and full-width digits keep leading zero and surrounding text", () => {
  assert.equal(latinInputDigits("پیگیری ۰۰١۲３"), "پیگیری 00123");
});

test("nested outgoing inputs use ASCII without mutating UI state or JSON types", () => {
  const data = { text: "رسید ۱۲", values: ["۰۱۲۳", { reference: "BANK٠٠١" }], amount: 1200, enabled: false, optional: null };
  assert.deepEqual(canonicalInput(data), { text: "رسید 12", values: ["0123", { reference: "BANK001" }], amount: 1200, enabled: false, optional: null });
  assert.equal(data.text, "رسید ۱۲");
});

test("passwords, credentials and signed identifiers remain exact", () => {
  const data = Object.fromEntries(["username", "password", "csrfmiddlewaretoken", "alternative_token", "preview_id", "client_key", "terms_version", "signature", "authority"].map(key => [key, "Ab۰۱۲٣"]));
  assert.deepEqual(canonicalInput(data), data);
});

test("dates retain their normal JSON serialization", () => {
  const date = new Date("2026-10-29T12:34:56Z");
  assert.equal(JSON.stringify(canonicalInput({ date })), JSON.stringify({ date }));
});
