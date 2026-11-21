import type { Bootstrap } from './api';

type CreditPaymentSettings = Pick<Bootstrap, 'demo_mode' | 'payment_backend' | 'payment_options' | 'package_checkout_enabled'>;

export function creditPaymentMethods(data: CreditPaymentSettings | null) {
  const gateway = !!data?.payment_options?.gateway_enabled || !!(data?.demo_mode && data.payment_backend === 'demo');
  const card = !!data?.payment_options?.card_enabled;
  let status: 'unknown' | 'closed' | 'available' = 'unknown';
  if (gateway || card) status = 'available';
  else if (data?.payment_options || data?.package_checkout_enabled === false) status = 'closed';
  return { gateway, card, status };
}

export type PurchaseIntent = { packageId: number; value: string; purchaseId?: string };
export type PurchaseResult = { id: string; package_id: number; status: string };

export function settledPurchase(status: string): boolean {
  return ['credited', 'failed', 'wallet_returned', 'cancelled', 'rejected'].includes(status);
}

/** Bind only the response to this request; uncertain results keep the same key. */
export function purchaseIntentAfterResponse(intent: PurchaseIntent | null, result: PurchaseResult): PurchaseIntent | null {
  if (!intent || intent.packageId !== result.package_id || (intent.purchaseId && intent.purchaseId !== result.id)) return intent;
  return settledPurchase(result.status) ? null : { ...intent, purchaseId: result.id };
}
