const opaqueFields = new Set([
  "id", "username", "password", "password1", "password2", "old_password",
  "new_password1", "new_password2", "csrfmiddlewaretoken", "token", "signature",
  "authority", "status", "category", "message_tone", "source_mode", "source",
]);
export function opaqueInputField(name: string): boolean {
  return opaqueFields.has(name.toLowerCase()) || /_(id|token|signature|key|hash|digest|cipher|version)$/i.test(name);
}

export function latinInputDigits(value: string): string {
  return value.replace(/[۰-۹٠-٩０-９]/g, digit => {
    const code = digit.charCodeAt(0);
    return String(code >= 65296 ? code - 65296 : code >= 1776 ? code - 1776 : code - 1632);
  });
}

export function canonicalInput(value: unknown, field = ""): unknown {
  if (opaqueInputField(field)) return value;
  if (typeof value === "string") return latinInputDigits(value);
  if (Array.isArray(value)) return value.map(item => canonicalInput(item));
  if (value && typeof value === "object" && [Object.prototype, null].includes(Object.getPrototypeOf(value))) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, canonicalInput(item, key)]));
  }
  return value;
}
