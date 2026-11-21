import { latinInputDigits } from './input-digits.ts';

type Change = { kind: 'equal' | 'removed' | 'added'; text: string };
export type TrialWording = 'rewrite' | 'phrase' | 'exact';

export function matchesTrialWording(mode: TrialWording, draft: string, phrase: string, reviewedBody?: string): boolean {
  if (mode === 'rewrite') return true;
  if (!reviewedBody) return false;
  if (mode === 'exact') return reviewedBody === latinInputDigits(draft);
  return !!phrase.trim() && reviewedBody.includes(latinInputDigits(phrase));
}

export function trialWordChanges(draft: string, reviewed: string): Change[] {
  const before = draft.match(/\s+|\S+/gu) ?? [];
  const after = reviewed.match(/\s+|\S+/gu) ?? [];
  // Longest common subsequences keep repeated Persian words aligned. Both inputs
  // are bounded by the trial's draft and SMS length limits.
  const lengths = Array.from({ length: before.length + 1 }, () => new Uint16Array(after.length + 1));
  for (let i = before.length - 1; i >= 0; i--) {
    for (let j = after.length - 1; j >= 0; j--) {
      lengths[i][j] = before[i] === after[j]
        ? lengths[i + 1][j + 1] + 1 : Math.max(lengths[i + 1][j], lengths[i][j + 1]);
    }
  }
  const changes: Change[] = [];
  function append(kind: Change['kind'], text: string) {
    const previous = changes.at(-1);
    if (previous?.kind === kind) previous.text += text;
    else changes.push({ kind, text });
  }
  let i = 0;
  let j = 0;
  while (i < before.length || j < after.length) {
    if (i < before.length && j < after.length && before[i] === after[j]) {
      append('equal', before[i]);
      i++; j++;
    } else if (i < before.length && (j === after.length || lengths[i + 1][j] >= lengths[i][j + 1])) {
      append('removed', before[i++]);
    } else {
      append('added', after[j++]);
    }
  }
  return changes;
}
