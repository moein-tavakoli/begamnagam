import type { CreditPurchase, ReceiptChannel } from './api';

export const openPurchase = (status: string) => ['created', 'pending', 'unknown', 'verified', 'awaiting_transfer', 'awaiting_review'].includes(status);
export function safeReceiptChannels(channels: ReceiptChannel[] = []) {
  return channels.filter(channel => (channel.name === 'bale' && /^https:\/\/ble\.ir\/[A-Za-z][A-Za-z0-9_]{4,31}$/.test(channel.url)) || (channel.name === 'telegram' && /^https:\/\/t\.me\/[A-Za-z][A-Za-z0-9_]{4,31}$/.test(channel.url)));
}
export function receiptText(purchase: Pick<CreditPurchase, 'id'|'name'|'message_count'|'amount_toman'>) {
  return `رسید خرید بگم نگم\nشناسهٔ خرید: ${purchase.id}\nبسته: ${purchase.name}\nتعداد پیام: ${purchase.message_count}\nمبلغ: ${purchase.amount_toman} تومان\nتصویر رسید پرداخت را پیوست می‌کنم.`;
}
