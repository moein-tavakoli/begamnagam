import assert from 'node:assert/strict';
import test from 'node:test';
import { purchaseExamples, trialExampleDraft } from '../lib/purchase-examples.ts';

test('a public example opens its own editable draft without putting message text in the URL', () => {
  const club = purchaseExamples.find(example => example.id === 'film-club');
  assert.ok(club);
  assert.match(club.body, /فیلم/);
  for (const example of purchaseExamples) {
    assert.match(example.id, /^[a-z-]+$/);
    assert.equal(trialExampleDraft(example.id), example.input);
  }
  assert.equal(new Set(purchaseExamples.map(example => example.id)).size, purchaseExamples.length);
});

test('a private message or ambiguous query parameter cannot prefill a trial from the URL', () => {
  for (const value of ['یک پیام شخصی', '__proto__', ['film-club', 'noise'], undefined]) {
    assert.equal(trialExampleDraft(value), '');
  }
});
