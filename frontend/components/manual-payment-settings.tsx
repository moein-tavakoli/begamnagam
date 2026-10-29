"use client";

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api, errorMessage } from '@/lib/api';

type Configuration = { values:{enabled:boolean;card_number:string;card_holder:string;bank_name:string;bale_username:string;telegram_username:string};revision:number;ready:boolean;problem:string };
export function ManualPaymentSettings({onFailure}:{onFailure:(e:unknown)=>void}){
  const [config,setConfig]=useState<Configuration|null>(null),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  const load=useCallback(async()=>{try{setConfig(await api<Configuration>('/manage/manual-payment-settings'));setError('');}catch(e){setError(errorMessage(e));onFailure(e);}},[onFailure]);
  useEffect(()=>{void load();},[load]);
  async function save(event:FormEvent<HTMLFormElement>){
    event.preventDefault();const form=new FormData(event.currentTarget);if(!config)return;setBusy(true);setNotice('');setError('');
    try{setConfig(await api<Configuration>('/manage/manual-payment-settings',{method:'POST',body:{revision:config.revision,reason:form.get('reason'),values:{enabled:form.get('enabled')==='on',card_number:String(form.get('card_number')||''),card_holder:String(form.get('card_holder')||''),bank_name:String(form.get('bank_name')||''),bale_username:String(form.get('bale_username')||''),telegram_username:String(form.get('telegram_username')||'')}}}));setNotice('تنظیمات ذخیره شد. کارت‌به‌کارت فقط با تأیید رسید توسط ادمین اعتبار می‌دهد.');}
    catch(e){setError(errorMessage(e));onFailure(e);}finally{setBusy(false);}
  }
  return <section className="manage-card"><div className="manage-section-heading"><h2>کارت مقصد و دریافت رسید</h2><button className="manage-button secondary" disabled={busy} onClick={()=>void load()}>تازه‌سازی</button></div>
    <p className="manage-notice">شمارهٔ کارت متعلق به دریافت‌کنندهٔ وجه است. برای رسید، شناسهٔ شخص پشتیبان را وارد کن که پیام خصوصی دریافت می‌کند. لینک کانال عمومی مناسب نیست. تصویر رسید در سایت ذخیره نمی‌شود.</p>
    {error && <p role="alert" className="manage-error">{error}</p>}{notice && <p role="status" className="manage-notice">{notice}</p>}
    {!config?<p role="status">در حال دریافت تنظیمات…</p>:<form className="manage-form" onSubmit={save} key={config.revision}>
      {config.problem && <p className="manage-notice">{config.problem}</p>}
      <div className="manage-two-columns"><label>شمارهٔ کارت مقصد<input name="card_number" dir="ltr" inputMode="numeric" autoComplete="off" maxLength={24} defaultValue={config.values.card_number} placeholder="۱۶ رقم"/></label><label>نام صاحب کارت<input name="card_holder" maxLength={80} defaultValue={config.values.card_holder}/></label></div>
      <label>نام بانک<input name="bank_name" maxLength={80} defaultValue={config.values.bank_name||''} placeholder="مثلاً بانک ملت"/></label>
      <div className="manage-two-columns"><label>شناسهٔ پشتیبان در بله<input name="bale_username" dir="ltr" autoComplete="off" maxLength={33} defaultValue={config.values.bale_username} placeholder="username"/></label><label>شناسهٔ پشتیبان در تلگرام<input name="telegram_username" dir="ltr" autoComplete="off" maxLength={33} defaultValue={config.values.telegram_username} placeholder="username"/></label></div>
      <p className="manage-muted">فقط شناسه، بدون لینک؛ حداقل یکی لازم است. شمارهٔ کارت و مرجع‌های بانکی در دیتابیس رمز‌شده‌اند. تغییر کارت، درخواست‌های قبلی را تغییر نمی‌دهد.</p>
      <label className="checkbox-label"><input name="enabled" type="checkbox" defaultChecked={config.values.enabled}/>خرید کارت‌به‌کارت در صفحهٔ پرداخت فعال باشد</label>
      <label>دلیل تغییر<input name="reason" minLength={3} maxLength={200} required/></label>
      <button className="manage-button primary" disabled={busy}>{busy?'در حال ذخیره…':'ذخیرهٔ تنظیمات'}</button>
    </form>}
  </section>;
}
