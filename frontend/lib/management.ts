export { managementExplanation, managementDisplayValue } from './management-copy.ts';
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
export type ManagementRecordFilter = { page: number; page_size: number; query: string; status: string };
export const managementPageSizes = [10, 25, 50, 100] as const;
export function managementVisibleColumns(columns: ManagementRecords['columns']): ManagementRecords['columns'] {
  return columns.filter(col => col.type !== 'id' && col.key !== 'id' && col.key !== 'record_id'
    && !col.key.endsWith('_id') && !col.label.includes('شناسه'));
}
export function managementGridPage(current: ManagementRecordFilter, model: {page:number;pageSize:number}): ManagementRecordFilter {
  const page=model.pageSize === current.page_size ? model.page + 1 : 1;
  return page===current.page && model.pageSize===current.page_size ? current : {...current,page,page_size:model.pageSize};
}
export function managementGridRange({from,to,count}:{from:number;to:number;count:number}): string {
  const number = (n:number) => n.toLocaleString('fa-IR');
  return `${number(from)} تا ${number(to)} از ${number(count)} سطر`;
}
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
  archived: "بایگانی‌شده", blocked: "مسدود", unavailable: "در دسترس نیست",
  credited: "اعتبار افزوده شد", wallet_returned: "برگشت به کیف پول", sending: "در حال ارسال", simulated: "ثبت آزمایشی",
  topup: "شارژ کیف پول", order_debit: "برداشت هزینهٔ پیام", order_return: "برگشت هزینهٔ پیام", package_debit: "برداشت خرید بسته", payment_return: "برگشت پرداخت",
};
export const managementState = (value: unknown) => value ? states[String(value)] || "وضعیت ثبت‌شده نیاز به بررسی دارد" : "—";
export const managementNumber = (value: unknown) => typeof value === "number" ? value.toLocaleString("fa-IR") : "—";
export function managementDate(value: unknown): string {
  if (!value) return "—";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "short", ...(String(value).length > 10 ? { timeStyle: "short" as const } : {}), timeZone: "Asia/Tehran" }).format(date);
}
export type ManagementAction = { name: string; label: string; object_id: string; value?: boolean; manualPayment?: { amount_toman: number }; userId?: string; accountLimits?: { sender_daily_limit: number | null; rewrite_daily_limit: number | null } };
export function managementActions(resource: string, row: ManagementRow, permissions: string[]): ManagementAction[] {
  const actions: ManagementAction[] = [];
  const add = (name: string, label: string, value?: boolean) => actions.push({ name, label, object_id: row.record_id, value });
  if (resource === "accounts") {
    if (permissions.includes("manage_free_sending")) add("free_sending", row.unlimited_free_sends ? "قطع ارسال رایگان نامحدود" : "فعال‌سازی ارسال رایگان نامحدود", !row.unlimited_free_sends);
    if (permissions.includes("approve_manual_payments")) add("grant_package", "فعال‌سازی بسته با رسید بانکی");
    if (permissions.includes('manage_account_limits')) actions.push({ name: 'account_limits', label: 'سقف اختصاصی', object_id: row.record_id,
      accountLimits: { sender_daily_limit: typeof row.sender_daily_limit === 'number' ? row.sender_daily_limit : null,
        rewrite_daily_limit: typeof row.rewrite_daily_limit === 'number' ? row.rewrite_daily_limit : null } });
    if (permissions.includes("suspend_account")) add(row.suspended ? "unsuspend" : "suspend", row.suspended ? "رفع تعلیق" : "تعلیق حساب");
    if (permissions.includes("manage_message_tone")) add("tone", row.direct_message_tone ? "لحن معمولی" : "لحن صریح", !row.direct_message_tone);
  }
  if (resource === 'manual-payments' && permissions.includes('approve_manual_payments') && ['awaiting_transfer','awaiting_review'].includes(String(row.status))) {
    actions.push({name:'approve_card',label:'تأیید و فعال‌سازی بسته',object_id:row.record_id,manualPayment:{amount_toman:Number(row.purchase__amount_toman)}});
    add('reject_card','رد رسید');
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

export function managementHref(resource: string): string {
  return resource === "dashboard" ? "/manage" : `/manage/${resource === "accounts" ? "users" : resource}`;
}
export function managementUserHref(id: string, section?: "messages" | "invitations"): string {
  return `/manage/users/${encodeURIComponent(id)}${section ? `?section=${section}` : ""}`;
}
export function managementRoute(pathname: string): { resource: string; userId?: string } {
  const [, , resource, userId] = pathname.split("/");
  return { resource: !resource ? "dashboard" : resource === "users" ? "accounts" : resource,
    ...(resource === "users" && userId ? { userId } : {}) };
}
export function managementShowsBalances(resource: string, permissions: string[]): boolean {
  return resource === 'dashboard' && permissions.includes('view_operations');
}
export function managementBreadcrumbs(session: ManagementSession, pathname: string): { title: string; href?: string }[] {
  const route = managementRoute(pathname);
  const title = managementNavigation(session).find(item => item.key === route.resource)?.title || session.resources?.find(item => item.key === route.resource)?.title || 'بخش مدیریت';
  if (route.resource === 'staff' && pathname.endsWith('/roles')) return [{title:'مدیریت',href:'/manage'},{title:'کارمندان سامانه',href:'/manage/staff'},{title:'نقش‌ها'}];
  if (route.resource === 'dashboard') return [{ title: 'مدیریت', href: '/manage' }, { title: 'نمای کلی' }];
  return [{ title: 'مدیریت', href: '/manage' }, ...(route.userId ? [{ title:'کاربران', href:'/manage/users' }, { title:`پروندهٔ کاربر ${Number(route.userId).toLocaleString('fa-IR')}` }] : [{title}])];
}
export function managementNavigation(session: ManagementSession): { key: string; title: string }[] {
  if (!session.authenticated) return [];
  const permissions = session.permissions || [], resources = session.resources || [];
  return [
    ...(permissions.includes("view_operations") ? [{ key: "dashboard", title: "نمای کلی" }] : []),
    ...(resources.some(item => item.key === "accounts") ? [{ key: "accounts", title: "کاربران" }] : []),
    ...(permissions.includes("view_operations") ? [{ key: "monitoring", title: "مانیتورینگ" }] : []),
    ...(resources.some(item => item.key === "blacklist") ? [{ key: "blacklist", title: "لیست سیاه" }] : []),
    ...(permissions.includes("support_chat") ? [{ key: "support", title: "پشتیبانی" }] : []),
    ...(permissions.includes("manage_staff") ? [{ key: "staff", title: "کارمندان سامانه" }] : []),
    ...(permissions.includes("view_changelog") ? [{ key: "changelog", title: "تاریخچهٔ تغییرات" }] : []),
    ...resources.filter(item => item.key !== "accounts" && item.key !== "blacklist" && (!resources.some(resource => resource.key === "accounts") || !["orders", "invitations", "invitation-deliveries", "invitation-sends"].includes(item.key))),
    ...([ ["manage_site_limits", "limits", "تنظیمات سایت"], ["manage_message_packages", "packages", "بسته‌های پیام"],
      ["manage_message_examples", "examples", "پیام‌های نمونه"], ["manage_manual_payments", "manual-settings", "کارت و دریافت رسید"],
      ["manage_ai", "ai", "هوش مصنوعی"] ].filter(([permission]) => permissions.includes(permission)).map(([, key, title]) => ({ key, title }))),
  ];
}
export function managementLanding(session:ManagementSession):string|null {
  const first=managementNavigation(session)[0];
  return first?managementHref(first.key):null;
}
const auditReasons: Record<string, string> = {
  suspend: "تعلیق کاربر از پنل مدیریت", unsuspend: "رفع تعلیق کاربر از پنل مدیریت", tone: "تغییر لحن کاربر از پنل مدیریت",
  free_sending: "تغییر ارسال رایگان کاربر از پنل مدیریت", account_limits: "تغییر سقف اختصاصی کاربر از پنل مدیریت",
  halt: "توقف ارسال از پنل مدیریت", resume: "ازسرگیری ارسال از پنل مدیریت", review: "بررسی پرونده از پنل مدیریت",
  message_texts: "بررسی متن پیام از پنل مدیریت", attempt_texts: "بررسی متن تلاش پیام از پنل مدیریت",
  close_report: "بستن گزارش از پنل مدیریت", hold_report: "نگهداری گزارش از پنل مدیریت", ack_alert: "بررسی هشدار از پنل مدیریت",
  confirm_refund: "ثبت سند بازپرداخت از پنل مدیریت", grant_package: "فعال‌سازی بسته پس از بررسی واریز بانکی", approve_card: "تأیید رسید پس از بررسی واریز بانکی", reject_card: "رسید بانکی تأیید نشد.",
  limits: "ذخیره تنظیمات سایت از پنل مدیریت", request_limits: "ذخیره کنترل درخواست از پنل مدیریت", ai: "ذخیره تنظیمات هوش مصنوعی از پنل مدیریت",
  manual_settings: "ذخیره تنظیمات کارت و رسید از پنل مدیریت", packages: "ذخیره بسته پیام از پنل مدیریت",
  example_save: "ذخیره پیام نمونه از پنل مدیریت", example_delete: "حذف پیام نمونه از پنل مدیریت",
};
export const managementReason = (action: string): string => auditReasons[action] || "ثبت اقدام از پنل مدیریت";

export type ManagementActivity = {
  account: { id: number; phone: string; phone_masked: string; suspended: boolean };
  section: "messages" | "invitations";
  rows: (ManagementRow & { kind: "order" | "attempt" | "moderation" | "invitation"; id: string; created_at: string; status: string; reason_code?: string; phone?: string; order_id?: string })[];
  page: number; total: number; page_size: number;
};
