import assert from "node:assert/strict";
import { test } from "node:test";
import { invitationDeliveryLabel, resendExplanation, type Invitation } from "../lib/invitations.ts";

test("invitation outcomes distinguish delivery, simulation and verified registration", () => {
  assert.notEqual(invitationDeliveryLabel("accepted"), invitationDeliveryLabel("delivered"));
  assert.match(invitationDeliveryLabel("delivered_demo"), /آزمایشی/);
  assert.match(invitationDeliveryLabel("unknown"), /بررسی/);
  assert.equal(invitationDeliveryLabel("internal_error"), "در حال بررسی");
});
test("resend guidance explains registration, exhaustion, uncertainty and cooldown", () => {
  const item = { status: "waiting", sends_remaining: 2, delivery_status: "delivered", can_resend: true } as Invitation;
  assert.equal(resendExplanation(item), "");
  assert.match(resendExplanation({...item, status: "registered"}), /ثبت‌نام/);
  assert.match(resendExplanation({...item, status: "expired"}), /مهلت/);
  assert.match(resendExplanation({...item, sends_remaining: 0}), /سقف تعداد/);
  assert.match(resendExplanation({...item, delivery_status: "unknown"}), /نتیجه/);
  assert.match(resendExplanation({...item, can_resend: false}), /۲۴ ساعت/);
  assert.match(resendExplanation({...item, can_resend: false, cooldown_hours: 2}), /۲ ساعت/);
  assert.equal(resendExplanation({...item, sends_remaining: null, max_sends: null, cooldown_hours: 0}), "");
});
