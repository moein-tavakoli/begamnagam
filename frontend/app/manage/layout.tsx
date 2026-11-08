import { Suspense } from "react";
import { ManagementConsole } from "@/components/management-console";
import { privateMetadata } from "@/lib/seo";
import { ManagementTheme } from "@/components/management-theme";
import "./manage.css";

export const metadata = privateMetadata("/manage");

export default function ManagementLayout({ children }: { children: React.ReactNode }) {
  return <ManagementTheme><Suspense fallback={<p role="status">در حال دریافت مدیریت…</p>}><ManagementConsole>{children}</ManagementConsole></Suspense></ManagementTheme>;
}
