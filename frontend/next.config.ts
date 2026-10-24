import type { NextConfig } from "next";

const apiOrigin = (
  process.env.INTERNAL_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

const config: NextConfig = {
  output: process.env.BUILD_STANDALONE === "1" ? "standalone" : undefined,
  outputFileTracingRoot: process.cwd(),
  turbopack: { root: process.cwd() },
  poweredByHeader: false,
  // Django admin requires trailing slashes; preserve them through the proxy.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${apiOrigin}/api/v1/:path*` },
      { source: "/admin/:path*", destination: `${apiOrigin}/admin/:path*/` },
      {
        source: "/static/admin/:path*",
        destination: `${apiOrigin}/static/admin/:path*`,
      },
    ];
  },
  async headers() {
    return [
      { source: "/sw.js", headers: [{ key: "Cache-Control", value: "no-cache, no-store, must-revalidate" }, { key: "Service-Worker-Allowed", value: "/" }] },
      { source: "/offline.html", headers: [{ key: "Cache-Control", value: "no-cache" }] },
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};

export default config;
