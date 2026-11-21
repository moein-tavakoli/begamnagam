"use client";

import Link from 'next/link';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, ApiError, errorMessage, type Preview } from '@/lib/api';
import { normalizePhone, phoneInput, validPhone } from '@/lib/format';
import { useApp } from './app-provider';
import { AuthGate } from './auth-gate';
import { Composer } from './composer';
import { BusyButton, ErrorBox, ServiceState } from './feedback';
import { RecipientPhoneField } from './recipient-phone-field';
import styles from './purchase-examples.module.css';

type Trial = { trial_id: string; full_sms: string; expires_at: string };

export function TextTrial() {
  const { data } = useApp();
  if (data?.rewrite_mode === 'template') {
    return <div className="account-page wrap">
      <h1>متن خودم را امتحان کنم</h1>
      <p role="status" data-trial-unavailable>بازنویسی متن دلخواه فعلاً فعال نیست. می‌توانی نمونه‌های آماده را در صفحهٔ تعرفه‌ها ببینی.</p>
      <Link href="/pricing" className="button ghost">مشاهدهٔ تعرفه‌ها و نمونه‌ها</Link>
    </div>;
  }
  return data?.authenticated ? <TrialForm /> : <div className="account-page wrap">
    <TrialHeading />
    <ServiceState />
    {data && <AuthGate purpose="برای امتحان متن خودت، اول شمارهٔ خودت را تأیید کن." />}
  </div>;
}

function TrialHeading() {
  return <header className="account-heading">
    <h1>متن خودم را امتحان کنم</h1>
    <p>ببین حرفت در پیامک چطور خوانده می‌شود. برای این پیش‌نمایش شمارهٔ گیرنده لازم نیست، پیامکی ارسال نمی‌شود و هدیه یا اعتباری مصرف نمی‌کنی.</p>
  </header>;
}

function TrialForm() {
  const { reload } = useApp();
  const [draft, setDraft] = useState('');
  const [trial, setTrial] = useState<Trial | null>(null);
  const [choosingRecipient, setChoosingRecipient] = useState(false);
  const [recipient, setRecipient] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [fieldError, setFieldError] = useState('');
  const pending = useRef<AbortController | null>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const draftInput = useRef<HTMLTextAreaElement>(null);
  const editing = useRef(false);

  useEffect(() => () => pending.current?.abort(), []);
  useEffect(() => {
    if (trial) resultHeading.current?.focus();
    else if (editing.current) draftInput.current?.focus();
  }, [trial]);
  useEffect(() => {
    if (choosingRecipient) document.getElementById('quote-recipient')?.focus();
  }, [choosingRecipient]);

  function edit() {
    editing.current = true;
    setPreview(null);
    setTrial(null);
    setChoosingRecipient(false);
    setRecipient('');
    setFieldError('');
    setError('');
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending.current) return;
    setError('');
    setFieldError('');
    if (!trial && draft.trim().length < 3) {
      setFieldError('منظورت را در حداقل ۳ حرف بنویس.');
      draftInput.current?.focus();
      return;
    }
    if (trial && !validPhone(recipient)) {
      setFieldError('شماره موبایل گیرنده را با ۰۹ و ۱۱ رقم وارد کن.');
      document.getElementById('quote-recipient')?.focus();
      return;
    }
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    try {
      if (trial) {
        const bound = await api<Preview>(`/messages/text-trials/${trial.trial_id}/bind`, {
          method: 'POST', body: { recipient_phone: normalizePhone(recipient) }, signal: controller.signal,
        });
        if (!controller.signal.aborted) setPreview(bound);
      } else {
        const result = await api<Trial>('/messages/text-trials', {
          method: 'POST', body: { text: draft }, signal: controller.signal,
        });
        if (!controller.signal.aborted) setTrial(result);
      }
    } catch (reason) {
      if (controller.signal.aborted) return;
      setError(reason instanceof ApiError && reason.code === 'freeform_unavailable'
        ? 'بازنویسی متن دلخواه فعلاً در دسترس نیست. کمی بعد دوباره امتحان کن.' : errorMessage(reason));
      if (reason instanceof ApiError && reason.code === 'authentication_required') void reload();
    } finally {
      pending.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  if (preview) return <Composer initialReview={{ source: 'text-trial', preview, recipientPhone: recipient }}
    focusOnActivate onExit={edit} />;
  return <div className="account-page wrap" data-update-blocked={!!draft || busy}>
    <TrialHeading />
    <section className={styles.examples} aria-label="آزمایش متن پیام">
      <ErrorBox message={error} />
      {!trial ? <form onSubmit={submit} noValidate>
        <label htmlFor="trial-text">متن خودت</label>
        <textarea id="trial-text" ref={draftInput} value={draft} rows={4} maxLength={280} autoComplete="off"
          disabled={busy} aria-invalid={!!fieldError}
          aria-describedby={fieldError ? 'trial-hint trial-text-error' : 'trial-hint'}
          onChange={event => { setDraft(event.target.value); setFieldError(''); setError(''); }} />
        <p id="trial-hint" className={styles.note}>تا ۲۸۰ حرف بنویس. شمارهٔ تماس یا نشانی خصوصی وارد نکن.</p>
        {fieldError && <p id="trial-text-error" className="field-error" role="alert">{fieldError}</p>}
        <div className="form-actions"><BusyButton type="submit" className="button primary" busy={busy}>
          {busy ? 'در حال آماده‌سازی متن…' : 'دیدن پیش‌نمایش پیامک'}
        </BusyButton></div>
      </form> : <>
        <h2 ref={resultHeading} tabIndex={-1}>پیش‌نمایش پیامک تو</h2>
        <div className={styles.comparison}>
          <div className={styles.input}><h3>متن اولیهٔ تو</h3><p>{draft}</p></div>
          <div className={styles.sms}><h3>متن کامل پیامک</h3><p>{trial.full_sms}</p></div>
        </div>
        <p className={styles.note}>لینک داخل پیش‌نمایش نمونه است. لینک خصوصی گیرنده پس از انتخاب شماره جایگزین می‌شود.</p>
        <div className="form-actions">
          <button type="button" className="button ghost" disabled={busy} onClick={edit}>ویرایش متن</button>
          {!choosingRecipient && <button type="button" className="button primary" onClick={() => setChoosingRecipient(true)}>ادامه برای ارسال همین پیام</button>}
        </div>
        {choosingRecipient && <form onSubmit={submit} className={styles.recipient} noValidate>
          <RecipientPhoneField value={recipient} active disabled={busy} readOnly={false} error={fieldError}
            onChange={value => { setRecipient(phoneInput(value)); setFieldError(''); setError(''); }} />
          <div className="form-actions"><BusyButton type="submit" className="button primary" busy={busy}>
            بازبینی نهایی با این گیرنده
          </BusyButton></div>
        </form>}
      </>}
    </section>
  </div>;
}
