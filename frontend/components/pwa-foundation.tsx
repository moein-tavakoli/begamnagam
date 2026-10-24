"use client";
import { useEffect, useRef, useState } from "react";

function idleForUpdate(){
  const busy=document.querySelector('[aria-busy="true"], [data-update-blocked="true"]');
  const dirty=Array.from(document.querySelectorAll<HTMLInputElement|HTMLTextAreaElement>('input,textarea')).some(e=>e instanceof HTMLInputElement && e.type==='checkbox'?e.checked:!!e.value);
  return !busy && !dirty;
}

type InstallEvent = Event & { prompt(): Promise<void>; userChoice: Promise<{outcome:string}> };
export function PWAFoundation() {
  const [offline,setOffline]=useState(false);
  const [install,setInstall]=useState<InstallEvent|null>(null);
  const [ios,setIos]=useState(false);
  const [waiting,setWaiting]=useState<ServiceWorker|null>(null);
  const [notice,setNotice]=useState("");
  const updating=useRef(false);
  useEffect(()=>{
    const online=()=>setOffline(!navigator.onLine);
    const prompt=(event:Event)=>{event.preventDefault();setInstall(event as InstallEvent);};
    const installed=()=>{setInstall(null);setIos(false);};
    const changed=()=>{
      if(updating.current && idleForUpdate()) location.reload();
      else {setWaiting(navigator.serviceWorker.controller);setNotice('نسخه تازه فعال است؛ پس از پایان کار فعلی می‌تونی صفحه را تازه کنی.');}
    };
    const message=(event:MessageEvent)=>{
      if(event.data?.type==='CHECK_UPDATE_SAFETY')event.ports[0]?.postMessage({idle:idleForUpdate()});
      if(event.data?.type==='UPDATE_BLOCKED_BY_CLIENT'){updating.current=false;setNotice('در یکی از تب‌ها کاری باز است؛ اول آن را تمام کن یا تب را ببند.');}
    };
    online();
    const standalone=matchMedia('(display-mode: standalone)').matches || !!(navigator as Navigator & {standalone?:boolean}).standalone;
    setIos(!standalone && /iPad|iPhone|iPod/.test(navigator.userAgent));
    window.addEventListener('online',online);window.addEventListener('offline',online);
    window.addEventListener('beforeinstallprompt',prompt);window.addEventListener('appinstalled',installed);
    if(process.env.NODE_ENV==='production' && 'serviceWorker' in navigator && window.isSecureContext){
      navigator.serviceWorker.addEventListener('controllerchange',changed);
      navigator.serviceWorker.addEventListener('message',message);
      void navigator.serviceWorker.register('/sw.js',{scope:'/',updateViaCache:'none'}).then(reg=>{
        if(reg.waiting)setWaiting(reg.waiting);
        reg.addEventListener('updatefound',()=>{ const worker=reg.installing;worker?.addEventListener('statechange',()=>{if(worker.state==='installed' && navigator.serviceWorker.controller)setWaiting(worker);}); });
      }).catch(()=>setNotice('نصب برنامه فعلاً در دسترس نیست؛ نسخه وب قابل استفاده است.'));
    }
    return ()=>{window.removeEventListener('online',online);window.removeEventListener('offline',online);window.removeEventListener('beforeinstallprompt',prompt);window.removeEventListener('appinstalled',installed);navigator.serviceWorker?.removeEventListener('controllerchange',changed);navigator.serviceWorker?.removeEventListener('message',message);};
  },[]);
  async function installApp(){if(!install)return;await install.prompt();await install.userChoice;setInstall(null);}
  function updateApp(){
    if(!idleForUpdate()){setNotice('اول کار فعلی رو تمام کن؛ برای به‌روزرسانی، فرم باید خالی باشد.');return;}
    if(waiting?.state==='activated'){location.reload();return;}
    updating.current=true;waiting?.postMessage({type:'ACTIVATE_APPROVED_UPDATE'});
  }
  return <>
    {offline && <div className="pwa-connection" role="status">اینترنت قطع شده؛ عملیات به اتصال نیاز دارند و خودکار تکرار نمی‌شوند.</div>}
    {(install||ios||waiting||notice) && <aside className="pwa-controls" aria-label="نصب و نسخه برنامه">
      {install && <button type="button" className="button secondary compact" onClick={()=>void installApp()}>نصب بگم نگم</button>}
      {ios && <details><summary>نصب روی آیفون</summary><p>در Safari، گزینه Share و سپس Add to Home Screen را بزن.</p></details>}
      {waiting && <><span>نسخه تازه آماده است؛ می‌تونی بعداً نصبش کنی.</span><button type="button" className="button secondary compact" onClick={updateApp}>به‌روزرسانی در زمان مناسب</button></>}
      {notice && <p role="status">{notice}</p>}
    </aside>}
  </>;
}
