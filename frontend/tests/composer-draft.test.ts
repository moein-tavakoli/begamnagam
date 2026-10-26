import assert from "node:assert/strict";
import { test } from "node:test";
import { draftProblem, draftTopicHint } from "../lib/composer-draft.ts";

const topics = [
  { id: "appreciation", example: "از توجه و کمکت ممنونم" },
  { id: "noise", example: "لطفاً آرام‌تر صحبت کن" },
];

test("editing a suggestion clears attribution and does not automatically choose another topic", () => {
  assert.equal(draftTopicHint("noise", topics[1].example, topics), "noise");
  assert.equal(draftTopicHint("noise", "می‌خوام دربارهٔ قرض گرفتن وسایلم حرف بزنم", topics), "");
  assert.equal(draftTopicHint("noise", topics[0].example, topics), "");
  assert.equal(draftTopicHint("", topics[0].example, topics), "");
});

test("configured freeform rewriting accepts custom drafts without any topic or suggestions", () => {
  assert.equal(draftProblem("لطفاً پیش از قرض گرفتن وسایلم از خودم بپرس", "", [], true), null);
  assert.equal(draftProblem("لطفاً وسایلم را پیش از جابه‌جایی با من هماهنگ کن", "noise", topics, true), null);
  assert.equal(draftProblem("  ", "noise", topics, true), "too_short");
});

test("inactive freeform rewriting permits an explicit example and rejects silent template replacement", () => {
  assert.equal(draftProblem(topics[1].example, "noise", topics, false), null);
  assert.equal(draftProblem("یک موضوع متفاوت دارم", "noise", topics, false), "freeform_unavailable");
  assert.equal(draftProblem(topics[0].example, "", topics, false), "freeform_unavailable");
  assert.equal(draftProblem("متن دلخواه", "custom", topics, false), "freeform_unavailable");
});
