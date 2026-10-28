import assert from 'node:assert/strict';
import test from 'node:test';
import { walletToman, walletEntryLabel, topupLabel } from '../lib/wallet.ts';

test('wallet formats integer balances without floating point loss', () => {
  assert.equal(walletToman('9007199254740993'), `${new Intl.NumberFormat('fa-IR').format(9007199254740993n)} تومان`);
  assert.equal(walletToman('0'), '۰ تومان');
  for (const value of ['-1', '1.5', 'NaN', '<script>']) assert.equal(walletToman(value), '—');
});
test('uncertain charges do not promise success and returns identify wallet credit', () => {
  assert.match(topupLabel('unknown'), /دوباره پرداخت نکن/);
  assert.match(walletEntryLabel('payment_return'), /کیف پول/);
});
