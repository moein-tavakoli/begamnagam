// Nonces authorize Next's generated bootstrap scripts without allowing arbitrary
// inline JavaScript. Inline styles remain necessary for React style properties.
export const monitoringTvPath = "/manage/monitoring/tv";
export const monitoringTvGatewayHeader = "x-begam-monitoring-tv";
export const monitoringTvRenderHeader = "x-begam-monitoring-tv-view";

export function isMonitoringTvRequest(path: string, method: string, enabled: string | undefined, gateway: string | null) {
  return path === monitoringTvPath && (method === "GET" || method === "HEAD")
    && enabled === "1" && gateway === "1";
}

export function contentSecurityPolicy(nonce: string, development: boolean, https: boolean, { monitoringTv = false } = {}) {
  if (!/^[A-Za-z0-9+/]{43}=$/.test(nonce)) throw new Error("Invalid CSP nonce");
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development ? " 'unsafe-eval'" : ""}`,
    "script-src-attr 'none'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https://trustseal.enamad.ir",
    "font-src 'self'",
    `connect-src 'self'${development ? " ws: wss:" : ""}`,
    "worker-src 'self'",
    "manifest-src 'self'",
    "object-src 'none'",
    "frame-src 'none'",
    "base-uri 'none'",
    monitoringTv ? "form-action 'none'" : "form-action 'self'",
    monitoringTv ? "frame-ancestors http://tv.ir http://192.168.1.117:8080" : "frame-ancestors 'none'",
    ...(!development && https && !monitoringTv ? ["upgrade-insecure-requests"] : []),
  ].join("; ");
}
