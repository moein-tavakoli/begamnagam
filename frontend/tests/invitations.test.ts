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
  assert.match(resendExplanation({...item, status: "expired"}), /۳۰روزه/);
  assert.match(resendExplanation({...item, sends_remaining: 0}), /هر سه/);
  assert.match(resendExplanation({...item, delivery_status: "unknown"}), /نتیجه/);
  assert.match(resendExplanation({...item, can_resend: false}), /۲۴ ساعت/);
});
