"use client";
import { useEffect, useRef, useState } from 'react';
import { api, errorMessage } from '@/lib/api';
import { balanceLabel, type ProviderBalance } from '@/lib/provider-balances';
import { Icon } from './icons';
import styles from './provider-balances.module.css';

export function ProviderBalances({onFailure}:{onFailure:(e:unknown)=>void}){
  return <section className={styles.bar} aria-label="اعتبار سرویس‌های متصل"><Balance provider="kavenegar" onFailure={onFailure}/><Balance provider="gapgpt" onFailure={onFailure}/></section>;
}
function Balance({provider,onFailure}:{provider:'kavenegar'|'gapgpt';onFailure:(e:unknown)=>void}){
  const [value,setValue]=useState<ProviderBalance|null>(null),[error,setError]=useState('');
  const failure=useRef(onFailure);failure.current=onFailure;
  useEffect(()=>{
    let disposed=false,running=false,timer:ReturnType<typeof setTimeout>|undefined,controller:AbortController|undefined,failures=0;
    async function load(){
      if(disposed||running||document.hidden||!navigator.onLine)return;
      running=true;controller=new AbortController();let wait=60000;
      try{
        const result=await api<ProviderBalance>(`/manage/provider-balances/${provider}`,{signal:controller.signal});
        if(!disposed){setValue(result);setError('');failures=0;if(result.status==='updating')wait=3000;}
      }catch(e){if(!disposed&&!controller.signal.aborted){setValue(null);setError(errorMessage(e));failure.current(e);failures++;wait=Math.min(60000,10000*2**Math.min(failures,3));}}
      finally{running=false;if(!disposed)timer=setTimeout(()=>void load(),wait);}
    }
    const resume=()=>{if(timer)clearTimeout(timer);if(!document.hidden&&navigator.onLine)void load();};
    const visible=()=>{if(document.hidden){if(timer)clearTimeout(timer);controller?.abort();}else resume();};
    void load();window.addEventListener('focus',resume);window.addEventListener('online',resume);document.addEventListener('visibilitychange',visible);
    return()=>{disposed=true;if(timer)clearTimeout(timer);controller?.abort();window.removeEventListener('focus',resume);window.removeEventListener('online',resume);document.removeEventListener('visibilitychange',visible);};
  },[provider]);
  const label=provider==='kavenegar'?'اعتبار پیامک':'اعتبار GapGPT';
  const stale=value?.status==='stale';
  const time=value?.observed_at?new Intl.DateTimeFormat('fa-IR',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tehran'}).format(new Date(value.observed_at)):null;
  const message=error?'ارتباط با سرویس برقرار نشد':stale?(value.reason==='refresh_in_progress'?'آخرین موجودی؛ در حال استعلام':'آخرین موجودی؛ استعلام تازه ناموفق'):value?.status==='unsupported'?'API موجودی تأیید نشده':value?.status==='available'?`استعلام ${time} · تا ۲ دقیقه تأخیر`:value?.status==='not_configured'?'کلید خصوصی سرویس لازم است':value?.status==='disabled'?'پروفایل اتصال خارجی فعال نیست':value?.status==='unavailable'?(value.reason==='access_denied'?'دسترسی به موجودی مجاز نیست':'دوباره به‌صورت خودکار بررسی می‌شود'):'';
  return <article className={`${styles.card} ${stale?styles.stale:''}`} aria-label={label}>
    <span className={styles.icon}><Icon name={provider==='kavenegar'?'phone':'sparkle'} size={20}/></span>
    <div className={styles.copy}><h2>{label}<span>{provider==='kavenegar'?'کاوه‌نگار':''}</span></h2>
      <p className={styles.amount} aria-live="polite" aria-atomic="true"><span className="sr-only">{label}: </span>{provider==='gapgpt'?<a className={styles.wallet} href="https://gapgpt.app/platform-v2/wallet" target="_blank" rel="noopener noreferrer" aria-label="بازکردن کیف پول GapGPT در زبانهٔ جدید">بررسی در پنل ↗</a>:error?'فعلاً دریافت نشد':balanceLabel(value)}{stale && <span className={styles.old}>قدیمی</span>}</p>
      <small title={stale&&time?`آخرین استعلام موفق: ${time}`:undefined}>{message}</small>
    </div>
    
  </article>;
}
