"use client";

import Link from 'next/link';
import { useApp } from './app-provider';
import { Icon } from './icons';
import { ServiceState } from './feedback';
import { toman } from '@/lib/format';
import styles from './credit-shop.module.css';

const fa = new Intl.NumberFormat('fa-IR');
export function PackageCatalog({ compact = false }: { compact?: boolean }) {
  const { data } = useApp();
  return <section className={styles.catalog} aria-label="بسته‌های پیام">
    {!compact && <div className={styles.gift}><span className={styles.giftIcon}><Icon name="heart" size={26}/></span><div><h2>اولین ۳ پیام، مهمان ما</h2><p>برای هر شمارهٔ تأییدشده، یک بار. بعد از آن، بستهٔ دلخواهت را انتخاب کن.</p></div><Link href="/#compose" className="button ghost">نوشتن اولین پیام <Icon name="arrow" size={17}/></Link></div>}
    <ServiceState/>
    <div className={styles.cards}>{(data?.message_packages ?? []).filter(p => p.active).map((item, index) => <article key={item.id} className={`${styles.package} ${styles[`color${index % 4}`]}`} style={{animationDelay:`${index*60}ms`}}>
      <div className={styles.packageTop}><span>{item.name}</span><Icon name="chat" size={23}/></div>
      <h2 className={styles.units}>{fa.format(item.message_count)} <span>پیام</span></h2>
      <p className={styles.price}>{toman(item.price_toman)}<small>قیمت کل بسته</small></p>
      <p className={styles.packageNote}><Icon name="check" size={16}/> هر ارسال، یک اعتبار</p>
      <Link className="button primary" href={`/credits?package=${item.id}`} prefetch={false}>انتخاب بسته <Icon name="arrow" size={18}/></Link>
    </article>)}</div>
    {data && !data.message_packages?.length && <p className={styles.empty}>فعلاً بستهٔ فعالی موجود نیست؛ کمی بعد دوباره سر بزن.</p>}
    {!compact && <div className={styles.assurances}><p><Icon name="shield" size={19}/> مشخصات فرستنده به گیرنده نمایش داده نمی‌شود.</p><p><Icon name="receipt" size={19}/> هر پیام یک اعتبار، حتی پیامک چندبخشی.</p><p><Icon name="refresh" size={19}/> اعتبار ارسال ناموفقِ قطعی به بسته برمی‌گردد.</p></div>}
  </section>;
}
