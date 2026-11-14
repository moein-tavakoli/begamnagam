const shortCode = /^(?=[A-Za-z0-9]{0,4}[0-9])[A-Za-z0-9]{5}$/;
const typedCode = /^[arci](?=[A-Za-z0-9]{0,4}[0-9])[A-Za-z0-9]{5}$/;
const legacyStop = /^[A-Za-z0-9]{8}$/;
const legacyReply = /^p[A-Za-z0-9]{8}$/;

export function isShortRecipientCode(code: string): boolean {
  return (code.length === 6 && !code.startsWith('i') && typedCode.test(code)) ||
    (code.length === 5 && shortCode.test(code));
}

export function isInvitationPathCode(code: string): boolean {
  return code.length === 6 && code.startsWith('i') && typedCode.test(code);
}

export function isRecipientActionCode(code: string): boolean {
  return code.length === 6 && code.startsWith('a') && typedCode.test(code);
}

export function actionFromFragment(fragment: string): { token: string; action?: 'reply' | 'stop' } | null {
  const [token, action, extra] = fragment.split('/', 3);
  if (!isRecipientActionCode(token) || extra !== undefined) return null;
  if (action === undefined) return { token };
  return action === 'reply' || action === 'stop' ? { token, action } : null;
}

export function isRecipientPathCode(code: string): boolean {
  return isShortRecipientCode(code) || (code.length === 8 && legacyStop.test(code)) ||
    (code.length === 9 && legacyReply.test(code));
}

export function replyTokenFromFragment(code: string): string | null {
  if (code.length === 9 && legacyReply.test(code)) return code.slice(1);
  if (!isShortRecipientCode(code)) return null;
  const reply = code.length === 6 ? code.startsWith('r') : /^[a-z5-9]/.test(code);
  return reply ? code : null;
}
