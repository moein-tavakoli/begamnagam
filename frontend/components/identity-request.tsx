"use client";

import Link from 'next/link';
import {useEffect, useRef, useState} from 'react';
import {api, ApiError, errorMessage} from '@/lib/api';
import {identityRequestNotice, identityStatusLabels, type IdentityConsent} from '@/lib/identity-consent';
import {useApp} from './app-provider';
import {AuthGate} from './auth-gate';
import {BusyButton, ErrorBox, ServiceState} from './feedback';

export function IdentityRequest({token, choicesHref}: {token: string; choicesHref: string}) {
  const {data} = useApp();
  const heading = useRef<HTMLHeadingElement>(null);
  const pending = useRef<AbortController | null>(null);
  const [record, setRecord] = useState<IdentityConsent | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [switching, setSwitching] = useState(false);
  const [canSwitch, setCanSwitch] = useState(false);
  useEffect(() => {
    heading.current?.focus();
    return () => pending.current?.abort();
  }, []);

  async function sendRequest() {
    const controller = new AbortController();
    pending.current?.abort();
    pending.current = controller;
    setBusy(true);setError('');setCanSwitch(false);
    try {
      const result = await api<IdentityConsent>('/recipient/actions/identity', {
        method: 'POST', body: {token}, signal: controller.signal,
      });
      if (!controller.signal.aborted) setRecord(result);
    } catch (error) {
      if (!controller.signal.aborted) {
        setError(errorMessage(error));
        setCanSwitch(error instanceof ApiError && ['identity_unavailable', 'link_unavailable'].includes(error.code));
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return <section className="account-page wrap" aria-labelledby="identity-request-title">
    <div className="account-heading"><h1 id="identity-request-title" ref={heading} tabIndex={-1}>میخوام بدونم کیه</h1><p>{identityRequestNotice}</p></div>
    <div className="account-card">
      <ServiceState/>
      <ErrorBox message={error}/>
      {data && (!data.authenticated || switching) ? <AuthGate forceReverify={switching} purpose="همان شماره‌ای را تأیید کن که این پیامک را دریافت کرده."/>
        : data?.authenticated && !record && <BusyButton type="button" className="button primary full-width" busy={busy} onClick={()=>void sendRequest()}>ثبت درخواست شناختن فرستنده</BusyButton>}
      {record && <><p className="success-notice" role="status">{identityStatusLabels[record.status]}؛ نتیجه را در پروفایل خودت ببین.</p><Link className="button primary" href="/profile" prefetch={false}>دیدن درخواست در پروفایل</Link></>}
      {canSwitch && !switching && <button type="button" className="text-button" onClick={()=>setSwitching(true)}>تأیید شمارهٔ دیگری</button>}
      <p className="small muted">این درخواست نام، مشخصات دیگر یا اجازهٔ دیدن سابقهٔ پیام‌ها را نمی‌دهد. فرستنده می‌تونه اجازهٔ نمایش شماره‌اش را دوباره برداره.</p>
      <a className="text-button" href={choicesHref}>بازگشت به گزینه‌ها</a>
    </div>
  </section>;
}
