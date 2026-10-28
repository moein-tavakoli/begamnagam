import assert from "node:assert/strict";
import { test } from "node:test";
import { managementActions, type ManagementRow } from "../lib/management.ts";

test("management row actions respect individual capabilities and current record state", () => {
  const account: ManagementRow = { record_id: "17", suspended: false, direct_message_tone: false };
  assert.deepEqual(managementActions("accounts", account, []), []);
  assert.deepEqual(managementActions("accounts", account, ["suspend_account"]).map(action => action.name), ["suspend"]);
  assert.equal(managementActions("accounts", { ...account, suspended: true }, ["suspend_account"])[0].name, "unsuspend");
  const tone = managementActions("accounts", account, ["manage_message_tone"])[0];
  assert.deepEqual(tone, { name: "tone", label: "لحن صریح", object_id: "17", value: true });
  assert.deepEqual(managementActions("refunds", { record_id: "r1", status: "refunded" }, ["confirm_refund"]), []);
  assert.deepEqual(managementActions("alerts", { record_id: "a1", acknowledged_by_id: 1 }, ["view_operations"]), []);
});

test("report viewing and triage stay separate and no order replay action is exposed", () => {
  const report: ManagementRow = { record_id: "case1", status: "open" };
  assert.deepEqual(managementActions("reports", report, []).map(action => action.name), ["review"]);
  assert.deepEqual(managementActions("reports", report, ["triage_report"]).map(action => action.name), ["review", "close_report", "hold_report"]);
  assert.ok(!managementActions("reports", { ...report, status: "closed" }, ["triage_report"]).some(action => action.name === "close_report"));
  assert.deepEqual(managementActions("orders", { record_id: "order1", status: "unknown" }, ["operate_safety", "confirm_refund"]), []);
  assert.deepEqual(managementActions("orders", { record_id: "order1" }, ["view_private_message_text"]).map(action => action.name), ["message_texts"]);
});
