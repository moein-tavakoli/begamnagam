import type { Metadata } from "next";
import { Preferences } from "@/components/account-pages";
export const metadata: Metadata = { title: "قطع دریافت پیام" };
export default function Page() {
  return <Preferences />;
}
