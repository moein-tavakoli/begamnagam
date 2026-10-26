type DraftTopic = { id: string; example: string };

// A topic is only a hint while its original example is still in the field.
// Editing must never silently send an unrelated topic template instead.
export function draftTopicHint(
  selectedId: string,
  text: string,
  topics: readonly DraftTopic[],
): string {
  return topics.some(topic => topic.id === selectedId && topic.example === text)
    ? selectedId
    : "";
}

export function draftProblem(
  text: string,
  selectedId: string,
  topics: readonly DraftTopic[],
  freeformEnabled: boolean,
): "too_short" | "freeform_unavailable" | null {
  if (text.trim().length < 3) return "too_short";
  if (!freeformEnabled && !draftTopicHint(selectedId, text, topics))
    return "freeform_unavailable";
  return null;
}
