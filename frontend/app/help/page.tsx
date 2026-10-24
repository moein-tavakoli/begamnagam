import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/icons";
import { Pricing } from "@/components/pricing";
export const metadata: Metadata = { title: "راهنما و هزینه" };

export default function HelpPage() {
  return (
    <div className="document-page wrap">
      <Link className="back-link" href="/">
        بازگشت به خانه <Icon name="arrow" size={16} />
      </Link>
      <div className="account-heading">
        <span className="eyebrow">قبل از فرستادن، با هم مرور کنیم</span>
        <h1>یک پیام خوب، از توجه شروع می‌شه.</h1>
        <p>
          بگم نگم برای یادآوری محترمانه و قدردانیه؛ هیچ جمله‌ای تضمین نمی‌کنه که
          مخاطب ناراحت نشه.
        </p>
      </div>
      <Pricing />
      <section className="guidelines" id="how-it-works">
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
        <details>
          <summary>گیرنده می‌فهمه پیام از طرف کیه؟</summary>
          <p>
            اسم و شماره فرستنده در پیام گیرنده نمایش داده نمی‌شه. سرویس برای
            کنترل سوءاستفاده، شماره تأییدشده فرستنده و سوابق درخواست رو نگه
            می‌داره. ناشناس‌بودن برای گیرنده، به معنی ناشناس‌بودن برای سرویس
            نیست.
          </p>
        </details>
        <details>
          <summary>می‌شه به پیام پاسخ داد؟</summary>
          <p>
            خیر. بگم نگم گفت‌وگو، چت، پروفایل عمومی یا راه ارتباط مستقیم بین دو
            نفر نداره.
          </p>
        </details>
        <details>
          <summary>هوش مصنوعی دقیقاً چه کاری می‌کنه؟</summary>
          <p>
            در حالت پایه، منظور شما به متن آمادهٔ بررسی‌شده تبدیل می‌شه. اگر مدل
            زبانی فعال باشه، فقط به انتخاب از میان متن‌های بررسی‌شده کمک می‌کنه.
            متن آزاد مدل مستقیماً برای گیرنده ارسال نمی‌شه. همیشه متن نهایی رو
            قبل از ادامه می‌بینی.
          </p>
        </details>
        <details>
          <summary>اگر پیام نخواستم، چطور دریافت رو قطع کنم؟</summary>
          <p>
            در <Link href="/preferences">صفحه قطع دریافت</Link> شماره خودت رو
            تأیید کن و دریافت تمام پیام‌های سرویس رو متوقف کن. همین‌جا می‌تونی
            دوباره فعالش کنی.
          </p>
        </details>
        <details>
          <summary>وضعیت ارسال یعنی پیام خونده شده؟</summary>
          <p>
            خیر. وضعیت صف یا ارسال، وضعیت پردازش سیستم و سرویس پیامکی رو نشون
            می‌ده؛ تأیید نمی‌کنه که کسی پیام رو دیده یا خونده.
          </p>
        </details>
        <details>
          <summary>نسخه آزمایشی پیامک واقعی می‌فرسته؟</summary>
          <p>
            در حالت آزمایشی، کد ورود با برچسب «کد ورود آزمایشی» در صفحه نمایش
            داده می‌شه و پرداخت و ارسال شبیه‌سازی می‌شن. هیچ پولی کسر نمی‌شه و
            پیامکی ارسال نمی‌شه.
          </p>
        </details>
      </section>
      <div className="document-cta">
        <p>یک حرف کوچک، با نیت خوب داری؟</p>
        <Link href="/#compose" className="button primary">
          نوشتن پیام <Icon name="arrow" size={18} />
        </Link>
      </div>
    </div>
  );
}
