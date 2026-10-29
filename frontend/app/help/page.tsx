import Link from "next/link";
import { Icon } from "@/components/icons";
import { Pricing } from "@/components/pricing";
import { StructuredData } from "@/components/structured-data";
import { helpQuestions, howItWorksSteps } from "@/lib/help-content";
import { pageJsonLd, publicMetadata } from "@/lib/seo";
export const metadata = publicMetadata("/help");

export default function HelpPage() {
  return (
    <div className="document-page wrap">
      <StructuredData data={pageJsonLd("/help", helpQuestions)} />
      <div className="account-heading">
        <h1>یک پیام خوب، از توجه شروع می‌شه.</h1>
        <p>
          بگم نگم برای یادآوری محترمانه و قدردانیه؛ هیچ جمله‌ای تضمین نمی‌کنه که
          مخاطب ناراحت نشه.
        </p>
      </div>
      <Pricing />
      <section className="guidelines" id="how-it-works">
        <h2>بگم نگم چطور کار می‌کند؟</h2>
        <ol className="prose-card">
          {howItWorksSteps.map(step => <li key={step.title}><h3>{step.title}</h3><p>{step.text}</p></li>)}
        </ol>
      </section>
      <section className="guidelines" id="write-respectfully">
        <h2>چطور حرفم رو بهتر برسونم؟</h2>
        <div className="guideline-grid">
          <article>
            <span>۰۱</span>
            <h3>رفتار رو ببین، نه شخصیت رو</h3>
            <p>
              «می‌شه موقع استراحت کمی آروم‌تر صحبت کنیم؟» بهتر از برچسب‌زدن به
              شخصیت کسیه.
            </p>
          </article>
          <article>
            <span>۰۲</span>
            <h3>چیزی رو بگو که قابل تغییره</h3>
            <p>
              بهداشت و رعایت فضای مشترک قابل یادآوری‌اند. ظاهر، هویت، بیماری و
              مسائل خصوصی محل قضاوت نیستند.
            </p>
          </article>
          <article>
            <span>۰۳</span>
            <h3>به یک بار گفتن بسنده کن</h3>
            <p>
              تکرار پیام و دور زدن قطع دریافت، کمک نیست. به انتخاب فرد برای
              دریافت‌نکردن احترام بذار.
            </p>
          </article>
          <article>
            <span>۰۴</span>
            <h3>خوبی‌ها رو هم بگو</h3>
            <p>
              یک تشکر کوتاه بابت خوش‌قولی، همراهی یا رعایت حال دیگران هم می‌تونه
              روز کسی رو بهتر کنه.
            </p>
          </article>
        </div>
      </section>
      <section className="faq-section">
        <h2>سؤال‌هایی که ممکنه داشته باشی</h2>
        {helpQuestions.map(faq => (
          <details key={faq.id} id={faq.id}>
            <summary>{faq.question}</summary>
            <p id={`${faq.id}-answer`}>{faq.answer}{"link" in faq && <> <Link href={faq.link.href} prefetch={false}>{faq.link.label}</Link></>}</p>
          </details>
        ))}
      </section>
      <div className="document-cta">
        <p>پیش از نوشتن پیام، <Link href="/privacy">حریم خصوصی و قوانین استفاده</Link> رو مرور کن.</p>
        <Link href="/#compose" className="button primary">
          نوشتن پیام <Icon name="arrow" size={18} />
        </Link>
      </div>
    </div>
  );
}
