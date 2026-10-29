export type ManagementSession = {
  authenticated: boolean;
  session_identity?: string;
  username?: string;
  permissions?: string[];
  resources?: { key: string; title: string }[];
};
export type ManagementRow = Record<string, unknown> & { record_id: string };
export type ManagementRecords = {
  title: string; columns: { key: string; label: string; type: string }[];
  rows: ManagementRow[]; total: number; page: number; page_size: number; statuses: [string, string][];
};
export type LimitRule = { scope: string; label: string; protected: boolean; enabled: boolean; maximum: number; window_seconds: number; revision: number };
export type LimitSettings = {
  gateway_problem?: string;
  values: Record<string, number | boolean>; revision: number;
  sections: { title: string; fields: { key: string; label: string; help: string; type: string; min?: number; max?: number | null }[] }[];
  requests: LimitRule[];
};
export type ManagementDashboard = {
  operations: Record<string, number | boolean | null>;
  totals: Record<string, number>;
  environment: { demo: boolean; sms: string; otp: string; payment: string; paid_enabled: boolean };
  updated_at: string;
};

const states: Record<string, string> = {
  awaiting_transfer: "منتظر واریز", awaiting_review: "منتظر بررسی رسید", pending: "در انتظار", queued: "در صف", submitting: "در حال ارسال", accepted: "پذیرفته‌شده",
  delivered: "رسیده به گیرنده", delivered_demo: "تحویل آزمایشی", failed: "ناموفق", unknown: "نیازمند تطبیق",
  suppressed: "متوقف‌شده", expired: "منقضی", not_ready: "آماده نشده", done: "انجام‌شده", sent: "ارسال‌شده",
  open: "باز", closed: "بسته", approved: "تأییدشده", rejected: "ردشده", allowed: "مجاز",
  awaiting_payment: "منتظر پرداخت", paid: "پرداخت‌شده", cancelled: "لغوشده", verified: "تأییدشده",
  created: "ایجادشده", requested: "درخواست‌شده", processing: "در حال بررسی", refunded: "مستردشده",
  purchase: "خرید بسته", reserve: "رزرو ارسال", release: "برگشت اعتبار",
  payment: "دریافت", refund: "استرداد", critical: "بحرانی", high: "مهم", warning: "نیازمند توجه",
};
export const managementState = (value: unknown) => states[String(value)] || String(value);
export const managementNumber = (value: unknown) => typeof value === "number" ? value.toLocaleString("fa-IR") : "—";
export function managementDate(value: unknown): string {
  if (!value) return "—";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "short", ...(String(value).length > 10 ? { timeStyle: "short" as const } : {}), timeZone: "Asia/Tehran" }).format(date);
}
export type ManagementAction = { name: string; label: string; object_id: string; value?: boolean; manualPayment?: { amount_toman: number }; accountLimits?: { sender_daily_limit: number | null; rewrite_daily_limit: number | null } };
export function managementActions(resource: string, row: ManagementRow, permissions: string[]): ManagementAction[] {
  const actions: ManagementAction[] = [];
  const add = (name: string, label: string, value?: boolean) => actions.push({ name, label, object_id: row.record_id, value });
  if (resource === "accounts") {
    if (permissions.includes("approve_manual_payments")) add("grant_package", "فعال‌سازی بسته با رسید بانکی");
    if (permissions.includes('manage_account_limits')) actions.push({ name: 'account_limits', label: 'سقف اختصاصی', object_id: row.record_id,
      accountLimits: { sender_daily_limit: typeof row.sender_daily_limit === 'number' ? row.sender_daily_limit : null,
        rewrite_daily_limit: typeof row.rewrite_daily_limit === 'number' ? row.rewrite_daily_limit : null } });
    if (permissions.includes("suspend_account")) add(row.suspended ? "unsuspend" : "suspend", row.suspended ? "رفع تعلیق" : "تعلیق حساب");
    if (permissions.includes("manage_message_tone")) add("tone", row.direct_message_tone ? "لحن معمولی" : "لحن صریح", !row.direct_message_tone);
  }
  if (resource === 'manual-payments' && permissions.includes('approve_manual_payments') && ['awaiting_transfer','awaiting_review'].includes(String(row.status))) {
    actions.push({name:'approve_card',label:'تأیید و فعال‌سازی بسته',object_id:row.record_id,manualPayment:{amount_toman:Number(row.purchase__amount_toman)}});
    add('reject_card','رد رسید با دلیل');
  }
  if (resource === "orders" && permissions.includes("view_private_message_text")) add("message_texts", "مشاهدهٔ متن‌ها");
  if (resource === "reports") {
    add("review", "بررسی پرونده");
    if (permissions.includes("triage_report")) {
      if (row.status !== "closed") add("close_report", "بستن گزارش");
      add("hold_report", "نگهداری ۳۰ روزه");
    }
  }
  if (resource === "alerts" && permissions.includes("view_operations") && !row.acknowledged_by_id) add("ack_alert", "ثبت بررسی");
  if (resource === "refunds" && permissions.includes("confirm_refund") && row.status !== "refunded") add("confirm_refund", "ثبت بازپرداخت مستند");
  return actions;
}
