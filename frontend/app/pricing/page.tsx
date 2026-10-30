import Link from 'next/link';
import { PackageCatalog } from '@/components/package-catalog';
import { StructuredData } from '@/components/structured-data';
import { pageJsonLd, publicMetadata } from '@/lib/seo';
import styles from '@/components/credit-shop.module.css';

export const metadata = publicMetadata('/pricing');
export default function PricingPage() {
  return <div className={`wrap ${styles.page}`}>
    <StructuredData data={pageJsonLd('/pricing')}/>
    <header className={styles.intro}><span className={styles.eyebrow}>کمی حرف خوب، برای حال بهتر</span><h1>تعرفه‌ها و بسته‌های پیام<span>.</span></h1><p>به اندازهٔ حرف‌هایی که می‌خواهی برسانی، اعتبار بگیر.</p></header>
    <PackageCatalog/>
    <section className={styles.faq} aria-labelledby="pricing-questions"><h2 id="pricing-questions">قبل از خرید</h2>
      <details><summary>هدیه‌ها با خرید بسته چه می‌شوند؟</summary><p>هدیه‌های باقی‌مانده حفظ می‌شوند و اول مصرف می‌شوند؛ پس از آن هر ارسال یک اعتبار از بسته کم می‌کند.</p></details>
      <details><summary>چطور پرداخت کنم؟</summary><p>هنگام خرید، روش‌های فعال را می‌بینی: درگاه بانکی یا کارت‌به‌کارت. درگاه پس از تأیید پرداخت، بسته را خودکار فعال می‌کند. برای کارت‌به‌کارت، رسید را در بله یا تلگرام برای پشتیبانی می‌فرستی و بسته پس از بررسی ادمین فعال می‌شود.</p></details>
      <details><summary>اگر پیام ارسال نشود چه می‌شود؟</summary><p>اعتبار ارسال ناموفق قطعی به بسته برمی‌گردد. تا وقتی نتیجه نامشخص است، ارسال دوباره انجام نده. ثبت درخواست به معنی تحویل قطعی یا خوانده‌شدن پیام نیست.</p></details>
      <p className={styles.terms}>پیش از خرید، <Link href="/privacy">قوانین استفاده و حریم خصوصی</Link> را بخوان. اعتبار برای خدمات سایت است و برداشت بانکی ندارد.</p>
    </section>
  </div>;
}
