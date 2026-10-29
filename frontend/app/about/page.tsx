import Link from "next/link";
import { StructuredData } from "@/components/structured-data";
import { pageJsonLd, publicMetadata, serviceFacts } from "@/lib/seo";

export const metadata = publicMetadata("/about");

export default function AboutPage() {
  return (
    <article className="document-page wrap">
      <StructuredData data={pageJsonLd("/about")} />
      <header className="account-heading" id={serviceFacts[0].id}>
        <h1>{serviceFacts[0].title}</h1>
        <p>{serviceFacts[0].text}</p>
      </header>
      <div className="prose-card">
        {serviceFacts.slice(1).map(fact => (
          <section key={fact.id} id={fact.id} aria-labelledby={`${fact.id}-title`}>
            <h2 id={`${fact.id}-title`}>{fact.title}</h2>
            <p>{fact.text}</p>
          </section>
        ))}
        <section aria-labelledby="about-details">
          <h2 id="about-details">اطلاعات بیشتر</h2>
          <p>
            <Link href="/help#how-it-works">مراحل استفاده و پرسش‌های متداول</Link>،{" "}
            <Link href="/pricing">تعرفه‌ها و بسته‌ها</Link> و{" "}
            <Link href="/privacy">قوانین و حریم خصوصی</Link> را بخوان.
            پیوندهای سرویس در <Link href="/links">صفحهٔ شبکه‌های اجتماعی</Link> قرار دارند.
          </p>
        </section>
      </div>
      <div className="document-cta">
        <Link href="/#compose" className="button primary">نوشتن پیام</Link>
      </div>
    </article>
  );
}
