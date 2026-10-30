import { version } from "../../package.json";

export function GET() {
  return Response.json({version},{headers:{"Cache-Control":"no-store, max-age=0","X-Robots-Tag":"noindex, nofollow"}});
}
