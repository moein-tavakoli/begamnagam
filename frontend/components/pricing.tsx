"use client";
import Link from "next/link";
import { useApp } from "./app-provider";
import { toman } from "@/lib/format";
import { Icon } from "./icons";
import { ServiceState } from "./feedback";
import { FreeSendsBalance } from "./free-sends";

export function Pricing() {
  const { data } = useApp();
  return <section className="pricing-card">
    <h2>بسته‌های ارسال پیام</h2>
    <p>۳ ارسال اول هدیهٔ ماست؛ یک‌بار برای هر شمارهٔ تأییدشده. بعد از هدیه، هر ارسال یک اعتبار از بسته مصرف می‌کند؛ حتی اگر پیامک چندبخشی باشد.</p>
    <FreeSendsBalance />
    {!data ? <ServiceState /> : <div className="pricing-package-list">{(data.message_packages ?? []).filter(item => item.active).map(item => <article key={item.id}>
      <h3>{item.name}</h3><p>{new Intl.NumberFormat("fa-IR").format(item.message_count)} پیام</p><strong>{toman(item.price_toman)}</strong><small>قیمت کل بسته</small>
    </article>)}</div>}
    {data && !data.message_packages?.length && <p>فعلاً بستهٔ فعالی تعریف نشده است.</p>}
    <Link className="button primary" href="/credits" prefetch={false}>مشاهده و خرید بسته</Link>
    <div className="pricing-footnote"><Icon name="info" size={19} /><p>بسته را، در صورت فعال‌بودن، با کیف پول یا زرین‌پال می‌خری. اعتبار ارسال ناموفق قطعی به بسته برمی‌گردد؛ اعتبار کیف پول برداشت بانکی ندارد. ثبت در صف به معنی تحویل قطعی یا خوانده‌شدن پیام نیست.</p></div>
  </section>;
}
