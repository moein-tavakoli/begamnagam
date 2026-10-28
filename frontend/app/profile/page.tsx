import { Profile } from "@/components/profile";
import { privateMetadata } from "@/lib/seo";

export const metadata = privateMetadata("/profile");

export default function Page() {
  return <Profile />;
}
