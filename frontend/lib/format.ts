export function latinDigits(value: string): string {
  return value
    .replace(/[۰-۹]/g, (digit) => String(digit.charCodeAt(0) - 1776))
    .replace(/[٠-٩]/g, (digit) => String(digit.charCodeAt(0) - 1632));
}

export function normalizePhone(value: string): string {
  const digits = latinDigits(value).replace(/[\s()-]/g, "");
  if (digits.startsWith("+98")) return `0${digits.slice(3)}`;
  if (digits.startsWith("0098")) return `0${digits.slice(4)}`;
  if (digits.startsWith("98") && digits.length === 12)
    return `0${digits.slice(2)}`;
  return digits;
}

export function validPhone(value: string): boolean {
  return /^09\d{9}$/.test(normalizePhone(value));
}

export function toman(amount: number): string {
  return `${new Intl.NumberFormat("fa-IR").format(amount)} تومان`;
}

export const statusLabels: Record<string, string> = {
  awaiting_payment: "منتظر پرداخت",
  pending_payment: "منتظر پرداخت",
  created: "ایجاد شده",
  paid: "پرداخت ثبت شد",
  queued: "در صف ارسال",
  processing: "در حال پردازش",
  sending: "در حال ارسال",
  sent: "تحویل به پنل پیامک",
  simulated: "ارسال آزمایشی ثبت شد",
  delivered_demo: "ارسال شبیه‌سازی شد",
  delivered: "تحویل به اپراتور",
  failed: "ارسال ناموفق",
  blocked: "ارسال متوقف شد",
  cancelled: "لغو شده",
  refunded: "مبلغ برگشت داده شد",
};

export function statusLabel(status: string): string {
  return statusLabels[status] || "در حال بررسی";
}

export function isPending(status: string): boolean {
  return ["paid", "queued", "processing", "sending"].includes(status);
}
