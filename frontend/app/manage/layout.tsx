import { Suspense } from "react";
import { ManagementConsole } from "@/components/management-console";
import { privateMetadata } from "@/lib/seo";
import "./manage.css";

export const metadata = privateMetadata("/manage");

export default function ManagementLayout({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<p role="status">در حال دریافت مدیریت…</p>}><ManagementConsole>{children}</ManagementConsole></Suspense>;
}
