import test from 'node:test';
import assert from 'node:assert/strict';
import { rialAsToman, balanceLabel, type ProviderBalance } from '../lib/provider-balances.ts';
const balance:ProviderBalance={provider:'kavenegar',status:'available',amount:'0',currency:'IRR',observed_at:'2026-10-28T10:00:00Z',checked_at:'2026-10-28T10:00:00Z',reason:null};
test('provider rial balances convert to exact toman values without floating point rounding',()=>{
  assert.equal(rialAsToman('0'),'۰ تومان');assert.equal(rialAsToman('1'),'۰٫۱ تومان');assert.equal(rialAsToman('12345'),'۱٬۲۳۴٫۵ تومان');assert.equal(rialAsToman('-1'),'−۰٫۱ تومان');
  assert.equal(rialAsToman('999999999999999999'),'۹۹٬۹۹۹٬۹۹۹٬۹۹۹٬۹۹۹٬۹۹۹٫۹ تومان');
  for(const value of ['NaN','1.1','Infinity','<script>'])assert.equal(rialAsToman(value),null);
});
test('unknown or failed balances are never presented as a real zero balance',()=>{
  assert.equal(balanceLabel(balance),'۰ تومان');assert.equal(balanceLabel({...balance,status:'unavailable',amount:null}),'فعلاً دریافت نشد');
  assert.equal(balanceLabel({...balance,provider:'gapgpt',status:'unsupported',amount:null,currency:null}),'بررسی در پنل');
  assert.equal(balanceLabel({...balance,status:'stale',amount:'12345'}),'۱٬۲۳۴٫۵ تومان');
});
