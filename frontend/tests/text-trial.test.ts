import assert from 'node:assert/strict';
import test from 'node:test';
import { matchesTrialWording, trialWordChanges } from '../lib/text-trial.ts';

test('marks the changed Persian word without losing its joiner or the surrounding sentence', () => {
  assert.deepEqual(trialWordChanges('خودت جمله‌ات را اصلاح کردی.', 'خودت جمله‌هات را اصلاح کردی.'), [
    { kind: 'equal', text: 'خودت ' },
    { kind: 'removed', text: 'جمله‌ات' },
    { kind: 'added', text: 'جمله‌هات' },
    { kind: 'equal', text: ' را اصلاح کردی.' },
  ]);
});

test('preserves repeated words, newlines, punctuation and emoji when reading either side', () => {
  for (const [draft, body] of [
    ['مکث کن، مکث کن.', 'اینجا مکث کن.'],
    ['خوب!\nآفرین 🌱', 'خوب؟  آفرین 🌱'],
    ['عدد 2 را بگو', 'عدد 2 را بگو'],
    ['نفس بکش', ''],
  ]) {
    const changes = trialWordChanges(draft, body);
    assert.equal(changes.filter(part => part.kind !== 'added').map(part => part.text).join(''), draft);
    assert.equal(changes.filter(part => part.kind !== 'removed').map(part => part.text).join(''), body);
    if (draft === body) assert.deepEqual(changes, [{ kind: 'equal', text: draft }]);
  }
});

test('a protected trial requires a reviewed body and the exact submitted wording after digit canonicalization', () => {
  const draft = 'روی جملهٔ ۲ مکث کن.';
  assert.ok(matchesTrialWording('exact', draft, '', 'روی جملهٔ 2 مکث کن.'));
  assert.equal(matchesTrialWording('exact', draft, '', 'روی جمله 2 مکث کن.'), false);
  assert.equal(matchesTrialWording('exact', draft, '', undefined), false);
  assert.ok(matchesTrialWording('phrase', draft, 'جملهٔ ۲', 'برای جملهٔ 2 مکث کن.'));
  assert.equal(matchesTrialWording('phrase', draft, 'جملهٔ ۲', 'روی جمله‌های 2 مکث کن.'), false);
  assert.equal(matchesTrialWording('phrase', draft, 'جملهٔ ۲', undefined), false);
  assert.ok(matchesTrialWording('rewrite', draft, '', undefined));
});
