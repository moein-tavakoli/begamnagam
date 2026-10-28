export type PurchaseIntent = { packageId: number; value: string; purchaseId?: string };
export type PurchaseResult = { id: string; package_id: number; status: string };

export function settledPurchase(status: string): boolean {
  return ['credited', 'failed', 'wallet_returned'].includes(status);
}

/** Bind only the response to this request; uncertain results keep the same key. */
export function purchaseIntentAfterResponse(intent: PurchaseIntent | null, result: PurchaseResult): PurchaseIntent | null {
  if (!intent || intent.packageId !== result.package_id || (intent.purchaseId && intent.purchaseId !== result.id)) return intent;
  return settledPurchase(result.status) ? null : { ...intent, purchaseId: result.id };
}
