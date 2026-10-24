import Link from "next/link";
import { Composer } from "@/components/composer";
import { Icon } from "@/components/icons";
import { LetterFlight } from "@/components/letter-flight";

export default function Home() {
  return (
    <>
      <section className="hero wrap" aria-labelledby="welcome-title">
        <div className="hero-copy">
          <span className="hero-eyebrow"><Icon name="sparkle" size={18} /> حرف‌های کوچیک، حالِ بهتر</span>
          <h1 id="welcome-title">یه حرف خوب،<br />یه <span className="highlight-text">حال خوب‌تر.</span></h1>
          <p className="hero-description">تشکر، دلگرمی یا یه یادآوری دوستانه؛<br />حرفت رو با احترام برسون، بدون نمایش اسمت به گیرنده.</p>
          <a href="#compose" className="button primary hero-cta">بزن بریم، حرفم رو بگم <Icon name="arrow" size={20} /></a>
          <Link href="/help" className="hero-help">اول ببینم چطوری کار می‌کنه</Link>
        </div>
        <div className="hero-art"><LetterFlight /><span className="art-sticker">یه کم مهربونی، از طرف تو <Icon name="heart" size={16} /></span></div>
      </section>
      <div className="promise-strip wrap" aria-label="اصول بگم نگم">
        <span><Icon name="shield" size={18} /> هویت پنهان برای گیرنده</span>
        <span><Icon name="heart" size={18} /> حق قطع دریافت برای همه</span>
        <span><Icon name="sparkle" size={18} /> تأیید متن قبل از ارسال</span>
      </div>
      <Composer />
      <section className="how-section wrap" id="how-it-works">
        <div className="section-heading"><span className="eyebrow">پیچیده‌اش نمی‌کنیم</span><h2>از حرف تو، تا لبخند اون.</h2><p>سه قدم کوچیک برای یه پیام با ملاحظه.</p></div>
        <div className="how-grid">
          <article><span className="how-icon"><Icon name="chat" size={27} /><small>۱</small></span><h3>تو بگو چی توی دلته</h3><p>موضوع رو انتخاب کن؛ یه تشکر قشنگ یا یه یادآوری درباره رفتاری قابل تغییر.</p></article>
          <article><span className="how-icon"><Icon name="sparkle" size={27} /><small>۲</small></span><h3>کلمه‌هاش رو با هم ببینیم</h3><p>یک متن آماده و بررسی‌شده پیشنهاد می‌دیم. اول بخون، بعد تأییدش کن.</p></article>
          <article><span className="how-icon"><Icon name="phone" size={27} /><small>۳</small></span><h3>با احترام به دستش برسه</h3><p>شماره‌ها و مبلغ رو بررسی کن. فعلاً پرداخت و ارسال فقط آزمایشیه.</p></article>
        </div>
      </section>
      <section className="care-section wrap"><span className="care-illustration"><Icon name="heart" size={58} /></span><div><span className="eyebrow">مهربونی، دوطرفه‌ست</span><h2>حقِ نشنیدن هم محترمه.</h2><p>حتی یک پیام با نیت خوب ممکنه کسی رو ناراحت کنه. درباره رفتار حرف بزنیم، نه شخصیت آدم‌ها؛ و به انتخابشون احترام بذاریم.</p><Link href="/preferences" className="text-link">پیام نمی‌خوام؛ دریافت رو متوقف کنم <Icon name="arrow" size={18} /></Link></div></section>
    </>
  );
}
