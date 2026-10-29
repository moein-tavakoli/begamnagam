import { NextResponse, type NextRequest } from "next/server";
import { contentSecurityPolicy } from "@/lib/security";
import { getSeoConfig, publicPages } from "@/lib/seo";

export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString("base64");
  const policy = contentSecurityPolicy(nonce, process.env.NODE_ENV === "development",
    getSeoConfig().baseUrl.protocol === "https:");
  const headers = new Headers(request.headers);
  // Overwrite attacker-supplied values; these headers authorize no API access.
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", policy);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", policy);
  response.headers.set("Cache-Control", "private, no-store");
  if (getSeoConfig().indexable && Object.hasOwn(publicPages, request.nextUrl.pathname)) {
    response.headers.append("Link", '</llms.txt>; rel="describedby"; type="text/plain"');
  }
  return response;
}

export const config = {
  // API/admin have their own Django CSP. Do not apply HTML nonces to public
  // assets, the service worker, sitemap or robots, which remain cacheable.
  matcher: ["/((?!api(?:/|$)|admin(?:/|$)|static/|_next/|images/|icons/|icon\\.svg$|favicon\\.ico$|manifest\\.webmanifest$|robots\\.txt$|sitemap\\.xml$|llms\\.txt$|sw\\.js$|offline\\.html$).*)"],
};
