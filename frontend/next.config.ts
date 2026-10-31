import type { NextConfig } from "next";

const apiOrigin = (
  process.env.INTERNAL_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

const config: NextConfig = {
  output: process.env.BUILD_STANDALONE === "1" ? "standalone" : undefined,
  outputFileTracingRoot: process.cwd(),
  turbopack: { root: process.cwd() },
  poweredByHeader: false,
  devIndicators: false,
  productionBrowserSourceMaps: false,
  // Public settings remain fixed by the image build when pages render with
  // per-request CSP nonces. Never add provider credentials to this object.
  env: {
    APP_BASE_URL: process.env.APP_BASE_URL || "http://localhost:3000",
    SEO_INDEXABLE: process.env.SEO_INDEXABLE || "0",
  },
  // Django admin requires trailing slashes; preserve them through the proxy.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${apiOrigin}/api/v1/:path*` },
      { source: "/api/v2/:path*", destination: `${apiOrigin}/api/v2/:path*` },
      { source: "/admin/:path*", destination: `${apiOrigin}/admin/:path*/` },
      {
        source: "/static/admin/:path*",
        destination: `${apiOrigin}/static/admin/:path*`,
      },
    ];
  },
  async headers() {
    return [
      { source: "/r", headers: [{ key: "Cache-Control", value: "no-store" }, { key: "Referrer-Policy", value: "no-referrer" }] },
      { source: "/r/:path*", headers: [{ key: "Cache-Control", value: "no-store" }, { key: "Referrer-Policy", value: "no-referrer" }] },
      { source: "/invitations", headers: [{ key: "Cache-Control", value: "no-store" }] },
      { source: "/wallet", headers: [{ key: "Cache-Control", value: "no-store" }] },
      { source: "/credits", headers: [{ key: "Cache-Control", value: "no-store" }] },
      { source: "/profile", headers: [{ key: "Cache-Control", value: "no-store" }] },
      { source: "/manage/:path*", headers: [{ key: "Cache-Control", value: "no-store" }] },
      ...["/r", "/r/:path*", "/wallet", "/credits", "/profile", "/history", "/invitations", "/preferences", "/manage/:path*", "/api/:path*", "/admin/:path*", "/offline.html"].map(source => ({
        source,
        headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow, noarchive, nosnippet" }],
      })),
      { source: "/sw.js", headers: [{ key: "Cache-Control", value: "no-cache, no-store, must-revalidate" }, { key: "Service-Worker-Allowed", value: "/" }] },
      { source: "/offline.html", headers: [
        { key: "Cache-Control", value: "no-cache" },
        { key: "Content-Security-Policy", value: "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'" },
      ] },
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          ...(process.env.NODE_ENV === "production" &&
            new URL(process.env.APP_BASE_URL || "http://localhost:3000").protocol === "https:"
            ? [{ key: "Strict-Transport-Security", value: "max-age=31536000" }] : []),
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
      { source: "/admin/:path*", headers: [{ key: "Referrer-Policy", value: "same-origin" }] },
      ...["/api/v2/document", "/api/v2/document/login"].map(source => ({
        source,
        headers: [{ key: "Referrer-Policy", value: "same-origin" }],
      })),
    ];
  },
};

export default config;
