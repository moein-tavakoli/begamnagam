import assert from 'node:assert/strict';
import test from 'node:test';
import { creditPaymentMethods, purchaseIntentAfterResponse } from '../lib/credit-purchases.ts';

test('terminal wallet return releases the previous checkout key for a new purchase', () => {
  const intent = { packageId: 1, value: 'same-request-key' };
  const pending = purchaseIntentAfterResponse(intent, {id:'purchase-1',package_id:1,status:'unknown'});
  assert.deepEqual(pending, {...intent,purchaseId:'purchase-1'});
  assert.equal(purchaseIntentAfterResponse(pending,{id:'purchase-1',package_id:1,status:'wallet_returned'}),null);
});
test('uncertain outcomes keep the key and another receipt cannot clear it', () => {
  const intent = {packageId:1,value:'stable',purchaseId:'purchase-1'};
  for (const status of ['created','pending','unknown','verified'])
    assert.deepEqual(purchaseIntentAfterResponse(intent,{id:'purchase-1',package_id:1,status}),intent);
  assert.equal(purchaseIntentAfterResponse(intent,{id:'other',package_id:1,status:'credited'}),intent);
  assert.equal(purchaseIntentAfterResponse(intent,{id:'purchase-1',package_id:2,status:'credited'}),intent);
  for (const status of ['credited','failed']) assert.equal(purchaseIntentAfterResponse(intent,{id:'purchase-1',package_id:1,status}),null);
});

test('the price list and review use only payment methods available on the website', () => {
  const options = { wallet_enabled: true, gateway_enabled: false, gateway_configured: false, wallet_terms_version: 'v1' };
  const live = { demo_mode: false, payment_backend: 'disabled', payment_options: options };

  assert.equal(creditPaymentMethods(null).status, 'unknown');
  assert.equal(creditPaymentMethods({ demo_mode: false }).status, 'unknown');
  assert.equal(creditPaymentMethods(live).status, 'closed');
  assert.deepEqual(creditPaymentMethods({ ...live, payment_options: { ...options, card_enabled: true } }),
    { gateway: false, card: true, status: 'available' });
  assert.deepEqual(creditPaymentMethods({ ...live, payment_options: { ...options, gateway_enabled: true } }),
    { gateway: true, card: false, status: 'available' });
  assert.equal(creditPaymentMethods({ demo_mode: true, payment_backend: 'demo' }).gateway, true);
  assert.equal(creditPaymentMethods({ demo_mode: false, payment_backend: 'demo' }).gateway, false);
});
