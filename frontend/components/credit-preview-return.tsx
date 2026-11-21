"use client";

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { api, errorMessage, type Preview } from '@/lib/api';
import { useCheckoutPreviewId } from '@/lib/use-checkout-preview-id';
import { useApp } from './app-provider';
import { AuthGate } from './auth-gate';
import { Composer } from './composer';
import { ErrorBox, ServiceState } from './feedback';

export function CreditPreviewReturn() {
  const { data } = useApp();
  const id = useCheckoutPreviewId();
  if (!data) return <div className="account-page wrap"><ServiceState/></div>;
  if (!data.authenticated) return <div className="account-page wrap"><AuthGate purpose="برای بازبینی پیام، وارد حساب خودت شو."/></div>;
  return <RestorePreview key={id ?? 'missing'} id={id}/>;
}

function RestorePreview({ id }: { id: string | null }) {
  const router = useRouter();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    void api<Preview>(`/messages/preview/${id}`, { signal: controller.signal })
      .then(result => { if (!controller.signal.aborted && result.preview_id === id) setPreview(result); })
      .catch(reason => { if (!controller.signal.aborted) setError(errorMessage(reason)); });
    return () => controller.abort();
  }, [id, attempt]);
  if (preview) return <Composer initialReview={{ source: 'purchase', preview }} onExit={() => router.replace('/#compose')}/>;
  return <section className="account-page wrap">
    <h1>بازبینی پیام پس از خرید</h1>
    {!id || error ? <>
      <ErrorBox message={error || 'پیش‌نمایشی برای بازگشت انتخاب نشده است.'}/>
      {id && <button type="button" className="button ghost" onClick={() => { setError(''); setAttempt(value => value + 1); }}>بررسی دوباره</button>}
      <Link className="button primary" href="/#compose">نوشتن پیام تازه</Link>
      <Link className="text-button" href="/credits">موجودی و خریدهای من</Link>
    </> : <p role="status">در حال دریافت متن تأییدشده برای بازبینی…</p>}
  </section>;
}
