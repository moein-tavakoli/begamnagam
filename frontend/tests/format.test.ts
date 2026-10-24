import { test } from "node:test";
import assert from "node:assert/strict";
import {
  latinDigits,
  normalizePhone,
  validPhone,
  isPending,
  statusLabel,
} from "../lib/format.ts";

test("Iranian phone input accepts Persian/Arabic digits and international formats", () => {
  for (const phone of [
    "۰۹۱۲۳۴۵۶۷۸۹",
    "٠٩١٢٣٤٥٦٧٨٩",
    "+98 912 345 6789",
    "00989123456789",
    "989123456789",
  ]) {
    assert.equal(normalizePhone(phone), "09123456789");
    assert.equal(validPhone(phone), true);
  }
  assert.equal(latinDigits("۱۲٣۴"), "1234");
});

test("invalid recipients are never silently repaired into another number", () => {
  for (const phone of [
    "0912345678",
    "091234567890",
    "+971501234567",
    "02112345678",
    "0912letters",
    "",
  ]) {
    assert.equal(validPhone(phone), false);
  }
});

test("only pending orders trigger polling and unknown status makes no delivery claim", () => {
  assert.equal(isPending("queued"), true);
  assert.equal(isPending("simulated"), false);
  assert.equal(isPending("delivered_demo"), false);
  assert.equal(statusLabel("delivered_demo"), "ارسال شبیه‌سازی شد");
  assert.equal(isPending("failed"), false);
  assert.equal(statusLabel("unknown-provider-response"), "در حال بررسی");
});
