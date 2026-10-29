"use client";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { api, ApiError, createIdempotencyKey, errorMessage } from '@/lib/api';
import { mergeSupportMessages, pendingIsConfirmed, supportAccessLost, supportDay, supportTime, type SupportMessage, type SupportPage, type SupportPending, type SupportThreadData, type SupportDraftState } from '@/lib/support';
import { Icon } from './icons';
import { notifySupportUpdate, useSupportPolling } from './support-polling';
import styles from './support-chat.module.css';

export function SupportThread({base,active,staff=false,onThread,onDirty,onFailure,initialDraft,onDraftState}:{base:string;active:boolean;staff?:boolean;onThread?:(t:SupportThreadData|null)=>void;onDirty?:(dirty:boolean)=>void;onFailure?:(e:unknown)=>void;initialDraft?:SupportDraftState;onDraftState?:(value:SupportDraftState)=>void}){
  const [page,setPage]=useState<SupportPage|null>(null),[messages,setMessages]=useState<SupportMessage[]>([]);
  const [draft,setDraft]=useState(initialDraft?.draft??''),[pending,setPending]=useState<SupportPending|null>(initialDraft?.pending??null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[pollError,setPollError]=useState('');
  const [older,setOlder]=useState<number|null>(null),[loadingOlder,setLoadingOlder]=useState(false),[atBottom,setAtBottom]=useState(true);
  const viewport=useRef<HTMLDivElement>(null),input=useRef<HTMLTextAreaElement>(null),mounted=useRef(true),readAck=useRef(0),historyLoaded=useRef(false);
  const pendingRef=useRef<SupportPending|null>(null);pendingRef.current=pending;
  const last=messages.at(-1)?.sequence??0;
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  useEffect(()=>{onDirty?.(!!draft || !!pending);},[draft,pending,onDirty]);
  useEffect(()=>{onDraftState?.({draft,pending});},[draft,pending,onDraftState]);
  function lost(e:unknown){
    if(supportAccessLost(e)){setMessages([]);setPage(null);setDraft('');setPending(null);if(!staff)window.dispatchEvent(new Event('privacy-reset'));}
    onFailure?.(e);
  }
  useSupportPolling(async signal=>{
    try{
      const result=await api<SupportPage>(`${base}/messages`,{signal});if(signal.aborted)return;
      setPage(result);onThread?.(result.thread);setMessages(current=>mergeSupportMessages(current,result.messages));setPollError('');
      if(!historyLoaded.current)setOlder(result.before_cursor);
      if(pendingIsConfirmed(pendingRef.current,result.messages)){setPending(null);setDraft('');setBusy(false);setError('');notifySupportUpdate();}
    }catch(e){if(!signal.aborted){setPollError(errorMessage(e));lost(e);}throw e;}
  },active,3000);
  useEffect(()=>{
    if(active && atBottom && viewport.current)viewport.current.scrollTop=viewport.current.scrollHeight;
  },[last,atBottom,active]);
  useEffect(()=>{
    if(!active || !atBottom || !page?.thread || document.hidden || !document.hasFocus() || !last)return;
    const acknowledged=staff?page.thread.staff_read_sequence:page.thread.customer_read_sequence;
    if(last<=Math.max(readAck.current,acknowledged))return;
    const controller=new AbortController();
    void api(`${base}/read`,{method:'POST',body:{through_sequence:last},signal:controller.signal}).then(()=>{if(!controller.signal.aborted){readAck.current=Math.max(readAck.current,last);notifySupportUpdate();}}).catch(e=>{if(!controller.signal.aborted && supportAccessLost(e))lost(e);});
    return()=>controller.abort();
  },[active,atBottom,last,page,base,staff]);
  async function loadOlder(){
    if(!older)return;setLoadingOlder(true);const height=viewport.current?.scrollHeight??0;
    try{const result=await api<SupportPage>(`${base}/messages?before=${older}`);if(!mounted.current)return;historyLoaded.current=true;setOlder(result.before_cursor);setMessages(current=>mergeSupportMessages(result.messages,current));requestAnimationFrame(()=>{if(viewport.current)viewport.current.scrollTop=viewport.current.scrollHeight-height;});}
    catch(e){if(mounted.current){setError(errorMessage(e));lost(e);}}finally{if(mounted.current)setLoadingOlder(false);}
  }
  async function send(event?:FormEvent<HTMLFormElement>){
    event?.preventDefault();if(busy || !page || (staff && !page.thread?.last_customer_sequence) || (!pending && !draft.trim()))return;
    const operation=pending??{text:draft.trim(),key:createIdempotencyKey(),replyTo:page?.thread?.last_customer_sequence??0};
    setPending(operation);pendingRef.current=operation;setBusy(true);setError('');
    try{
      const result=await api<{thread:SupportThreadData;message:SupportMessage}>(`${base}/messages`,{method:'POST',idempotencyKey:operation.key,body:{text:operation.text,...(staff?{reply_to_sequence:operation.replyTo}:{})}});
      if(!mounted.current)return;
      setMessages(current=>mergeSupportMessages(current,[result.message]));setPage(current=>current?{...current,thread:result.thread}:({thread:result.thread,messages:[],has_older:false,before_cursor:null,staff_online:false}));
      onThread?.(result.thread);setDraft('');setPending(null);setAtBottom(true);notifySupportUpdate();requestAnimationFrame(()=>{if(mounted.current && input.current?.getClientRects().length)input.current.focus({preventScroll:true});});
    }catch(e){if(mounted.current){
      setError(errorMessage(e));lost(e);
      if(e instanceof ApiError && ['invalid_support_text','invalid_reply','invalid_input','rate_limited','idempotency_conflict'].includes(e.code))setPending(null);
    }}finally{if(mounted.current)setBusy(false);}
  }
  function keyDown(event:KeyboardEvent<HTMLTextAreaElement>){
    if(event.key==='Enter' && !event.shiftKey && !event.nativeEvent.isComposing && !matchMedia('(pointer:coarse)').matches){event.preventDefault();void send();}
  }
  return <div className={styles.thread} data-update-blocked={draft || pending ? 'true':undefined}>
    <div className={styles.stream} ref={viewport} tabIndex={0} role="log" aria-live="polite" aria-relevant="additions" aria-label="پیام‌های گفت‌وگو" onScroll={e=>{const el=e.currentTarget;setAtBottom(el.scrollHeight-el.scrollTop-el.clientHeight<72);}}>
      {older && <button type="button" className={styles.older} disabled={loadingOlder} onClick={()=>void loadOlder()}>{loadingOlder?'در حال دریافت…':'پیام‌های قدیمی‌تر'}</button>}
      {!page && !error && !pollError && <p role="status" className={styles.loading}><span className="spinner"/> در حال دریافت گفت‌وگو…</p>}
      {page && !messages.length && <div className={styles.welcome}><span><Icon name="chat" size={28}/></span><h3>سلام، چطور می‌تونیم کمک کنیم؟</h3><p>سؤالت دربارهٔ ارسال پیام یا خرید بسته رو همین‌جا بنویس.</p></div>}
      {messages.map((message,index)=>{
        const mine=staff?message.role==='staff':message.role==='customer';
        const read=page?.thread && message.sequence<=(staff?page.thread.customer_read_sequence:page.thread.staff_read_sequence);
        return <div key={message.id}>{(!index || supportDay(messages[index-1].created_at)!==supportDay(message.created_at)) && <p className={styles.day}>{supportDay(message.created_at)}</p>}
          <article className={`${styles.bubble} ${mine?styles.mine:styles.theirs}`} aria-label={message.role==='staff'?'پیام پشتیبانی':'پیام کاربر'}>
            <span className={styles.author}>{mine?(staff?'پشتیبانی':'شما'):message.role==='staff'?'پشتیبانی':'کاربر'}</span>
            <p>{message.redacted?'متن این پیام طبق زمان نگهداری پاک شده است.':message.text}</p>
            <div className={styles.messageMeta}><time dateTime={message.created_at}>{supportTime(message.created_at)}</time>{mine && <span>{read?'خوانده شد':'ارسال شد'}<Icon name="check" size={12}/></span>}</div>
          </article>
        </div>;
      })}
      {page?.thread?.status==='closed' && <p className={styles.closed}>این گفت‌وگو پاسخ داده شده؛ با پیام تازه دوباره باز می‌شود.</p>}
    </div>
    {!atBottom && <button type="button" className={styles.newMessages} onClick={()=>{setAtBottom(true);if(viewport.current)viewport.current.scrollTop=viewport.current.scrollHeight;}}>رفتن به آخرین پیام <Icon name="arrow" size={15}/></button>}
    <div className={styles.composer}>
      {(error || pollError) && <p className={styles.error} role="alert">{error || pollError}</p>}
      {pending && !busy && <div className={styles.retry} role="status"><p>نتیجهٔ ارسال هنوز مشخص نیست؛ تکرار با همان شناسه انجام می‌شود تا پیام دوباره ثبت نشود.</p><button type="button" onClick={()=>void send()}>تلاش دوباره</button></div>}
      <form onSubmit={event=>void send(event)} aria-label="ارسال پیام به پشتیبانی">
        <label className="sr-only" htmlFor={`support-draft-${staff?'staff':'customer'}`}>{staff?'پاسخ به کاربر':'پیام به پشتیبانی'}</label>
        <textarea id={`support-draft-${staff?'staff':'customer'}`} ref={input} value={draft} onChange={e=>setDraft(e.target.value)} onKeyDown={keyDown} rows={2} maxLength={2000} disabled={busy || !!pending} placeholder={staff?'پاسخت را بنویس…':'پیامت رو اینجا بنویس…'} autoComplete="off"/>
        <button type="submit" aria-label={busy?'در حال ارسال پیام':'ارسال پیام پشتیبانی'} disabled={busy || !!pending || !draft.trim() || !page || (staff && !page.thread?.last_customer_sequence)}>{busy?<span className="spinner"/>:<Icon name="send" size={21}/>}</button>
      </form>
      <div className={styles.formNote}><span>فقط متن · رمز، کد ورود یا اطلاعات حساس نفرست.</span><span>{draft.length.toLocaleString('fa-IR')}/۲۰۰۰</span></div>
    </div>
  </div>;
}
