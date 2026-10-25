import { HomeFlow } from "@/components/home-flow";
import { StructuredData } from "@/components/structured-data";
import { pageJsonLd, publicMetadata } from "@/lib/seo";

export const metadata = publicMetadata("/");

export default function Home() {
  return <><StructuredData data={pageJsonLd("/")} /><HomeFlow /></>;
}
