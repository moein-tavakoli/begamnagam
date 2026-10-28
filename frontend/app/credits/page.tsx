import { CreditPackages } from "@/components/credit-packages";
import { privateMetadata } from "@/lib/seo";

export const metadata = privateMetadata("/credits");

export default function Page() {
  return <div className="account-page wrap"><div className="account-heading"><h1>اعتبار پیام‌های من</h1><p>بسته‌های فعال و موجودی حساب</p></div><CreditPackages /></div>;
}
