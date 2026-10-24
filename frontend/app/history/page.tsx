import type { Metadata } from "next";
import { History } from "@/components/account-pages";
export const metadata: Metadata = { title: "پیام‌های من" };
export default function Page() {
  return <History />;
}
