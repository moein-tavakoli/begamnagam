import { Preferences } from "@/components/account-pages";
import { privateMetadata } from "@/lib/seo";
export const metadata = privateMetadata("/preferences");
export default function Page() {
  return <Preferences />;
}
