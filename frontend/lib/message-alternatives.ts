import type { MessageTone } from './message-tones';

export type MessageAlternative = { id: string; label: string; text: string; token: string; message_tone: MessageTone; expires_at: string };
export function messageAlternatives(details: unknown): MessageAlternative[] {
  if (!details || typeof details !== 'object' || !('alternatives' in details) || !Array.isArray(details.alternatives)) return [];
  return details.alternatives.slice(0, 3).filter((v): v is MessageAlternative => !!v && typeof v === 'object' &&
    typeof v.id === 'string' && v.id.length <= 40 && typeof v.label === 'string' && v.label.length <= 80 &&
    typeof v.text === 'string' && v.text.length > 0 && v.text.length <= 201 &&
    typeof v.token === 'string' && v.token.length > 0 && v.token.length <= 4096 &&
    ['polite', 'firm', 'angry'].includes(v.message_tone) && typeof v.expires_at === 'string' && Number.isFinite(Date.parse(v.expires_at)));
}
export function alternativeRequest(alternative: MessageAlternative, recipient: string) {
  // No browser-owned message body or moderation verdict may replace this token.
  return { source_mode: 'reviewed_alternative', alternative_token: alternative.token,
    recipient_phone: recipient, message_tone: alternative.message_tone };
}
