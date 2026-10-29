import test from 'node:test';
import assert from 'node:assert/strict';
import { alternativeRequest, messageAlternatives } from '../lib/message-alternatives.ts';
import { managementActions } from '../lib/management.ts';

const offer = { id: 'conversation', label: 'گفت‌وگو', text: 'با احترام صحبت کنیم.',
  token: 'synthetic-token', message_tone: 'polite', expires_at: '2026-10-28T20:00:00Z' };

test('only bounded complete alternative records enter the selection UI', () => {
  assert.equal(messageAlternatives(undefined).length, 0);
  assert.equal(messageAlternatives({ alternatives: [offer, null, { ...offer, token: '' }] }).length, 1);
  for (const broken of [{ ...offer, message_tone: 'unchecked' }, { ...offer, text: 'x'.repeat(202) },
    { ...offer, expires_at: 'unknown' }, { ...offer, token: 'x'.repeat(4097) }]) {
    assert.equal(messageAlternatives({ alternatives: [broken] }).length, 0);
  }
});

test('selection submits the server token and target, never a replacement body or approval flag', () => {
  const alternative = messageAlternatives({ alternatives: [offer] })[0];
  const request = alternativeRequest(alternative, '09901234567');
  assert.deepEqual(request, { source_mode: 'reviewed_alternative', alternative_token: 'synthetic-token',
    recipient_phone: '09901234567', message_tone: 'polite' });
  assert.equal('text' in request, false);
  assert.equal('allowed' in request, false);
});

test('account count controls require their permission and preserve the difference between null and zero', () => {
  const row = { record_id: '123', sender_daily_limit: null, rewrite_daily_limit: 0 };
  assert.equal(managementActions('accounts', row, []).length, 0);
  const [action] = managementActions('accounts', row, ['manage_account_limits']);
  assert.equal(action.name, 'account_limits');
  assert.deepEqual(action.accountLimits, { sender_daily_limit: null, rewrite_daily_limit: 0 });
});
