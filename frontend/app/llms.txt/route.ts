import { llmsText } from "@/lib/seo";

export const dynamic = "force-static";

export function GET() {
  const text = llmsText();
  return new Response(text ?? "Not available in this environment.\n", {
    status: text === null ? 404 : 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "X-Content-Type-Options": "nosniff",
      "X-Robots-Tag": text === null ? "noindex, nofollow" : "noindex",
      "Cache-Control": text === null ? "no-store" : "public, max-age=3600",
    },
  });
}
