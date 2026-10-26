export type Invitation = {
  id: string;
  phone_masked: string;
  created_at: string;
  registered_at: string | null;
  status: "registered" | "expired" | "waiting";
  send_count: number;
  sends_remaining: number;
  can_resend: boolean;
  next_send_at: string;
  delivery_status: string;
  reason: string | null;
  reward_credits: number;
  reward_pending: boolean;
  sends: { number: number; status: string; created_at: string }[];
};

export type InvitationList = {
  results: Invitation[];
  next_offset: number | null;
  total: number;
  registered: number;
  earned_credits: number;
  daily_remaining: number;
  consent_version: string;
};

export function invitationDeliveryLabel(status: string): string {
  return ({ pending: "در صف ارسال", submitting: "در حال بررسی ارسال", unknown: "نتیجه در حال بررسی",
    accepted: "تحویل به سرویس پیامک", delivered: "رسیده به مخاطب", delivered_demo: "ارسال آزمایشی ثبت شد",
    cancelled: "ارسال متوقف شد", failed: "ارسال انجام نشد" } as Record<string, string>)[status] || "در حال بررسی";
}

export function resendExplanation(item: Invitation): string {
  if (item.status === "registered") return "ثبت‌نام انجام شده؛ دعوت دیگری لازم نیست.";
  if (item.status === "expired") return "مهلت ۳۰روزهٔ دعوت تمام شده است.";
  if (item.sends_remaining === 0) return "هر سه نوبت درخواست دعوت استفاده شده است.";
  if (["pending", "submitting", "unknown"].includes(item.delivery_status)) return "ابتدا نتیجهٔ درخواست قبلی باید مشخص شود.";
  if (!item.can_resend) return "درخواست بعدی پس از ۲۴ ساعت از درخواست قبلی فعال می‌شود.";
  return "";
}
