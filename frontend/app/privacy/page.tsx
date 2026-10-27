import Link from "next/link";
import { Icon } from "@/components/icons";
import { PrivacyContent } from "@/components/privacy-content";
import { StructuredData } from "@/components/structured-data";
import { pageJsonLd, publicMetadata } from "@/lib/seo";
export const metadata = publicMetadata("/privacy");

export default function PrivacyPage() {
  return (
    <div className="document-page policy-page wrap">
      <StructuredData data={pageJsonLd("/privacy")} />
      <Link className="back-link" href="/">
        بازگشت به خانه <Icon name="arrow" size={16} />
      </Link>
      <div className="account-heading">
        <span className="eyebrow">اعتماد، با شفافیت</span>
        <h1>حریم خصوصی و مرزهای استفاده.</h1>
        <p>
          پیش از تأیید ارسال، متن نهایی و این شرایط رو بررسی کن. شمارهٔ
          فرستنده برای گیرنده نمایش داده نمی‌شه؛ ارسال مسئولانه وظیفهٔ فرستنده است.
        </p>
      </div>
      <div className="prose-card">
        <PrivacyContent />
      </div>
      <div className="document-cta">
        <Icon name="shield" size={28} />
        <p>حق دریافت‌نکردن، بخشی از احترامه.</p>
        <Link href="/preferences" prefetch={false} className="button secondary">
          مدیریت دریافت پیام
        </Link>
      </div>
    </div>
  );
}
