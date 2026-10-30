import { latinInputDigits } from "./input-digits.ts";
export const latinDigits = latinInputDigits;

export function normalizePhone(value: string): string {
  const digits = latinDigits(value).replace(/[\s()-]/g, "");
  if (digits.startsWith("+98")) return `0${digits.slice(3)}`;
  if (digits.startsWith("0098")) return `0${digits.slice(4)}`;
  if (digits.startsWith("98") && digits.length === 12)
    return `0${digits.slice(2)}`;
  return digits;
}

export function phoneInput(value: string): string {
  return normalizePhone(value).replace(/[^0-9]/g, "").slice(0, 11);
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
  accepted: "پذیرفته‌شده توسط سرویس‌دهنده",
  unknown: "در حال بررسی نتیجه؛ دوباره ارسال نکن",
  delivered: "رسیده به گیرنده",
  failed: "ارسال ناموفق",
  blocked: "ارسال متوقف شد",
  cancelled: "لغو شده",
  refunded: "مبلغ برگشت داده شد",
};

export function statusLabel(status: string): string {
  return statusLabels[status] || "در حال بررسی";
}

export function isPending(status: string): boolean {
  return ["paid", "queued", "processing", "sending", "accepted", "unknown"].includes(status);
}
