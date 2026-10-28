import { History } from "@/components/account-pages";
import { privateMetadata } from "@/lib/seo";
export const metadata = privateMetadata("/history");
export default function Page() {
  return <History />;
}
