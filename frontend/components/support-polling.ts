"use client";
import { useEffect, useRef, useState } from 'react';

// Visible tabs only, one request at a time, and bounded backoff after failures.
export function useSupportPolling(task:(signal:AbortSignal)=>Promise<void>,enabled:boolean,interval:number,revision=0){
  const latest=useRef(task);latest.current=task;
  useEffect(()=>{
    if(!enabled)return;
    let disposed=false,running=false,failures=0,timer:ReturnType<typeof setTimeout>|undefined;
    let controller:AbortController|undefined;
    async function tick(){
      if(disposed || running || document.hidden || !navigator.onLine)return;
      running=true;controller=new AbortController();
      try{await latest.current(controller.signal);failures=0;}catch{failures=Math.min(failures+1,4);}
      finally{running=false;if(!disposed)timer=setTimeout(()=>void tick(),Math.min(60000,interval*2**failures));}
    }
    const resume=()=>{if(timer)clearTimeout(timer);if(!document.hidden && navigator.onLine)void tick();};
    const visibility=()=>{if(document.hidden){if(timer)clearTimeout(timer);controller?.abort();}else resume();};
    document.addEventListener('visibilitychange',visibility);window.addEventListener('online',resume);window.addEventListener('focus',resume);
    void tick();
    return()=>{disposed=true;if(timer)clearTimeout(timer);controller?.abort();document.removeEventListener('visibilitychange',visibility);window.removeEventListener('online',resume);window.removeEventListener('focus',resume);};
  },[enabled,interval,revision]);
}
export function notifySupportUpdate(){window.dispatchEvent(new Event('support-updated'));}
export function useSupportRevision(){
  const [revision,setRevision]=useState(0);
  useEffect(()=>{const refresh=()=>setRevision(v=>v+1);window.addEventListener('support-updated',refresh);return()=>window.removeEventListener('support-updated',refresh);},[]);
  return revision;
}
