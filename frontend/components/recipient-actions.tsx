"use client";
import Link from 'next/link';
import {useEffect, useState} from 'react';
import {api, errorMessage} from '@/lib/api';
import {useApp} from './app-provider';
import {BusyButton, ErrorBox} from './feedback';

export function RecipientActions() {
  const {data} = useApp();
  const [token,setToken] = useState('');
  const [valid,setValid] = useState(false);
  const [canReport,setCanReport] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [reason,setReason] = useState('unwanted');
  const [details,setDetails] = useState('');
  const [checked,setChecked] = useState(false);
  useEffect(()=>{setToken(location.hash.slice(1));},[]);
  useEffect(()=>{
    if(!token || !data) return;
    let cancelled=false;
    void api<{active:boolean;can_report:boolean}>('/recipient/actions/inspect',{method:'POST',body:{token}})
      .then(value=>{if(!cancelled){setValid(value.active);setCanReport(value.can_report);}})
      .catch(e=>{if(!cancelled)setError(errorMessage(e));});
    return ()=>{cancelled=true;};
  },[token,!!data]);
  async function act(action:'stop'|'report') {
    setBusy(true);setError('');setNotice('');
    try {
      const result=await api<{receipt?:string}>('/recipient/actions/'+action,{method:'POST',body:{token,reason,details}});
      setNotice(action==='stop'?'دریافت پیام از همه فرستنده‌ها برای این شماره متوقف شد.':'گزارش ثبت شد و دریافت پیام متوقف شد. کد پیگیری: '+result.receipt);
      setDetails('');setChecked(false);
    } catch(e){setError(errorMessage(e));} finally {setBusy(false);}
  }
  return <div className="account-page wrap" data-update-blocked={!!details || busy}>
    <div className="account-heading"><span className="eyebrow">انتخاب با توست</span><h1>آرامش تو مهمه.</h1><p>برای توقف دریافت یا گزارش این پیام، لازم نیست حساب بسازی. فرستنده از هویت یا گزارش تو مطلع نمی‌شه.</p></div>
    <div className="account-card">
      <ErrorBox message={error}/>
      {!token && <p>لینک داخل پیامک را کامل باز کن. برای مدیریت شماره خودت هم می‌تونی از صفحه قطع دریافت استفاده کنی.</p>}
      {token && !valid && !error && <p role="status">در حال بررسی لینک…</p>}
      {valid && <>
        <h2>نمی‌خوای پیام دیگه‌ای دریافت کنی؟</h2>
        <p>این انتخاب، دریافت پیام از همه فرستنده‌های بگم نگم را متوقف می‌کنه. پیامی که قبلاً به شبکه تحویل شده قابل پس‌گرفتن نیست.</p>
        <BusyButton className="button primary full-width" busy={busy} onClick={()=>void act('stop')}>توقف دریافت همه پیام‌ها</BusyButton>
        {canReport && <details className="recipient-report"><summary>گزارش پیام ناخواسته یا آزاردهنده</summary>
          <form onSubmit={e=>{e.preventDefault();if(checked)void act('report');}}>
            <label htmlFor="report-reason">دلیل گزارش</label><select id="report-reason" value={reason} onChange={e=>setReason(e.target.value)}>
              <option value="unwanted">پیام ناخواسته</option><option value="harassment">احساس مزاحمت یا آزار</option><option value="wrong_number">شماره اشتباه</option><option value="other">دلیل دیگر</option>
            </select>
            <label htmlFor="report-details">توضیح اختیاری، حداکثر۵۰۰نویسه</label><textarea id="report-details" rows={4} maxLength={500} value={details} onChange={e=>setDetails(e.target.value)} aria-describedby="report-privacy"/>
            <p id="report-privacy" className="small muted">شماره، نشانی یا اطلاعات حساس ننویس. فقط پشتیبان مجاز توضیحت را می‌بینه.</p>
            <label className="checkbox-label"><input type="checkbox" checked={checked} onChange={e=>setChecked(e.target.checked)}/><span>می‌خواهم این گزارش ثبت و دریافت پیام برای این شماره متوقف شود.</span></label>
            <BusyButton className="button secondary full-width" busy={busy} disabled={!checked}>ثبت گزارش و توقف دریافت</BusyButton>
          </form></details>}
      </>}
      {notice && <p className="success-notice" role="status">{notice}</p>}
      <p className="small muted">این لینک را برای دیگران نفرست؛ دارندهٔ لینک می‌تواند دریافت را متوقف یا پیام را گزارش کند.</p>
      {data?.support_contact && <p>راه تماس پشتیبانی: <bdi>{data.support_contact}</bdi></p>}
      <Link href="/preferences">مدیریت شماره خودم با تأیید شماره</Link>
    </div>
  </div>;
}
