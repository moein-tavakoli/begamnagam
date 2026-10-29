import assert from 'node:assert/strict';
import test from 'node:test';
import { safeReceiptChannels, receiptText, openPurchase } from '../lib/manual-payments.ts';
import { purchaseIntentAfterResponse } from '../lib/credit-purchases.ts';
import { managementActions } from '../lib/management.ts';

test('receipt links allow only the two configured support services and plain handles',()=>{
  const good=[{name:'bale',label:'بله',url:'https://ble.ir/test_support'},{name:'telegram',label:'تلگرام',url:'https://t.me/test_support'}];
  for(const url of ['javascript:alert(1)','https://t.me.evil.test/test_support','https://t.me/test_support?start=private','https://ble.ir/../bad','http://t.me/test_support'])
    assert.deepEqual(safeReceiptChannels([...good,{name:'telegram',label:'fake',url}]),good);
});
test('receipt text uses purchase snapshots and contains no sender phone or identity',()=>{
  const text=receiptText({id:'purchase-1',name:'همراه',message_count:9,amount_toman:30000});
  assert(text.includes('purchase-1'));assert(text.includes('30000 تومان'));assert(text.includes('9'));assert(!text.includes('تأیید شد'));
});
test('card transfer and receipt review remain open until approval or rejection',()=>{
  const intent={packageId:1,value:'stable',purchaseId:'purchase-1'};
  for(const status of ['awaiting_transfer','awaiting_review']){
    assert(openPurchase(status));assert.deepEqual(purchaseIntentAfterResponse(intent,{id:'purchase-1',package_id:1,status}),intent);
  }
  for(const status of ['credited','cancelled','rejected']){
    assert(!openPurchase(status));assert.equal(purchaseIntentAfterResponse(intent,{id:'purchase-1',package_id:1,status}),null);
  }
});
test('grant and receipt actions are permission scoped and closed receipts cannot be approved',()=>{
  const account={record_id:'123'};
  assert(!managementActions('accounts',account,[]).some(a=>a.name==='grant_package'));
  assert(managementActions('accounts',account,['approve_manual_payments']).some(a=>a.name==='grant_package'));
  const receipt={record_id:'receipt-1',status:'awaiting_review',purchase__amount_toman:10000};
  assert.deepEqual(managementActions('manual-payments',receipt,[]),[]);
  assert.deepEqual(managementActions('manual-payments',receipt,['approve_manual_payments']).map(a=>a.name),['approve_card','reject_card']);
  for(const status of ['approved','rejected','cancelled'])assert.deepEqual(managementActions('manual-payments',{...receipt,status},['approve_manual_payments']),[]);
});
