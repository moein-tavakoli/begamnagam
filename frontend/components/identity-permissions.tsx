"use client";

import {useCallback, useEffect, useRef, useState} from 'react';
import {api, errorMessage} from '@/lib/api';
import {openSessionChannel} from '@/lib/browser-capabilities';
import {anonymityNotice, identityStatusLabels, revocationNotice, type IdentityConsent, type IdentityRequests} from '@/lib/identity-consent';
import {BusyButton, ErrorBox} from './feedback';
import styles from './identity-permissions.module.css';

export function IdentityPermissions() {
  const [direction, setDirection] = useState<'incoming' | 'outgoing'>('incoming');
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<IdentityConsent[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [checks, setChecks] = useState<Record<string, number | undefined>>({});
  const [phones, setPhones] = useState<Record<string, string>>({});
  const [phoneBusy, setPhoneBusy] = useState('');
  const listing = useRef<AbortController | null>(null);
  const decisionRequest = useRef<AbortController | null>(null);
  const phoneRequest = useRef<AbortController | null>(null);
  const listGeneration = useRef(0);
  const phoneGeneration = useRef(0);
  const channel = useRef<ReturnType<typeof openSessionChannel>>(null);

  const clearPhones = useCallback(() => {
    phoneGeneration.current += 1;
    phoneRequest.current?.abort();
    setPhones({});setPhoneBusy('');
  }, []);

  const refresh = useCallback(async () => {
    const generation = ++listGeneration.current;
    listing.current?.abort();
    const controller = new AbortController();
    listing.current = controller;
    clearPhones();setLoading(true);
    try {
      const result = await api<IdentityRequests>(`/identity-requests?direction=${direction}&page=${page}`, {signal: controller.signal});
      if (generation === listGeneration.current && !controller.signal.aborted) {
        setRows(result.results);setCount(result.count);setError('');
        // Keep an explicit choice only while this exact pending revision lasts.
        setChecks(previous => Object.fromEntries(result.results
          .filter(row => row.status === 'pending' && previous[row.id] === row.revision)
          .map(row => [row.id, row.revision])));
      }
    } catch (error) {
      if (generation === listGeneration.current && !controller.signal.aborted) {
        setRows([]);setCount(0);setError(errorMessage(error));clearPhones();
      }
    } finally {
      if (generation === listGeneration.current && !controller.signal.aborted) setLoading(false);
    }
  }, [direction, page, clearPhones]);

  useEffect(() => {
    void refresh();
    const peer = openSessionChannel();
    channel.current = peer;
    const changed = (event: MessageEvent) => {if (event.data === 'identity-consent-changed') void refresh();};
    const visibility = () => {
      clearPhones();
      if (document.hidden) {listGeneration.current += 1;listing.current?.abort();}
      else void refresh();
    };
    const focus = () => {if (!document.hidden) void refresh();};
    const timer = setInterval(() => {if (!document.hidden) void refresh();}, 15000);
    peer?.addEventListener('message', changed);
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('blur', clearPhones);
    window.addEventListener('offline', clearPhones);
    window.addEventListener('pagehide', clearPhones);
    window.addEventListener('focus', focus);
    return () => {
      listGeneration.current += 1;listing.current?.abort();
      phoneGeneration.current += 1;phoneRequest.current?.abort();
      decisionRequest.current?.abort();
      peer?.close();channel.current = null;clearInterval(timer);
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('blur', clearPhones);
      window.removeEventListener('offline', clearPhones);
      window.removeEventListener('pagehide', clearPhones);
      window.removeEventListener('focus', focus);
    };
  }, [refresh, clearPhones]);

  async function decide(row: IdentityConsent, action: 'approve' | 'decline' | 'revoke') {
    if (busy) return;
    const controller = new AbortController();
    decisionRequest.current = controller;
    clearPhones();setBusy(row.id);setError('');setNotice('');
    try {
      await api(`/identity-requests/${row.id}`, {
        method: 'POST', body: {action, revision: row.revision, ...(action === 'approve' ? {consent: true} : {})}, signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      channel.current?.postMessage('identity-consent-changed');
      setNotice(action === 'approve' ? 'نمایش شماره‌ات فقط برای همین درخواست‌دهنده تأیید شد.'
        : action === 'revoke' ? 'برای همین فرد دوباره ناشناس شدی؛ نمایش بعدی شماره بسته شد.' : 'درخواست رد شد؛ شماره‌ات پنهان می‌مونه.');
      await refresh();
    } catch (error) {
      if (!controller.signal.aborted) {await refresh();setError(errorMessage(error));}
    } finally {
      if (!controller.signal.aborted) setBusy('');
    }
  }

  async function showPhone(row: IdentityConsent) {
    clearPhones();
    const generation = phoneGeneration.current;
    const controller = new AbortController();
    phoneRequest.current = controller;
    setPhoneBusy(row.id);setError('');
    try {
      const result = await api<{phone: string}>(`/identity-requests/${row.id}/phone`, {signal: controller.signal});
      if (!controller.signal.aborted && generation === phoneGeneration.current && !document.hidden)
        setPhones({[row.id]: result.phone});
    } catch (error) {
      if (!controller.signal.aborted && generation === phoneGeneration.current) {
        await refresh();setError(errorMessage(error));
      }
    } finally {
      if (generation === phoneGeneration.current) setPhoneBusy('');
    }
  }

  function switchDirection(value: 'incoming' | 'outgoing') {
    if (direction === value) return;
    clearPhones();setRows([]);setCount(0);setChecks({});setError('');setNotice('');setPage(1);setDirection(value);
  }

  return <section className={styles.panel} aria-labelledby="identity-permissions-title">
    <h2 id="identity-permissions-title">میخوام بدونم</h2>
    <p className="small muted">{anonymityNotice}</p>
    <div className={styles.tabs} role="group" aria-label="جهت درخواست‌ها">
      <button className="button ghost" type="button" aria-pressed={direction === 'incoming'} disabled={!!busy} onClick={()=>switchDirection('incoming')}>درخواست‌های دیگران</button>
      <button className="button ghost" type="button" aria-pressed={direction === 'outgoing'} disabled={!!busy} onClick={()=>switchDirection('outgoing')}>درخواست‌های من</button>
    </div>
    <ErrorBox message={error}/>
    {notice && <p className="success-notice" role="status">{notice}</p>}
    {loading && <p className="small muted" role="status">در حال بررسی درخواست‌ها…</p>}
    {!loading && !error && rows.length === 0 && <p className="small muted">هنوز درخواستی در این بخش نیست.</p>}
    <div className={styles.list}>
      {rows.map(row => <article className={styles.request} key={row.id} aria-label={direction === 'incoming' ? 'درخواست نمایش شمارهٔ من' : 'درخواست من برای شناختن فرستنده'}>
        <h3>{direction === 'incoming' ? 'گیرندهٔ پیامت می‌خواد بدونه کی هستی' : 'درخواست شناختن فرستنده'}</h3>
        {row.message_created_at && <p className="small muted">پیام {new Intl.DateTimeFormat('fa-IR', {dateStyle: 'medium', timeStyle: 'medium'}).format(new Date(row.message_created_at))}</p>}
        {direction === 'outgoing' && row.requested_at && <p className="small muted">درخواست تو: {new Intl.DateTimeFormat('fa-IR', {dateStyle: 'medium', timeStyle: 'medium'}).format(new Date(row.requested_at))}</p>}
        {direction === 'incoming' && row.message_excerpt && <p className="small">از پیام خودت: «{row.message_excerpt}»</p>}
        <p className="small">وضعیت: {direction === 'outgoing' && row.status === 'pending' ? 'شماره هنوز پنهان است' : identityStatusLabels[row.status]}</p>
        {direction === 'incoming' && row.status === 'pending' && <>
          <label className="checkbox-label"><input type="checkbox" checked={checks[row.id] === row.revision} disabled={!!busy || loading} onChange={event=>setChecks({...checks, [row.id]: event.target.checked ? row.revision : undefined})}/><span>تأیید می‌کنم فقط شمارهٔ موبایلم برای همین درخواست‌دهنده در پروفایل سایتش دیده بشه.</span></label>
          <div className={styles.buttons}>
            <BusyButton type="button" className="button primary" busy={busy === row.id} disabled={!!busy || loading || checks[row.id] !== row.revision} onClick={()=>void decide(row, 'approve')}>تأیید نمایش شماره</BusyButton>
            <button type="button" className="button ghost" disabled={!!busy || loading} onClick={()=>void decide(row, 'decline')}>رد درخواست</button>
          </div>
        </>}
        {direction === 'incoming' && row.status === 'approved' && <>
          <p className="small muted">اجازهٔ این فرد شامل هیچ فرد دیگری یا جهت برعکس ارتباط نمی‌شه.</p>
          <BusyButton type="button" className="button secondary" busy={busy === row.id} disabled={!!busy || loading} onClick={()=>void decide(row, 'revoke')}>ناشناس شدن</BusyButton>
        </>}
        {direction === 'outgoing' && row.status === 'approved' && <>
          <BusyButton type="button" className="button secondary" busy={phoneBusy === row.id} disabled={loading || !!phoneBusy} onClick={()=>void showPhone(row)}>مشاهده شماره</BusyButton>
          {phones[row.id] && <p className={styles.phone} role="status">شمارهٔ تأییدشده: <bdi>{phones[row.id]}</bdi></p>}
        </>}
        {direction === 'outgoing' && row.status === 'pending' && <p className="small muted">تا خودش تأیید نکنه، نمی‌تونی شماره‌اش را ببینی.</p>}
      </article>)}
    </div>
    <div className={styles.buttons}>
      <button type="button" className="text-button" disabled={loading || !!busy} onClick={()=>void refresh()}>به‌روزرسانی درخواست‌ها</button>
      {count > 20 && <nav className={styles.buttons} aria-label="صفحه‌های درخواست">
        <button type="button" className="button ghost" disabled={loading || !!busy || page <= 1} onClick={()=>{clearPhones();setRows([]);setPage(page-1);}}>قبلی</button>
        <span>{new Intl.NumberFormat('fa-IR').format(page)}</span>
        <button type="button" className="button ghost" disabled={loading || !!busy || page*20 >= count} onClick={()=>{clearPhones();setRows([]);setPage(page+1);}}>بعدی</button>
      </nav>}
    </div>
    <p className="small muted">{revocationNotice} شماره در حافظهٔ پایدار یا حالت آفلاین ذخیره نمی‌شه؛ مشاهدهٔ دوباره به بررسی آنلاین مجوز نیاز داره.</p>
  </section>;
}
