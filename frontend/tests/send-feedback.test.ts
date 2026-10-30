import test from 'node:test';
import assert from 'node:assert/strict';
import { sendFeedback } from '../lib/send-feedback.ts';

test('queue admission can acknowledge registration without claiming delivery', () => {
  for (const status of ['queued', 'processing', 'accepted', 'sent', 'delivered', 'delivered_demo'])
    assert.equal(sendFeedback(status), 'accepted', status);
});

test('uncertain, unconfirmed and unrecognized outcomes never show a success check', () => {
  for (const status of ['unknown', 'created', 'awaiting_payment', 'pending_payment', '', 'future_status'])
    assert.equal(sendFeedback(status), 'uncertain', status);
});

test('a blocked, cancelled or failed send cannot play success feedback', () => {
  for (const status of ['blocked', 'cancelled', 'failed', 'refunded'])
    assert.equal(sendFeedback(status), 'rejected', status);
});
