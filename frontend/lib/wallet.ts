export type WalletTopup = { id: string; amount_toman: number; status: string; created_at: string; redirect_url?: string | null };
export type WalletState = {
  balance_toman: string; wallet_enabled: boolean; gateway_enabled: boolean;
  gateway_configured: boolean; wallet_terms_version: string; withdrawable: false;
  entries: { id: string; kind: string; amount_toman: number; balance_after_toman: string; created_at: string; order_id?: string; purchase_id?: string }[];
  topups: WalletTopup[];
};
export function walletToman(value: string | number): string {
  try {
    const text = String(value);
    if (!/^\d+$/.test(text)) return '—';
    return `${new Intl.NumberFormat('fa-IR').format(BigInt(text))} تومان`;
  } catch { return '—'; }
}
export const walletEntryLabel = (kind: string) => ({ topup: 'شارژ کیف پول', order_debit: 'هزینهٔ ارسال پیام', order_return: 'برگشت هزینهٔ ارسال', package_debit: 'خرید بستهٔ پیام', payment_return: 'برگشت پرداخت به کیف پول' }[kind] || 'تراکنش کیف پول');
export const topupLabel = (status: string) => ({ credited: 'شارژ تأیید شد', failed: 'پرداخت تأیید نشد', unknown: 'نیازمند بررسی؛ دوباره پرداخت نکن', pending: 'در انتظار تأیید پرداخت', created: 'درخواست ثبت شد' }[status] || 'در حال بررسی');
