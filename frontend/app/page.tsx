import { HomeFlow } from "@/components/home-flow";
import { StructuredData } from "@/components/structured-data";
import { pageJsonLd, publicMetadata } from "@/lib/seo";

export const metadata = {
  ...publicMetadata("/"),
  other: { enamad: "5251197" },
};

export default function Home() {
  return <><StructuredData data={pageJsonLd("/")} /><HomeFlow /></>;
}
