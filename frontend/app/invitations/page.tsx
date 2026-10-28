import { Invitations } from "@/components/invitations";
import { privateMetadata } from "@/lib/seo";
export const metadata = privateMetadata("/invitations");
export default function Page() { return <Invitations />; }
