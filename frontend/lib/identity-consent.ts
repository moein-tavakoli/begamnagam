export const anonymityNotice = 'شمارهٔ حسابت پنهان می‌مونه؛ فقط با درخواست طرف مقابل و تأیید خودت در پروفایل سایت، شماره‌ات برای همون فرد قابل مشاهده می‌شه.';
export const identityRequestNotice = 'درخواست می‌دی که بدونی فرستنده کیه. فقط اگر خودش در پروفایل سایت تأیید کنه، شمارهٔ موبایلش در پروفایل تو دیده می‌شه؛ تا قبل از تأیید، شماره پنهانه.';
export const revocationNotice = '«ناشناس شدن» نمایش بعدی شماره را فقط برای همین فرد قطع می‌کنه. شماره‌ای که قبلاً دیده یا کپی شده قابل پس‌گرفتن نیست.';
export const identitySettingsChanged = 'identity-settings-changed';

export type IdentityConsent = {
  id: string;
  status: 'pending' | 'approved' | 'declined' | 'revoked';
  revision: number;
  message_created_at: string | null;
  message_excerpt?: string;
  requested_at?: string;
};
export type IdentityRequests = {results: IdentityConsent[]; count: number; page: number};
export const identityStatusLabels: Record<IdentityConsent['status'], string> = {
  pending: 'منتظر تأیید', approved: 'نمایش شماره مجاز است', declined: 'درخواست رد شده', revoked: 'ناشناس',
};
