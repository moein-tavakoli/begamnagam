// The SMS URL has a plain alphanumeric code. Move it to the existing private
// recipient screen without doing any lookup, opt-out or report on a GET/HEAD.
export async function GET(_request: Request, context: { params: Promise<{ code: string }> }) {
  const { code } = await context.params;
  const headers = {
    "Cache-Control": "private, no-store, max-age=0",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive, nosnippet",
  };
  if (!/^[A-Za-z0-9]{8}$/.test(code)) return new Response(null, { status: 404, headers });
  return new Response(null, { status: 307, headers: { ...headers, Location: `/r#${code}` } });
}

export const HEAD = GET;
