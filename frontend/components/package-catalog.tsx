"use client";

import Link from 'next/link';
import { useApp } from './app-provider';
import { Icon } from './icons';
import { ServiceState } from './feedback';
import { PurchaseExamples } from './purchase-examples';
import { ConversionExposure } from './conversion-exposure';
import { creditCheckoutHref, creditPaymentMethods } from '@/lib/credit-purchases';
import { useCheckoutPreviewId } from '@/lib/use-checkout-preview-id';
import { perMessagePrice, toman } from '@/lib/format';
import styles from './credit-shop.module.css';

const fa = new Intl.NumberFormat('fa-IR');
export function PackageCatalog({ compact = false }: { compact?: boolean }) {
  const { data } = useApp();
  const previewId = useCheckoutPreviewId();
  const paymentClosed = creditPaymentMethods(data).status === 'closed';
  const packages = (data?.message_packages ?? []).filter(item => item.active);
  return <section className={styles.catalog} aria-label="بسته‌های پیام">
    {!compact && <div className={styles.gift}><span className={styles.giftIcon}><Icon name="heart" size={26}/></span><div><h2>اولین ۳ پیام، مهمان ما</h2><p>برای هر شمارهٔ تأییدشده، یک بار. بعد از آن، بستهٔ دلخواهت را انتخاب کن.</p></div><Link href="/#compose" className="button ghost">نوشتن اولین پیام <Icon name="arrow" size={17}/></Link></div>}
    <ServiceState/>
    {paymentClosed && <p className={styles.notice} role="status">خرید بسته فعلاً غیرفعال است. می‌توانی قیمت‌ها را بررسی کنی و از هدیه‌های باقی‌مانده‌ات استفاده کنی.</p>}
    {!compact && data?.conversion_experiment?.key === 'examples' && <ConversionExposure surface="pricing" />}
    {!compact && <PurchaseExamples />}
    {!compact && packages.length > 0 && data?.conversion_experiment?.key === 'price' && <ConversionExposure surface="pricing" />}
    <div className={styles.cards}>{packages.map((item, index) => <article key={item.id} className={`${styles.package} ${styles[`color${index % 4}`]}`} style={{animationDelay:`${index*60}ms`}}>
      <div className={styles.packageTop}><span>{item.name}</span><Icon name="chat" size={23}/></div>
      <h2 className={styles.units}>{fa.format(item.message_count)} <span>پیام</span></h2>
      <p className={styles.price}>{toman(item.price_toman)}<small>قیمت کل بسته</small><small>هر پیام {perMessagePrice(item.price_toman, item.message_count)}</small></p>
      <p className={styles.packageNote}><Icon name="check" size={16}/> هر ارسال، یک اعتبار</p>
      <Link className="button primary" href={creditCheckoutHref(previewId ?? '', item.id)} prefetch={false}>{paymentClosed ? 'بررسی بسته' : 'انتخاب بسته'} <Icon name="arrow" size={18}/></Link>
    </article>)}</div>
    {data && !packages.length && <p className={styles.empty}>فعلاً بستهٔ فعالی موجود نیست؛ کمی بعد دوباره سر بزن.</p>}
    {!compact && <div className={styles.assurances}><p><Icon name="shield" size={19}/> شمارهٔ حساب فرستنده به پیامک اضافه نمی‌شود.</p><p><Icon name="receipt" size={19}/> هر پیام یک اعتبار، حتی پیامک چندبخشی.</p><p><Icon name="refresh" size={19}/> اعتبار ارسال ناموفقِ قطعی به بسته برمی‌گردد.</p></div>}
  </section>;
}
