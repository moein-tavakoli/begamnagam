"use client";
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {useEffect, useRef, useState} from 'react';
import {api, ApiError, errorMessage} from '@/lib/api';
import {phoneInput, validPhone} from '@/lib/format';
import {actionFromFragment, isShortRecipientCode, replyTokenFromFragment} from '@/lib/recipient-links';
import {useApp} from './app-provider';
import {AuthGate} from './auth-gate';
import {Composer} from './composer';
import {BusyButton, ErrorBox} from './feedback';
import styles from './recipient-actions.module.css';

export function RecipientActions() {
  const [fragment,setFragment] = useState<string | null>(null);
  useEffect(()=>{
    const readFragment=()=>setFragment(location.hash.slice(1));
    readFragment();
    window.addEventListener('hashchange',readFragment);
    return ()=>window.removeEventListener('hashchange',readFragment);
  },[]);
  if (fragment === null) return null;
  const action = actionFromFragment(fragment);
  if (action) {
    const {token} = action;
    const choicesHref = `#${token}`;
    if (action.action === 'reply') return <AnonymousReply key={fragment} token={token} choicesHref={choicesHref}/>;
    if (action.action === 'stop') return <OptOut key={fragment} token={token} choicesHref={choicesHref}/>;
    return <RecipientActionMenu key={fragment} href={choicesHref}/>;
  }
  const replyToken = replyTokenFromFragment(fragment);
  return replyToken
    ? <AnonymousReply key={fragment} token={replyToken}/>
    : <OptOut key={fragment} token={fragment}/>;
}

function RecipientActionMenu({ href }: { href: string }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
  }, []);

  return <section className={`account-page wrap ${styles.menu}`} aria-labelledby="recipient-actions-title">
    <div className={`account-card ${styles.card}`}>
      <h1 id="recipient-actions-title" ref={heading} tabIndex={-1}>پاسخ یا لغو دریافت</h1>
      <div className={styles.actions}>
        <a className="button primary" href={href + '/reply'}>پاسخ</a>
        <a className="button ghost" href={href + '/stop'}>لغو دریافت</a>
      </div>
    </div>
  </section>;
}

function AnonymousReply({token, choicesHref}:{token:string; choicesHref?: string}) {
  const router=useRouter();
  const {data,loading,error:bootstrapError,reload}=useApp();
  const [verified,setVerified]=useState(false);
  const [failure,setFailure]=useState<{message:string;canSwitch:boolean}|null>(null);
  const [switching,setSwitching]=useState(false);
  const [inspection,setInspection]=useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const authenticated=!!data?.authenticated;
  useEffect(() => {
    if (choicesHref) heading.current?.focus();
  }, [choicesHref]);
  useEffect(()=>{
    if (!authenticated) return;
    const controller=new AbortController();
    void api<{active:boolean}>('/recipient/actions/reply',{method:'POST',body:{token},signal:controller.signal})
      .then(result=>{if(!controller.signal.aborted)setVerified(result.active);})
      .catch(error=>{
        if(!controller.signal.aborted)
          setFailure({message:errorMessage(error),canSwitch:error instanceof ApiError && error.code==='reply_unavailable'});
      });
    return ()=>controller.abort();
  },[authenticated,data?.session_identity,token,inspection]);
  const canReview=data?.rewrite_mode==='gapgpt' || data?.rewrite_mode==='ollama';
  if (authenticated && verified && canReview)
    return <Composer replyToken={token} onExit={() => {
      if (choicesHref) location.hash = choicesHref;
      else router.push('/');
    }} onReplyUnavailable={message=>{
      setVerified(false);
      setFailure({message,canSwitch:true});
    }}/>;
  return <div className="account-page wrap">
    <div className="account-heading"><h1 ref={heading} tabIndex={choicesHref ? -1 : undefined}>پاسخ ناشناس</h1><p>پاسخ از همین‌جا برای طرف مقابل فرستاده می‌شود و نام و شمارهٔ شما در پیامک دیده نمی‌شود.</p></div>
    <div className="account-card">
      <ErrorBox message={bootstrapError || failure?.message || ''}/>
      {(!data && loading) || (authenticated && !verified && !failure)
        ? <p role="status">در حال بررسی لینک پاسخ…</p>
        : null}
      {authenticated && verified && !canReview && <p role="status">بازبینی پاسخ موقتاً در دسترس نیست. کمی بعد همین لینک را دوباره باز کن.</p>}
      {failure?.canSwitch && !switching && <button type="button" className="button secondary" onClick={()=>setSwitching(true)}>تأیید شمارهٔ دیگری</button>}
      {(bootstrapError || (failure && !failure.canSwitch)) && <button type="button" className="button secondary" onClick={()=>{
        setFailure(null);
        void reload().then(()=>setInspection(attempt=>attempt+1));
      }}>تلاش دوباره</button>}
      {data && (!authenticated || switching) && <AuthGate forceReverify={switching} purpose="همان شماره‌ای را تأیید کن که پیامک را دریافت کرده."/>}
      {choicesHref ? <a href={choicesHref} className="text-button">بازگشت به گزینه‌ها</a>
        : <Link href="/">بازگشت به بگم نگم</Link>}
    </div>
  </div>;
}

function OptOut({token, choicesHref}:{token:string; choicesHref?: string}) {
  const {data} = useApp();
  const heading = useRef<HTMLHeadingElement>(null);
  const [valid,setValid] = useState(false);
  const [canReport,setCanReport] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [phone,setPhone] = useState('');
  const [reason,setReason] = useState('unwanted');
  const [details,setDetails] = useState('');
  const [checked,setChecked] = useState(false);
  const needsPhone = isShortRecipientCode(token);
  const canAct = !needsPhone || validPhone(phone);
  useEffect(() => {
    if (choicesHref) heading.current?.focus();
  }, [choicesHref]);
  useEffect(()=>{
    if(!token || !data) return;
    let cancelled=false;
    void api<{active:boolean;can_report:boolean}>('/recipient/actions/inspect',{method:'POST',body:{token}})
      .then(value=>{if(!cancelled){setValid(value.active);setCanReport(value.can_report);}})
      .catch(e=>{if(!cancelled)setError(errorMessage(e));});
    return ()=>{cancelled=true;};
  },[token,!!data]);
  async function act(action:'stop'|'report') {
    if (!canAct) return;
    setBusy(true);setError('');setNotice('');
    try {
      const result=await api<{receipt?:string}>('/recipient/actions/'+action,{
        method:'POST', body:{token,reason,details,...(needsPhone ? {phone} : {})},
      });
      setNotice(action==='stop'?'دریافت پیام از همه فرستنده‌ها برای این شماره متوقف شد.':'گزارش ثبت شد و دریافت پیام متوقف شد. کد پیگیری: '+result.receipt);
      setDetails('');setChecked(false);
    } catch(e){setError(errorMessage(e));} finally {setBusy(false);}
  }
  return <div className="account-page wrap" data-update-blocked={!!details || busy}>
    <div className="account-heading"><h1 ref={heading} tabIndex={choicesHref ? -1 : undefined}>آرامش تو مهمه.</h1><p>برای توقف دریافت یا گزارش این پیام، لازم نیست حساب بسازی. فرستنده از هویت یا گزارش تو مطلع نمی‌شه.</p></div>
    <div className="account-card">
      <ErrorBox message={error}/>
      {!token && <p>لینک داخل پیامک را کامل باز کن. برای مدیریت شماره خودت هم می‌تونی از صفحه قطع دریافت استفاده کنی.</p>}
      {token && !valid && !error && <p role="status">در حال بررسی لینک…</p>}
      {valid && <>
        <h2>نمی‌خوای پیام دیگه‌ای دریافت کنی؟</h2>
        <p>این انتخاب، دریافت پیام از همه فرستنده‌های بگم نگم را متوقف می‌کنه. پیامی که قبلاً به شبکه تحویل شده قابل پس‌گرفتن نیست.</p>
        {needsPhone && <div>
          <label htmlFor="recipient-confirm-phone">شماره‌ای که این پیامک را دریافت کرده</label>
          <input id="recipient-confirm-phone" className="phone-number-input" type="tel" inputMode="numeric"
            autoComplete="tel-national" dir="ltr" value={phone} disabled={busy}
            onChange={event=>setPhone(phoneInput(event.target.value))}/>
        </div>}
        <BusyButton className="button primary full-width" busy={busy} disabled={!canAct} onClick={()=>void act('stop')}>توقف دریافت همه پیام‌ها</BusyButton>
        {canReport && <details className="recipient-report"><summary>گزارش پیام ناخواسته یا آزاردهنده</summary>
          <form onSubmit={e=>{e.preventDefault();if(checked)void act('report');}}>
            <label htmlFor="report-reason">دلیل گزارش</label><select id="report-reason" value={reason} onChange={e=>setReason(e.target.value)}>
              <option value="unwanted">پیام ناخواسته</option><option value="harassment">احساس مزاحمت یا آزار</option><option value="wrong_number">شماره اشتباه</option><option value="other">دلیل دیگر</option>
            </select>
            <label htmlFor="report-details">توضیح اختیاری، حداکثر۵۰۰نویسه</label><textarea id="report-details" rows={4} maxLength={500} value={details} onChange={e=>setDetails(e.target.value)} aria-describedby="report-privacy"/>
            <p id="report-privacy" className="small muted">شماره، نشانی یا اطلاعات حساس ننویس. فقط پشتیبان مجاز توضیحت را می‌بینه.</p>
            <label className="checkbox-label"><input type="checkbox" checked={checked} onChange={e=>setChecked(e.target.checked)}/><span>می‌خواهم این گزارش ثبت و دریافت پیام برای این شماره متوقف شود.</span></label>
            <BusyButton className="button secondary full-width" busy={busy} disabled={!checked || !canAct}>ثبت گزارش و توقف دریافت</BusyButton>
          </form></details>}
      </>}
      {notice && <p className="success-notice" role="status">{notice}</p>}
      <p className="small muted">این لینک را برای دیگران نفرست.</p>
      {data?.support_contact && <p>راه تماس پشتیبانی: <bdi>{data.support_contact}</bdi></p>}
      <Link href="/preferences">مدیریت شماره خودم با تأیید شماره</Link>
      {choicesHref && <div><a href={choicesHref} className="text-button">بازگشت به گزینه‌ها</a></div>}
    </div>
  </div>;
}
