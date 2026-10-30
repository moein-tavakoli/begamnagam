import type { MessageTone, MessageToneOption } from '@/lib/message-tones';

export function MessageTonePicker({ options, value, onChange, disabled = false }: {
  options: MessageToneOption[]; value: MessageTone; onChange: (tone: MessageTone) => void; disabled?: boolean;
}) {
  if (!options.length) return null;
  return <fieldset className="message-tone-picker" disabled={disabled} aria-describedby="message-tone-help">
    <legend className="sr-only">لحن پیام</legend>
    <div className="message-tone-options"><span className="message-tone-label" aria-hidden="true">لحن پیام</span>{options.map(option => <label key={option.id} className={value === option.id ? 'is-selected' : ''}>
      <input type="radio" name="message_tone" value={option.id} checked={value === option.id} onChange={() => onChange(option.id)} />
      <span>{option.label}</span>
    </label>)}</div>
    <p id="message-tone-help">{options.find(option => option.id === value)?.description}</p>
  </fieldset>;
}
