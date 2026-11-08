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

import * as management from "../lib/management.ts";

test("management routes are stable deep links and accounts keep their API resource", () => {
  assert.equal(management.managementHref("dashboard"), "/manage");
  assert.equal(management.managementHref("accounts"), "/manage/users");
  assert.equal(management.managementHref("support"), "/manage/support");
  assert.deepEqual(management.managementRoute("/manage/users/17"), { resource: "accounts", userId: "17" });
  assert.deepEqual(management.managementRoute("/manage/accounts"), { resource: "accounts" });
  assert.deepEqual(management.managementRoute("/manage"), { resource: "dashboard" });
});

test("users follow overview and user activity leaves the global menu", () => {
  const navigation = management.managementNavigation({ authenticated: true, permissions: ["view_operations"], resources: [
    { key: "orders", title: "پیام‌ها" }, { key: "accounts", title: "حساب‌ها" }, { key: "invitations", title: "دعوت‌ها" }, { key: "alerts", title: "هشدارها" },
  ] });
  assert.deepEqual(navigation.slice(0, 2), [{ key: "dashboard", title: "نمای کلی" }, { key: "accounts", title: "کاربران" }]);
  assert.ok(!navigation.some(item => ["orders", "invitations"].includes(item.key)));
  assert.equal(management.managementUserHref("17", "invitations"), "/manage/users/17?section=invitations");
});

test("management audit reasons are fixed and specific to the selected action", () => {
  assert.ok(management.managementReason("suspend").length >= 3);
  assert.notEqual(management.managementReason("suspend"), management.managementReason("unsuspend"));
  assert.equal(management.managementReason("reject_card"), "رسید بانکی تأیید نشد.");
});

import { readFileSync } from "node:fs";

test("management forms keep audit context automatic while bank proof remains mandatory", () => {
  for (const file of ["management-console", "ai-settings", "manual-payment-settings", "manual-payment-dialog", "package-settings", "example-settings"]) {
    const source = readFileSync(new URL(`../components/${file}.tsx`, import.meta.url), "utf8");
    assert.doesNotMatch(source, /<(?:input|textarea)[^>]*name=["']reason["']/);
    assert.match(source, /reason:\s*managementReason\(/);
  }
  const payment = readFileSync(new URL("../components/manual-payment-dialog.tsx", import.meta.url), "utf8");
  for (const field of ["bank_reference", "paid_date", "bank_verified", "amount_toman"]) {
    assert.match(payment, new RegExp(`name="${field}"[^>]*required`));
  }
});


test('staff without user access retain authorized order and invitation navigation', () => {
  const resources = [{key:'orders',title:'پیام‌ها و سفارش‌ها'},{key:'invitations',title:'دعوت‌ها'}];
  const nav = management.managementNavigation({authenticated:true,permissions:[],resources});
  assert.ok(nav.some(item => item.key === 'orders'));
  assert.ok(nav.some(item => item.key === 'invitations'));
  assert.equal(nav.some(item => item.key === 'accounts'), false);
});


test('blacklist has its own route and no consent-override row actions', () => {
  assert.equal(management.managementHref('blacklist'), '/manage/blacklist');
  const nav = management.managementNavigation({authenticated:true,resources:[{key:'accounts',title:'کاربران'},{key:'blacklist',title:'لیست سیاه'}]});
  assert.equal(nav.filter(item => item.key === 'blacklist').length, 1);
  assert.deepEqual(managementActions('blacklist', {record_id:'opaque-id',blocked:true}, ['operate_safety','view_recipientstate','view_account']), []);
});

test('moderation causes explain the actual rejection in Persian', () => {
  assert.equal(management.managementExplanation('draft_without_intent'), 'پس از حذف عبارت‌های نامناسب، درخواست یا احساس مشخصی در متن باقی نمانده است.');
  assert.equal(management.managementExplanation('unsafe_or_changed_intent'), 'بازبین نتوانسته هم ایمن‌بودن متن و هم حفظ منظور اولیه را تأیید کند.');
  assert.match(management.managementExplanation('contact_details'), /اطلاعات تماس/);
  assert.match(management.managementExplanation('queue_expired'), /صف/);
  assert.match(management.managementExplanation('ai_unavailable'), /هوش مصنوعی/);
});

test('unknown machine codes have a Persian fallback without leaking raw codes', () => {
  assert.equal(management.managementExplanation('new_vendor_error'), 'توضیح فارسی این علت هنوز ثبت نشده است؛ جزئیات فنی باید بررسی شود.');
  assert.equal(management.managementExplanation(''), 'علتی ثبت نشده است.');
  assert.equal(management.managementState('new_vendor_state'), 'وضعیت ثبت‌شده نیاز به بررسی دارد');
});

test('translations are field-aware and never rewrite identifiers or user content', () => {
  assert.equal(management.managementDisplayValue('reason_code', 'draft_without_intent'), management.managementExplanation('draft_without_intent'));
  assert.equal(management.managementDisplayValue('last_error_code', 'submission_uncertain'), management.managementExplanation('submission_uncertain'));
  assert.equal(management.managementDisplayValue('payment_mode', 'free'), 'رایگان');
  assert.equal(management.managementDisplayValue('category', 'custom'), 'متن دلخواه');
  assert.equal(management.managementDisplayValue('original_text', 'draft_without_intent'), 'draft_without_intent');
  assert.equal(management.managementDisplayValue('object_id', 'unknown'), 'unknown');
  assert.equal(management.managementDisplayValue('reason', 'متن ثبت‌شدهٔ مدیر'), 'متن ثبت‌شدهٔ مدیر');
});

test('financial movement labels distinguish every current wallet movement', () => {
  const kinds = ['topup', 'order_debit', 'order_return', 'package_debit', 'payment_return'];
  const labels = kinds.map(management.managementState);
  assert.equal(new Set(labels).size, kinds.length);
  labels.forEach(label => assert.doesNotMatch(label, /نیاز به بررسی|[a-z_]/));
  assert.equal(management.managementDisplayValue('payment_mode', 'credit_live'), 'اعتبار بستهٔ واقعی');
  assert.equal(management.managementDisplayValue('payment_mode', 'credit_demo'), 'اعتبار بستهٔ آزمایشی');
  assert.equal(management.managementDisplayValue('purchase__environment', 'live'), 'واقعی');
});

test('actual backend audit actions retain distinct Persian meaning', () => {
  const actions = ['message_text_viewed', 'message_attempt_text_viewed', 'report_viewed', 'approve_manual_payment', 'reject_manual_payment', 'update_site_limits', 'update_ai_configuration', 'update_message_package', 'account_send_options'];
  const labels = actions.map(action => management.managementDisplayValue('action', action));
  assert.equal(new Set(labels).size, actions.length);
  labels.forEach(label => assert.doesNotMatch(String(label), /اقدام مدیریتی ثبت‌شده|[a-z_]/));
});

test('service balances mount only on an authorized overview', () => {
  assert.equal(management.managementShowsBalances('dashboard', ['view_operations']), true);
  for (const resource of ['accounts','blacklist','support','limits','ai','orders']) assert.equal(management.managementShowsBalances(resource, ['view_operations']), false);
  assert.equal(management.managementShowsBalances('dashboard', []), false);
});

test('breadcrumbs preserve the user route hierarchy without exposing phone data', () => {
  const session = {authenticated:true,permissions:['view_operations'],resources:[{key:'accounts',title:'کاربران'}]};
  assert.deepEqual(management.managementBreadcrumbs(session,'/manage/users/17'), [
    {title:'مدیریت',href:'/manage'}, {title:'کاربران',href:'/manage/users'}, {title:'پروندهٔ کاربر ۱۷'},
  ]);
});

test('Persian release history navigation is limited to authenticated management sessions', () => {
  assert.equal(management.managementNavigation({authenticated:false}).some(item=>item.key==='changelog'),false);
  assert.equal(management.managementNavigation({authenticated:true}).find(item=>item.key==='changelog')?.title,'تاریخچهٔ تغییرات');
  assert.equal(management.managementHref('changelog'),'/manage/changelog');
});
