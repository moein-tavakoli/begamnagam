import { SharedMessage } from "@/components/shared-message";
import { privateMetadata } from "@/lib/seo";

export const metadata = privateMetadata("/send");

export default function Page() {
  return <SharedMessage />;
}
