import { test } from "node:test";
import assert from "node:assert/strict";
import { pickRecipientNumbers } from "../lib/contact-picker.ts";

test("request only phone numbers for one contact", async () => {
  const numbers = await pickRecipientNumbers({
    async select(properties, options) {
      assert.deepEqual(properties, ["tel"]);
      assert.deepEqual(options, { multiple: false });
      return [{ tel: ["+۹۸ (۹۱۲) ۳۴۵-۶۷۸۹"] }];
    },
  });

  assert.deepEqual(numbers, ["09123456789"]);
});

test("keep distinct valid mobile numbers in the contact's order", async () => {
  const numbers = await pickRecipientNumbers({
    async select() {
      return [{ tel: [
        "۰۹۳۵۱۲۳۴۵۶۷",
        "091234567890",
        "00989351234567",
        "02112345678",
        "+971501234567",
        "09123456789 ext 1",
        "٠٩١٢٣٤٥٦٧٨٩",
      ] }];
    },
  });

  assert.deepEqual(numbers, ["09351234567", "09123456789"]);
});

test("closing the picker without a contact returns cancellation", async () => {
  assert.equal(await pickRecipientNumbers({ async select() { return []; } }), null);
});

test("a contact without shared mobile numbers returns an empty list", async () => {
  assert.deepEqual(await pickRecipientNumbers({ async select() { return [{}]; } }), []);
});
