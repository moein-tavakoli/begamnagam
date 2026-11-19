import { PersonalShare } from "@/components/personal-share";
import { privateMetadata } from "@/lib/seo";

export const metadata = privateMetadata("/profile/share");

export default function Page() {
  return <PersonalShare />;
}
