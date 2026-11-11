const shortCode = /^(?=[A-Za-z0-9]{0,4}[0-9])[A-Za-z0-9]{5}$/;
const legacyStop = /^[A-Za-z0-9]{8}$/;
const legacyReply = /^p[A-Za-z0-9]{8}$/;

export function isShortRecipientCode(code: string): boolean {
  return code.length === 5 && shortCode.test(code);
}

export function isRecipientPathCode(code: string): boolean {
  return isShortRecipientCode(code) || (code.length === 8 && legacyStop.test(code)) ||
    (code.length === 9 && legacyReply.test(code));
}

export function replyTokenFromFragment(code: string): string | null {
  if (code.length === 9 && legacyReply.test(code)) return code.slice(1);
  return isShortRecipientCode(code) && /^[a-z5-9]/.test(code) ? code : null;
}
