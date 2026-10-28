// Nonces authorize Next's generated bootstrap scripts without allowing arbitrary
// inline JavaScript. Inline styles remain necessary for React style properties.
export function contentSecurityPolicy(nonce: string, development: boolean, https: boolean) {
  if (!/^[A-Za-z0-9+/]{43}=$/.test(nonce)) throw new Error("Invalid CSP nonce");
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development ? " 'unsafe-eval'" : ""}`,
    "script-src-attr 'none'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    `connect-src 'self'${development ? " ws: wss:" : ""}`,
    "worker-src 'self'",
    "manifest-src 'self'",
    "object-src 'none'",
    "frame-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    ...(!development && https ? ["upgrade-insecure-requests"] : []),
  ].join("; ");
}
