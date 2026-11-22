import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { MonitoringTv } from "@/components/monitoring-tv";
import { privateMetadata } from "@/lib/seo";
import { monitoringTvRenderHeader } from "@/lib/security";

export const metadata = {
  ...privateMetadata("/manage"),
  title: "مانیتورینگ بگم نگم",
};

export default async function MonitoringTvPage() {
  if ((await headers()).get(monitoringTvRenderHeader) !== "1") notFound();
  return <MonitoringTv />;
}
