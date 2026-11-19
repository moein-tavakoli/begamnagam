import { isInvitationPathCode, isRecipientPathCode } from "../../../lib/recipient-links.ts";

// GET and HEAD only redirect. The recipient page handles explicit actions.
export async function GET(_request: Request, context: { params: Promise<{ code: string }> }) {
  const { code } = await context.params;
  const headers = {
    "Cache-Control": "private, no-store, max-age=0",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive, nosnippet",
  };
  const invitation = isInvitationPathCode(code);
  if (!invitation && !isRecipientPathCode(code)) return new Response(null, { status: 404, headers });
  const location = invitation ? "/" : `/r#${code}`;
  return new Response(null, { status: 307, headers: { ...headers, Location: location } });
}

export const HEAD = GET;
