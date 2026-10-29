"use client";

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { api, approvedPaymentRedirect, createIdempotencyKey, errorMessage, type CreditPurchase } from '@/lib/api';
import { toman } from '@/lib/format';
import { purchaseIntentAfterResponse, type PurchaseIntent } from '@/lib/credit-purchases';
import { openPurchase, receiptText, safeReceiptChannels } from '@/lib/manual-payments';
import { useApp } from './app-provider';
import { AuthGate } from './auth-gate';
import { ErrorBox, ServiceState } from './feedback';
import { Icon } from './icons';
import styles from './credit-shop.module.css';

const fa = new Intl.NumberFormat('fa-IR');
const statuses: Record<string,string> = { credited:'بسته‌ات فعال شد', wallet_returned:'مبلغ به کیف پول برگشت؛ بسته فعال نشد', awaiting_transfer:'درخواست آماده است؛ پرداخت و ارسال رسید', awaiting_review:'رسیدت در انتظار بررسی ادمین است', rejected:'این رسید تأیید نشد', cancelled:'درخواست لغو شد', unknown:'نتیجه هنوز مشخص نیست؛ دوباره پرداخت نکن', pending:'در انتظار تأیید پرداخت', created:'درخواست خرید ثبت شد', verified:'در حال تکمیل اعتبار', failed:'پرداخت تأیید نشد؛ اعتباری اضافه نشده' };

export function CreditPackages({ inline = false }: { inline?: boolean }) {
  if (inline) return <section className={styles.inline}><h3>برای ادامه، اعتبار پیام بگیر</h3><p>بسته‌های فعال را ببین و پس از خرید، برای ارسال همین پیام برگرد.</p><Link className="button primary" href="/credits" prefetch={false}>انتخاب بستهٔ پیام <Icon name="arrow" size={18}/></Link></section>;
  return <CreditCheckout/>;
}

function CreditCheckout() {
  const {data,reload} = useApp();
  const [selected,setSelected]=useState<number|null>(null),[method,setMethod]=useState<'card'|'gateway'>('gateway');
  const [consent,setConsent]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [purchases,setPurchases]=useState<CreditPurchase[]>([]),[purchase,setPurchase]=useState<CreditPurchase|null>(null);
  const [listReady,setListReady]=useState(false),[uncertain,setUncertain]=useState(false);
  const intent=useRef<PurchaseIntent|null>(null),generation=useRef(0);
  const options=data?.payment_options;
  const packages=(data?.message_packages??[]).filter(item=>item.active);
  const selectedPackage=packages.find(item=>item.id===selected);
  const pending=purchases.filter(item=>openPurchase(item.status));
  const gateway=!!options?.gateway_enabled || !!(data?.demo_mode && data.payment_backend==='demo');
  const enabled=method==='card' ? !!options?.card_enabled : gateway;
  const load=useCallback(async()=>{
    const current=++generation.current;
    try {
      const result=await api<{purchases:CreditPurchase[]}>('/credit-purchases');
      if(current!==generation.current)return;
      setPurchases(result.purchases);setListReady(true);setError('');
      const id=new URLSearchParams(window.location.search).get('purchase');
      setPurchase(previous=>result.purchases.find(p=>p.id===previous?.id || p.id===id) || result.purchases.find(p=>openPurchase(p.status)) || null);
    } catch(e){if(current===generation.current){setError(errorMessage(e));setListReady(false);}}
  },[]);
  useEffect(()=>{
    if(data?.authenticated) void load();
    return()=>{generation.current+=1;};
  },[data?.authenticated,data?.session_identity,load]);
  useEffect(()=>{
    if(!selected && packages.length){const id=Number(new URLSearchParams(window.location.search).get('package'));setSelected(packages.some(p=>p.id===id)?id:packages[0].id);}
  },[selected,packages]);
  useEffect(()=>{if(!gateway && options?.card_enabled)setMethod('card');},[gateway,options?.card_enabled]);
  function accept(result:CreditPurchase){
    setPurchase(result);setPurchases(items=>[result,...items.filter(p=>p.id!==result.id)]);
    if(intent.current) intent.current=purchaseIntentAfterResponse(intent.current,result);
    setUncertain(false);
  }
  async function buy(){
    if(!selectedPackage)return;
    setBusy(true);setError('');const current=++generation.current;
    intent.current ??= {packageId:selectedPackage.id,value:createIdempotencyKey()};
    try{
      const result=await api<CreditPurchase>('/credit-purchases',{method:'POST',idempotencyKey:intent.current.value,body:{package_id:selectedPackage.id,package_revision:selectedPackage.revision,payment_method:method,wallet_consent:consent,wallet_terms_version:options?.wallet_terms_version}});
      if(current!==generation.current)return;
      accept(result);
      if(result.redirect_url)window.location.assign(approvedPaymentRedirect(result.redirect_url,!!data?.demo_mode));
      else if(result.status==='credited')await reload();
    }catch(e){if(current===generation.current){setError(errorMessage(e));setUncertain(true);}}
    finally{if(current===generation.current)setBusy(false);}
  }
  async function update(item:CreditPurchase,path='',body?:unknown){
    setBusy(true);setError('');const current=++generation.current;
    try{
      const result=await api<CreditPurchase>(`/credit-purchases/${item.id}${path}`,path?{method:'POST',body}:{ });
      if(current!==generation.current)return;
      accept(result);if(result.status==='credited')await reload();
    }catch(e){if(current===generation.current)setError(errorMessage(e));}
    finally{if(current===generation.current)setBusy(false);}
  }
  return <div className={styles.shop} data-credit-shop="true" aria-busy={busy || undefined}>
    <div className={styles.stack}>
      <ServiceState/>
      <ErrorBox message={error}/>
      {uncertain && <div className={styles.notice}>نتیجهٔ درخواست قبلی مشخص نیست. ابتدا وضعیت را بررسی کن؛ برای تکرار همان درخواست، بسته و روش را تغییر نده.<button className="text-button" type="button" disabled={busy} onClick={()=>void load()}>بررسی خریدهای من</button></div>}
      {pending.filter(item=>item.id!==purchase?.id).map(item=><div className={styles.notice} key={item.id}><p>{item.name} · {statuses[item.status]}</p><button className="button ghost" disabled={busy} type="button" onClick={()=>setPurchase(item)}>مشاهده و پیگیری</button></div>)}
      {purchase && <PurchaseResult key={purchase.id} purchase={purchase} demo={!!data?.demo_mode} busy={busy} onUpdate={update}/>}
      {!pending.length && <><section className={styles.panel}>
        <h2 className={styles.step}><span>۱</span> بسته‌ات را انتخاب کن</h2>
        <fieldset className={styles.choices} disabled={busy || !!pending.length || uncertain} aria-label="انتخاب بسته">
          {packages.map(item=><label className={`${styles.choice} ${styles.packageChoice}`} key={item.id}><input type="radio" name="credit-package" value={item.id} checked={selected===item.id} onChange={()=>{setSelected(item.id);intent.current=null;}}/><span><strong>{fa.format(item.message_count)} پیام</strong><small>{item.name}</small><small>{toman(item.price_toman)}</small></span></label>)}
        </fieldset>
        {!packages.length && data && <p className={styles.muted}>فعلاً بستهٔ فعالی موجود نیست.</p>}
        <Link href="/pricing" className="text-button">مقایسهٔ تعرفه‌ها و شرایط</Link>
      </section>
      <section className={styles.panel}>
        <h2 className={styles.step}><span>۲</span> روش پرداخت</h2>
        <fieldset className={styles.choices} disabled={busy || !!pending.length || uncertain} aria-label="انتخاب روش پرداخت">
          <label className={styles.choice}><input type="radio" name="payment-method" value="gateway" checked={method==='gateway'} disabled={!gateway} onChange={()=>{setMethod('gateway');intent.current=null;setConsent(false);}}/><span><strong>زرین‌پال</strong><small>{gateway?'فعال‌سازی خودکار بسته':'فعلاً غیرفعال'}</small></span></label>
          <label className={styles.choice}><input type="radio" name="payment-method" value="card" checked={method==='card'} disabled={!options?.card_enabled} onChange={()=>{setMethod('card');intent.current=null;setConsent(false);}}/><span><strong>کارت‌به‌کارت</strong><small>{options?.card_enabled?'پس از تأیید ادمین':'فعلاً غیرفعال'}</small></span></label>
        </fieldset>
        {!gateway && !options?.card_enabled && <p className={styles.notice}>خرید فعلاً باز نیست. می‌توانی بسته‌ها را ببینی و از هدیه‌های باقی‌مانده استفاده کنی.</p>}
        {data?.authenticated ? <><label className={styles.consent}><input type="checkbox" checked={consent} disabled={busy || !!pending.length} onChange={e=>setConsent(e.target.checked)}/><span>اعتبار خرید برای خدمات سایت است و برداشت بانکی ندارد. برگشت هزینهٔ پرداخت پولی به کیف پول انجام می‌شود؛ اعتبار ارسال ناموفق قطعی به بسته برمی‌گردد. <Link href="/privacy">قوانین استفاده</Link> را می‌پذیرم.</span></label>
          <div className={styles.total}><span>مبلغ نهایی بسته</span><strong>{selectedPackage?toman(selectedPackage.price_toman):'—'}</strong></div>
          <button className={`button primary ${styles.pay}`} type="button" disabled={busy || !!pending.length || !listReady || !selectedPackage || !consent || !enabled} onClick={()=>void buy()}>{busy?<><span className="spinner"/> در حال ثبت…</>:uncertain?'تکرار همان درخواست':method==='card'?'دریافت شمارهٔ کارت و ثبت خرید':data?.demo_mode?'خرید آزمایشی بسته':'پرداخت با زرین‌پال'}<Icon name="arrow" size={18}/></button>
          {!listReady && <button className="text-button" type="button" disabled={busy} onClick={()=>void load()}>دریافت وضعیت خریدهای قبلی</button>}
          <p className={styles.muted}>{method==='card'?'رسید را در بله یا تلگرام برای پشتیبانی می‌فرستی؛ پس از تأیید، اعتبار اضافه می‌شود.':'بعد از تأیید خودِ درگاه، بسته خودکار فعال می‌شود؛ ارسال رسید مانع فعال‌شدن آن نیست.'}</p></> : <AuthGate purpose="برای خرید بسته، شمارهٔ خودت را تأیید کن."/>}
      </section>
      </>}
    </div>
    <aside className={styles.stack}>
      {data?.authenticated && <section className={styles.balance}><h2>موجودی پیام‌های تو</h2><div className={styles.balances}><p>هدیه<strong>{fa.format(data.free_sends_remaining??0)}</strong></p><p>اعتبار بسته<strong>{fa.format(data.purchased_sends_remaining??0)}</strong></p></div></section>}
      <section className={styles.panel}><Icon name="heart" size={27}/><h3>هدیه‌ها سر جای خودشان‌اند</h3><p className={styles.muted}>اول هدیه‌های باقی‌مانده مصرف می‌شوند، بعد اعتبار بسته. هر ارسال، حتی پیامک چندبخشی، یک اعتبار دارد.</p><Link href="/#compose" className="text-button">برگشت به نوشتن پیام <Icon name="arrow" size={16}/></Link></section>
      {purchases.length>0 && <details className={styles.history}><summary>خریدهای اخیر من</summary>{purchases.slice(0,12).map(item=><button type="button" disabled={busy} key={item.id} onClick={()=>setPurchase(item)}>{item.name} · {fa.format(item.message_count)} پیام<span>{statuses[item.status]||'در حال بررسی'} · {toman(item.amount_toman)}</span></button>)}</details>}
    </aside>
  </div>;
}

function PurchaseResult({purchase,demo,busy,onUpdate}:{purchase:CreditPurchase;demo:boolean;busy:boolean;onUpdate:(p:CreditPurchase,path?:string,body?:unknown)=>Promise<void>}){
  const [copied,setCopied]=useState('');
  const resultRef=useRef<HTMLElement>(null);
  useEffect(()=>{resultRef.current?.focus({preventScroll:true});resultRef.current?.scrollIntoView({block:'start',behavior:'instant'});},[]);
  const active=purchase.status==='awaiting_transfer',review=purchase.status==='awaiting_review';
  const channels=safeReceiptChannels(purchase.receipt_channels);
  async function copy(value:string,label:string){try{await navigator.clipboard.writeText(value);setCopied(label+' کپی شد.');}catch{setCopied('کپی خودکار انجام نشد؛ متن نمایش‌داده‌شده را انتخاب و کپی کن.');}}
  async function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=new FormData(event.currentTarget);await onUpdate(purchase,'/receipt',{receipt_sent:form.get('receipt_sent')==='on',reference:String(form.get('reference')||'')});}
  return <section className={`${styles.status} ${purchase.status==='credited'?styles.success:''}`} aria-label="وضعیت خرید" role="status" ref={resultRef} tabIndex={-1}>
    <h2><Icon name={purchase.status==='credited'?'check':'clock'} size={22}/>{statuses[purchase.status]||'خرید نیازمند بررسی است'}</h2>
    <p>{purchase.name} · {fa.format(purchase.message_count)} پیام · <strong>{toman(purchase.amount_toman)}</strong></p>
    <p className={styles.muted}>شناسهٔ خرید: <bdi>{purchase.id}</bdi></p>
    {demo && <p className={styles.notice}>این خرید آزمایشی است؛ هیچ وجهی منتقل نمی‌شود و اعتبار آن فقط در محیط آزمایشی است.</p>}
    {purchase.status==='rejected' && <p>دلیل بررسی: {purchase.review_note || 'برای پیگیری با پشتیبانی تماس بگیر.'}</p>}
    {active && purchase.card && <><p>مبلغ دقیق بسته را به کارت زیر واریز کن، سپس تصویر رسید و شناسهٔ خرید را برای پشتیبانی بفرست.</p><div className={styles.bankCard}><small>{purchase.card.bank_name || "کارت مقصدِ همین درخواست"}</small><bdi dir="ltr">{purchase.card.number.replace(/(.{4})(?=.)/g,'$1 ')}</bdi><p>{purchase.card.holder}</p><button type="button" className={styles.copyButton} onClick={()=>void copy(purchase.card!.number,'شمارهٔ کارت')}>کپی شمارهٔ کارت</button></div></>}
    {review && <p>ثبت ارسال رسید انجام شد. اعتبار پس از تطبیق و تأیید ادمین اضافه می‌شود؛ دوباره واریز نکن.</p>}
    {(active || review || purchase.status==='credited') && <div className={styles.receipt}>
      <h3>{purchase.status==='credited'?'ارسال رسید برای پشتیبانی':'ارسال تصویر رسید'}</h3>
      <p>{purchase.status==='credited'?'بسته فعال است. در صورت نیاز، تصویر رسید و مشخصات خرید را از راه‌های زیر برای پشتیبانی بفرست.':'متن زیر را همراه تصویر رسید در بله یا تلگرام برای پشتیبانی بفرست.'}</p>
      <pre>{receiptText(purchase)}</pre><button className="button ghost" type="button" onClick={()=>void copy(receiptText(purchase),'مشخصات خرید')}>کپی مشخصات خرید</button>
      <div className={styles.receiptLinks}>{channels.map(channel=><a className="button ghost" key={channel.name} href={channel.url} target="_blank" rel="noopener noreferrer">{channel.name==='bale'?'ارسال رسید در بله':'ارسال رسید در تلگرام'} ↗<span className="sr-only">در زبانهٔ جدید</span></a>)}</div>
      {!channels.length && <p className={styles.muted}>راه ارتباط ارسال رسید هنوز تنظیم نشده است. شناسهٔ خرید را برای پیگیری نگه دار.</p>}
      {active && <form className={styles.receiptForm} onSubmit={submit}>
        <label>شمارهٔ پیگیری بانکی (اختیاری)<input type="text" name="reference" minLength={6} maxLength={64} inputMode="numeric" autoComplete="off" dir="ltr" placeholder="شمارهٔ روی رسید" disabled={busy}/></label>
        <label className={styles.consent}><input type="checkbox" name="receipt_sent" required disabled={busy}/><span>تصویر رسید و شناسهٔ این خرید را برای پشتیبانی فرستادم.</span></label>
        <button className="button primary" disabled={busy}>{busy?'در حال ثبت…':'رسید را فرستادم؛ ثبت برای بررسی'}</button>
      </form>}
    </div>}
    <p className={styles.muted} aria-live="polite">{copied}</p>
    <div className={styles.statusActions}>{purchase.redirect_url && purchase.status==='pending' && <a className="button primary" href={approvedPaymentRedirect(purchase.redirect_url,demo)}>ادامهٔ همان پرداخت</a>}
      <button type="button" className="button ghost" disabled={busy} onClick={()=>void onUpdate(purchase)}>بررسی وضعیت</button>
      {active && <button type="button" className="button ghost" disabled={busy} onClick={()=>{if(window.confirm('فقط اگر وجهی واریز نکرده‌ای، درخواست را لغو کن. لغو شود؟'))void onUpdate(purchase,'/cancel-card',{});}}>واریز نکردم؛ لغو درخواست</button>}
      {purchase.status==='credited' && <Link href="/#compose" className="button primary">حالا پیام بنویس <Icon name="arrow" size={17}/></Link>}
    </div>
  </section>;
}
