import { Suspense } from "react";
import { headers } from "next/headers";
import { ManagementConsole } from "@/components/management-console";
import { privateMetadata } from "@/lib/seo";
import { ManagementTheme } from "@/components/management-theme";
import { monitoringTvRenderHeader } from "@/lib/security";
import "./manage.css";

export const metadata = privateMetadata("/manage");

export default async function ManagementLayout({ children }: { children: React.ReactNode }) {
  if ((await headers()).get(monitoringTvRenderHeader) === "1") {
    return <ManagementTheme>{children}</ManagementTheme>;
  }
  return <ManagementTheme><Suspense fallback={<p role="status">در حال دریافت مدیریت…</p>}><ManagementConsole>{children}</ManagementConsole></Suspense></ManagementTheme>;
}
