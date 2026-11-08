"use client";

import { ManagementButton, ManagementInput } from "./management-ui";
import { useCallback, useEffect, useState, type FormEvent, type RefObject } from 'react';
import { api, errorMessage } from '@/lib/api';
import { supportAccessLost, type SupportThreadData, type SupportWorkspaceMemory, type SupportDraftState } from '@/lib/support';
import { managementDate } from '@/lib/management';
import { Icon } from './icons';
import { SupportThread } from './support-thread';
import { notifySupportUpdate, useSupportPolling, useSupportRevision } from './support-polling';
import styles from './support-chat.module.css';

type Inbox = {conversations:SupportThreadData[];total:number;page:number;page_size:number;waiting_count:number;attention_count:number};
export function useSupportBadge(enabled:boolean,onFailure:(e:unknown)=>void){
  const [count,setCount]=useState(0),revision=useSupportRevision();
  useSupportPolling(async signal=>{try{const result=await api<{attention_count:number}>('/manage/support/summary',{signal});if(!signal.aborted)setCount(result.attention_count);}catch(e){if(!signal.aborted){if(supportAccessLost(e))setCount(0);onFailure(e);}throw e;}},enabled,20000,revision);
  return enabled?count:0;
}
export function SupportInbox({onFailure,memory}:{onFailure:(e:unknown)=>void;memory:RefObject<SupportWorkspaceMemory>}){
  const [data,setData]=useState<Inbox|null>(null),[selected,setSelected]=useState<SupportThreadData|null>(memory.current.thread);
  const [filter,setFilter]=useState('waiting'),[query,setQuery]=useState(''),[page,setPage]=useState(1),[error,setError]=useState('');
  const [dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),revision=useSupportRevision();
  const failure=useCallback((e:unknown)=>{onFailure(e);if(supportAccessLost(e)){memory.current={thread:null,composer:{draft:"",pending:null}};setSelected(null);setData(null);}},[onFailure,memory]);
  useSupportPolling(async signal=>{
    try{const result=await api<Inbox>('/manage/support/inbox',{method:'POST',body:{filter,query,page},signal});if(!signal.aborted){setData(result);setError('');}}
    catch(e){if(!signal.aborted){setError(errorMessage(e));failure(e);}throw e;}
  },true,10000,revision);
  // Filter/page transitions explicitly request a fresh list without racing a poll.
  useEffect(()=>{notifySupportUpdate();},[filter,query,page]);
  function select(thread:SupportThreadData|null){if(selected?.id===thread?.id)return;if(dirty && !window.confirm('پیام ارسال‌نشده داری. از این گفت‌وگو خارج شوی؟'))return;memory.current={thread,composer:{draft:"",pending:null}};setSelected(thread);setDirty(false);setError('');}
  async function close(){if(!selected)return;setBusy(true);setError('');try{const result=await api<{thread:SupportThreadData}>(`/manage/support/${selected.id}/close`,{method:'POST',body:{last_sequence:selected.last_sequence}});if(memory.current.thread?.id===result.thread.id)memory.current.thread={...memory.current.thread,...result.thread};setSelected(current=>current?.id===result.thread.id?{...current,...result.thread}:current);notifySupportUpdate();}catch(e){setError(errorMessage(e));failure(e);}finally{setBusy(false);}}
  const updateThread=useCallback((thread:SupportThreadData|null)=>{if(thread){if(memory.current.thread?.id===thread.id)memory.current.thread={...memory.current.thread,...thread};setSelected(current=>current?.id===thread.id?{...current,...thread}:current);}},[memory]);
  const rememberDraft=useCallback((composer:SupportDraftState)=>{memory.current.composer=composer;},[memory]);
  return <section className={styles.inbox} aria-label="صندوق پشتیبانی">
    <div className={styles.inboxIntro}><div><h2>یک جای مشترک برای پاسخ‌دادن</h2><p>همهٔ ادمین‌های واردشده می‌توانند پاسخ بدهند؛ نشان قرمز تا پاسخ به پیام کاربر باقی می‌ماند.</p></div><span className={styles.waitingTotal}>{(data?.waiting_count??0).toLocaleString('fa-IR')} منتظر پاسخ</span></div>
    {error && <p className={styles.error} role="alert">{error}</p>}
    <div className={`${styles.inboxLayout} ${selected?styles.conversationSelected:''}`}>
      <aside className={styles.sidebar} aria-label="فهرست گفت‌وگوها">
        <form className={styles.search} onSubmit={(e:FormEvent<HTMLFormElement>)=>{e.preventDefault();setQuery(String(new FormData(e.currentTarget).get('query')??'').trim());setPage(1);}}><label className="sr-only" htmlFor="support-search">جست‌وجوی شماره یا شناسهٔ حساب</label><ManagementInput name="query" id="support-search" type="search" placeholder="شماره یا شناسهٔ حساب" maxLength={100}/><ManagementButton type="submit" aria-label="جست‌وجوی گفت‌وگو"><Icon name="search" size={19}/></ManagementButton></form>
        <div className={styles.filters} aria-label="فیلتر گفت‌وگوها">{[['waiting','نیازمند پاسخ'],['all','همه'],['closed','بسته‌شده']].map(([key,label])=><ManagementButton type="button" key={key} aria-pressed={filter===key} onClick={()=>{setFilter(key);setPage(1);}}>{label}</ManagementButton>)}</div>
        {!data && !error && <p className={styles.loading} role="status">در حال دریافت پیام‌ها…</p>}
        {data && !data.conversations.length && <div className={styles.emptyList}><Icon name="check" size={26}/><p>{filter==='waiting'?'همهٔ پیام‌های این فهرست پاسخ گرفته‌اند.':'گفت‌وگویی در این فهرست نیست.'}</p></div>}
        <ul className={styles.conversations}>{data?.conversations.map(thread=><li key={thread.id}><ManagementButton type="button" className={selected?.id===thread.id?styles.selected:''} onClick={()=>select(thread)} aria-current={selected?.id===thread.id?'true':undefined}>
          <span className={styles.avatar}><Icon name="user" size={20}/></span><span className={styles.conversationLabel}><strong><bdi>{thread.phone_masked}</bdi></strong><small>حساب {thread.account_id?.toLocaleString('fa-IR')} · {managementDate(thread.updated_at)}</small><span className={thread.needs_reply?styles.needsReply:styles.answered}>{thread.needs_reply?'منتظر پاسخ':thread.status==='closed'?'بسته‌شده':'پاسخ داده شده'}</span></span>
          {!!thread.unread_count && <span className={styles.rowBadge} aria-label={`${thread.unread_count.toLocaleString('fa-IR')} پیام جدید`}>{thread.unread_count.toLocaleString('fa-IR')}</span>}
        </ManagementButton></li>)}</ul>
        {!!data && data.total>25 && <div className={styles.pagination}><ManagementButton type="button" disabled={page<=1} onClick={()=>setPage(p=>p-1)}>قبلی</ManagementButton><span>{page.toLocaleString('fa-IR')}</span><ManagementButton type="button" disabled={page*25>=data.total} onClick={()=>setPage(p=>p+1)}>بعدی</ManagementButton></div>}
      </aside>
      <div className={styles.staffPanel}>
        {selected?<><header className={styles.staffHeader}><ManagementButton type="button" className={styles.backToInbox} onClick={()=>select(null)} aria-label="بازگشت به فهرست گفت‌وگوها"><Icon name="arrow" size={19}/></ManagementButton><span><strong>گفت‌وگو با <bdi>{selected.phone_masked}</bdi></strong><small>حساب {selected.account_id?.toLocaleString('fa-IR')} · {selected.needs_reply?'منتظر پاسخ':selected.status==='closed'?'بسته‌شده':'پاسخ داده شده'}</small></span><ManagementButton type="button" className={styles.closeThread} disabled={busy || selected.needs_reply || selected.status==='closed' || dirty} onClick={()=>void close()}>{busy?'در حال ثبت…':'بستن گفت‌وگو'}</ManagementButton></header>
          <SupportThread key={selected.id} base={`/manage/support/${selected.id}`} staff active initialDraft={memory.current.composer} onDraftState={rememberDraft} onThread={updateThread} onDirty={setDirty} onFailure={failure}/>
        </>:<div className={styles.chooseConversation}><Icon name="chat" size={44}/><h3>یک گفت‌وگو را باز کن</h3><p>متن‌ها فقط در همین بخش دیده می‌شوند. ارسال فایل فعلاً غیرفعال است.</p></div>}
      </div>
    </div>
  </section>;
}
