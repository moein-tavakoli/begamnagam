"use client";
import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { api } from '@/lib/api';
import { supportLauncherBottom } from '@/lib/support';
import { useApp } from './app-provider';
import { Icon } from './icons';
import { SupportThread } from './support-thread';
import { useSupportPolling, useSupportRevision } from './support-polling';
import styles from './support-chat.module.css';

export function SupportWidget(){
  const {data}=useApp();const path=usePathname();
  const eligible=!!data?.authenticated && !/^\/(manage|admin|r)(\/|$)/.test(path);
  return eligible?<CustomerSupport/>:null;
}
function CustomerSupport(){
  const [open,setOpen]=useState(false),[summary,setSummary]=useState({unread_count:0,staff_online:false}),[bottom,setBottom]=useState(20);
  const wasOpen=useRef(false);
  const dialog=useRef<HTMLDialogElement>(null),trigger=useRef<HTMLButtonElement>(null),revision=useSupportRevision();
  useSupportPolling(async signal=>{const result=await api<typeof summary>('/support/summary',{signal});if(!signal.aborted)setSummary(result);},true,open?10000:30000,revision);
  useEffect(()=>{
    if(open){dialog.current?.showModal();wasOpen.current=true;}else{dialog.current?.close();if(wasOpen.current)trigger.current?.focus({preventScroll:true});wasOpen.current=false;}
  },[open]);
  useEffect(()=>{
    let frame=0;
    const position=()=>{
      cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{
        const button=trigger.current?.getBoundingClientRect();
        if(button){
          const obstacles=[...document.querySelectorAll('.composer-actions,.mobile-nav,.receipt-actions,.hero-cta')].map(element=>element.getBoundingClientRect()).filter(rect=>rect.width && rect.height && rect.top<innerHeight && rect.bottom>0);
          setBottom(supportLauncherBottom(innerHeight,button,obstacles));
        }
        if(dialog.current){dialog.current.style.setProperty('--support-height',`${window.visualViewport?.height??innerHeight}px`);dialog.current.style.setProperty('--support-top',`${window.visualViewport?.offsetTop??0}px`);}
      });
    };
    const observer=new MutationObserver(position);const main=document.querySelector('#main-content');if(main)observer.observe(main,{subtree:true,childList:true,attributes:true,attributeFilter:['class','style','hidden']});
    position();window.addEventListener('resize',position);window.addEventListener('hashchange',position);window.visualViewport?.addEventListener('resize',position);window.visualViewport?.addEventListener('scroll',position);
    return()=>{observer.disconnect();cancelAnimationFrame(frame);window.removeEventListener('resize',position);window.removeEventListener('hashchange',position);window.visualViewport?.removeEventListener('resize',position);window.visualViewport?.removeEventListener('scroll',position);};
  },[]);
  return <>
    <button type="button" ref={trigger} className={`${styles.launcher} support-launcher`} style={{bottom:`max(${bottom}px, calc(12px + env(safe-area-inset-bottom, 0px)))`}} aria-label={`پشتیبانی آنلاین${summary.unread_count?`؛ ${summary.unread_count.toLocaleString('fa-IR')} پاسخ خوانده‌نشده`:''}`} aria-haspopup="dialog" aria-expanded={open} aria-controls="customer-support" onClick={()=>setOpen(true)} title="پشتیبانی آنلاین">
      <Icon name="headset" size={24}/>{summary.unread_count>0 && <span className={styles.badge} aria-hidden="true">{summary.unread_count>99?'۹۹+':summary.unread_count.toLocaleString('fa-IR')}</span>}
    </button>
    <span className="sr-only" role="status" aria-atomic="true">{summary.unread_count?`${summary.unread_count.toLocaleString('fa-IR')} پاسخ خوانده‌نشده از پشتیبانی داری.`:''}</span>
    <dialog id="customer-support" ref={dialog} className={styles.dialog} aria-labelledby="support-heading" onCancel={event=>{event.preventDefault();setOpen(false);}} onClick={event=>{if(event.target===dialog.current){const r=dialog.current.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)setOpen(false);}}}>
      <header className={styles.header}><span className={styles.headerIcon}><Icon name="headset" size={24}/></span><div><h2 id="support-heading">پشتیبانی بگم نگم</h2><p><span className={`${styles.presence} ${summary.staff_online?styles.online:''}`}/>{summary.staff_online?'پشتیبان در پنل حضور دارد':'پیامت رو بفرست؛ همین‌جا پاسخ می‌دیم'}</p></div><button type="button" onClick={()=>setOpen(false)} aria-label="بستن گفت‌وگوی پشتیبانی"><Icon name="close" size={20}/></button></header>
      <details className={styles.rules}><summary>قوانین کوتاه گفت‌وگو</summary><p>با احترام و دربارهٔ خدمات سایت بنویس. فقط متن پذیرفته می‌شود؛ رمز، کد ورود، CVV2 یا اطلاعات حساس نفرست. پیام‌ها برای ادمین قابل مشاهده‌اند و متن آن‌ها پس از ۹۰ روز پاک می‌شود. برای رسید تصویری از راه‌های بله/تلگرام در صفحهٔ خرید استفاده کن. نوشتن پیام، پرداخت را تأیید نمی‌کند.</p></details>
      <SupportThread base="/support" active={open}/>
    </dialog>
  </>;
}
