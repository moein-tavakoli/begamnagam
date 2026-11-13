import { normalizePhone, validPhone } from "./format.ts";

type ContactPicker = {
  select(properties: string[], options: { multiple: boolean }): Promise<{ tel?: string[] }[]>;
};

export function getContactPicker(): ContactPicker | null {
  if (typeof window === "undefined" || !window.isSecureContext || window.top !== window) return null;
  const { contacts } = window.navigator as Navigator & { contacts?: ContactPicker };
  return typeof contacts?.select === "function" ? contacts : null;
}

export async function pickRecipientNumbers(picker: ContactPicker): Promise<string[] | null> {
  const [contact] = await picker.select(["tel"], { multiple: false });
  if (!contact) return null;

  const numbers = new Set<string>();
  for (const number of contact.tel ?? []) {
    if (validPhone(number)) numbers.add(normalizePhone(number));
  }
  return [...numbers];
}
