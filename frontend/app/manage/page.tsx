import { ManagementConsole } from "@/components/management-console";
import { privateMetadata } from "@/lib/seo";
import "./manage.css";

export const metadata = privateMetadata("/manage");

export default function ManagementPage() {
  return <ManagementConsole />;
}
