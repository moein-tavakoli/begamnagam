"use client";
import { useEffect, useRef, useState } from "react";
import { getServiceWorkerContainer } from "@/lib/browser-capabilities";
import { version } from "../package.json";
import { newerVersion } from "@/lib/app-version";

function idleForUpdate(){
  const busy=Array.from(document.querySelectorAll('[aria-busy="true"], [data-update-blocked="true"]')).some(e=>!e.closest('.app-update-notice'));
  const dirty=Array.from(document.querySelectorAll<HTMLInputElement|HTMLTextAreaElement>('input,textarea')).some(e=>{
    if(e instanceof HTMLInputElement){
      if(['hidden','radio','button','submit','reset'].includes(e.type))return false;
      if(e.type==='checkbox')return e.checked;
    }
    return !!e.value;
  });
  return !busy && !dirty;
}

type InstallEvent = Event & { prompt(): Promise<void>; userChoice: Promise<{outcome:string}> };
export function PWAFoundation() {
  const [offline,setOffline]=useState(false);
  const [install,setInstall]=useState<InstallEvent|null>(null);
  const [ios,setIos]=useState(false);
  const [waiting,setWaiting]=useState<ServiceWorker|null>(null);
  const [notice,setNotice]=useState("");
  const [availableVersion,setAvailableVersion]=useState("");
  const [updateMessage,setUpdateMessage]=useState("");
  const [updateDismissed,setUpdateDismissed]=useState(false);
  const updating=useRef(false);
  useEffect(()=>{setUpdateDismissed(false);},[availableVersion,waiting]);
  useEffect(()=>{
    let disposed=false,request:AbortController|null=null;
    const check=async()=>{
      if(document.visibilityState==='hidden'||request)return;
      request=new AbortController();
      try{
        const response=await fetch('/version.json',{cache:'no-store',credentials:'omit',signal:request.signal});
        if(!response.ok)return;
        const result=await response.json();
        if(!disposed&&newerVersion(result?.version,version))setAvailableVersion(result.version);
      }catch{/* Optional version checks must not interrupt the product. */}
      finally{request=null;}
    };
    void check();
    const timer=window.setInterval(()=>void check(),60000);
    window.addEventListener('focus',check);window.addEventListener('online',check);
    return()=>{disposed=true;request?.abort();window.clearInterval(timer);window.removeEventListener('focus',check);window.removeEventListener('online',check);};
  },[]);
  useEffect(()=>{
    let disposed=false;
    const serviceWorker=process.env.NODE_ENV==='production' && window.isSecureContext ? getServiceWorkerContainer() : null;
    const cleanups:Array<()=>void>=[];
    const online=()=>setOffline(!navigator.onLine);
    const prompt=(event:Event)=>{event.preventDefault();setInstall(event as InstallEvent);};
    const installed=()=>{setInstall(null);setIos(false);};
    const changed=()=>{
      if(updating.current && idleForUpdate()) location.reload();
      else {setWaiting(serviceWorker?.controller??null);setUpdateMessage('نسخهٔ جدید آماده است.');}
    };
    const message=(event:MessageEvent)=>{
      if(event.data?.type==='CHECK_UPDATE_SAFETY')event.ports[0]?.postMessage({idle:idleForUpdate()});
      if(event.data?.type==='UPDATE_BLOCKED_BY_CLIENT'){updating.current=false;setUpdateMessage('ابتدا کار تب‌های باز را تمام کن.');}
    };
    online();
    const standalone=matchMedia('(display-mode: standalone)').matches || !!(navigator as Navigator & {standalone?:boolean}).standalone;
    setIos(!standalone && /iPad|iPhone|iPod/.test(navigator.userAgent));
    window.addEventListener('online',online);window.addEventListener('offline',online);
    window.addEventListener('beforeinstallprompt',prompt);window.addEventListener('appinstalled',installed);
    if(serviceWorker){
      serviceWorker.addEventListener('controllerchange',changed);
      serviceWorker.addEventListener('message',message);
      // Some browser wrappers throw synchronously instead of rejecting register().
      void Promise.resolve().then(()=>disposed?null:serviceWorker.register('/sw.js',{scope:'/',updateViaCache:'none'})).then(reg=>{
        if(disposed||!reg)return;
        if(reg.waiting)setWaiting(reg.waiting);
        const found=()=>{
          const worker=reg.installing;
          if(!worker)return;
          const state=()=>{if(!disposed && worker.state==='installed' && serviceWorker.controller)setWaiting(worker);};
          worker.addEventListener('statechange',state);
          cleanups.push(()=>worker.removeEventListener('statechange',state));
        };
        reg.addEventListener('updatefound',found);
        cleanups.push(()=>reg.removeEventListener('updatefound',found));
      }).catch(()=>{if(!disposed)setNotice('نصب برنامه فعلاً در دسترس نیست؛ نسخه وب قابل استفاده است.');});
    }
    return ()=>{disposed=true;cleanups.forEach(cleanup=>cleanup());window.removeEventListener('online',online);window.removeEventListener('offline',online);window.removeEventListener('beforeinstallprompt',prompt);window.removeEventListener('appinstalled',installed);serviceWorker?.removeEventListener('controllerchange',changed);serviceWorker?.removeEventListener('message',message);};
  },[]);
  async function installApp(){
    if(!install)return;
    try{await install.prompt();await install.userChoice;}
    catch{setNotice('نصب انجام نشد؛ از منوی مرورگر دوباره امتحان کن.');}
    finally{setInstall(null);}
  }
  function updateApp(){
    if(updating.current)return;
    if(!idleForUpdate()){setUpdateMessage('اول کار فعلی را تمام کن.');return;}
    if(!waiting||waiting.state==='activated'){location.reload();return;}
    try{updating.current=true;setUpdateMessage('در حال به‌روزرسانی…');waiting.postMessage({type:'ACTIVATE_APPROVED_UPDATE'});}
    catch{updating.current=false;setUpdateMessage('دوباره امتحان کن.');}
  }
  return <>
    {offline && <div className="pwa-connection" role="status">اینترنت قطع شده؛ عملیات به اتصال نیاز دارند و خودکار تکرار نمی‌شوند.</div>}
    {(waiting||availableVersion)&&!updateDismissed&&<aside className="app-update-notice" aria-label="به‌روزرسانی برنامه">
      <span role="status">{updateMessage||'نسخهٔ جدید آماده است.'}</span>
      <button type="button" className="button secondary compact" onClick={updateApp} aria-busy={updating.current||undefined}>به‌روزرسانی</button>
      <button type="button" className="text-button" onClick={()=>setUpdateDismissed(true)}>بعداً</button>
    </aside>}
    {(install||ios||notice) && <aside className="pwa-controls" aria-label="نصب برنامه">
      {install && <button type="button" className="button secondary compact" onClick={()=>void installApp()}>نصب بگم نگم</button>}
      {ios && <details><summary>نصب روی آیفون</summary><p>در Safari، گزینه Share و سپس Add to Home Screen را بزن.</p></details>}
      {notice && <p role="status">{notice}</p>}
    </aside>}
  </>;
}
