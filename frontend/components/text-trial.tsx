"use client";

import Link from 'next/link';
import { Fragment, useEffect, useRef, useState, type FormEvent } from 'react';
import { api, ApiError, errorMessage, type Preview } from '@/lib/api';
import { latinDigits, normalizePhone, phoneInput, validPhone } from '@/lib/format';
import { matchesTrialWording, trialWordChanges, type TrialWording } from '@/lib/text-trial';
import { useApp } from './app-provider';
import { AuthGate } from './auth-gate';
import { Composer } from './composer';
import { BusyButton, ErrorBox, ServiceState } from './feedback';
import { RecipientPhoneField } from './recipient-phone-field';
import styles from './purchase-examples.module.css';

type Trial = { trial_id: string; full_sms: string; reviewed_body?: string; expires_at: string };
const wordingOptions = [
  ['rewrite', 'بازنویسی آزاد'], ['phrase', 'حفظ یک عبارت'], ['exact', 'حفظ کل متن'],
] as const;

export function TextTrial({ initialDraft = '' }: { initialDraft?: string }) {
  const { data } = useApp();
  if (data?.rewrite_mode === 'template') {
    return <div className="account-page wrap">
      <h1>متن خودم را امتحان کنم</h1>
      <p role="status" data-trial-unavailable>بازنویسی متن دلخواه فعلاً فعال نیست. می‌توانی نمونه‌های آماده را در صفحهٔ تعرفه‌ها ببینی.</p>
      <Link href="/pricing" className="button ghost">مشاهدهٔ تعرفه‌ها و نمونه‌ها</Link>
    </div>;
  }
  return data?.authenticated ? <TrialForm initialDraft={initialDraft} /> : <div className="account-page wrap">
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

function TrialComparison({ draft, trial }: { draft: string; trial: Trial }) {
  const reviewed = trial.reviewed_body;
  const changed = !!reviewed && reviewed !== draft;
  const words = changed ? trialWordChanges(draft, reviewed) : [];
  return <>
    {changed && <p className={styles.note}>در متن اولیه، حذف‌ها خط خورده‌اند. در بدنهٔ بازبینی‌شده، عبارت‌های افزوده زیرخط دارند.</p>}
    <div className={styles.comparison}>
      <div className={styles.input}><h3>متن اولیهٔ تو</h3>
        <p>{changed ? words.map((word, i) => word.kind === 'removed' ?
          <Fragment key={i}><span className="sr-only">حذف‌شده: </span><del>{word.text}</del></Fragment> :
          word.kind === 'equal' && word.text) : draft}</p>
      </div>
      {changed && <div className={styles.sms}><h3>بدنهٔ بازبینی‌شده</h3>
        <p>{words.map((word, i) => word.kind === 'added' ?
          <Fragment key={i}><span className="sr-only">افزوده‌شده: </span><ins>{word.text}</ins></Fragment> :
          word.kind === 'equal' && word.text)}</p>
      </div>}
      <div className={changed ? styles.fullSms : styles.sms}><h3>متن کامل پیامک</h3><p>{trial.full_sms}</p></div>
    </div>
    {trial.reviewed_body === draft && <p className={styles.note}>واژه‌های متن تغییری نکرده‌اند.</p>}
    {!trial.reviewed_body && <p className={styles.note}>مقایسهٔ واژه‌ها برای این پیش‌نمایش در دسترس نیست.</p>}
  </>;
}

function TrialForm({ initialDraft }: { initialDraft: string }) {
  const { reload } = useApp();
  const [draft, setDraft] = useState(initialDraft);
  const [wording, setWording] = useState<TrialWording>('rewrite');
  const [phrase, setPhrase] = useState('');
  const [phraseError, setPhraseError] = useState('');
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
  const phraseInput = useRef<HTMLInputElement>(null);
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
    setPhraseError('');
    setError('');
  }

  function editReviewedBody() {
    if (!trial?.reviewed_body) return;
    setDraft(trial.reviewed_body);
    setPhrase('');
    setWording('exact');
    edit();
  }

  function copySelectionToPhrase() {
    const input = draftInput.current;
    if (input && input.selectionEnd > input.selectionStart) {
      setPhrase(input.value.slice(input.selectionStart, input.selectionEnd));
      setPhraseError('');
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending.current) return;
    setError('');
    setFieldError('');
    setPhraseError('');
    if (!trial && draft.trim().length < 3) {
      setFieldError('منظورت را در حداقل ۳ حرف بنویس.');
      draftInput.current?.focus();
      return;
    }
    if (!trial && wording === 'phrase' && (!phrase.trim() || !latinDigits(draft).includes(latinDigits(phrase)))) {
      setPhraseError('عبارت را عیناً از متن خودت وارد کن.');
      phraseInput.current?.focus();
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
          method: 'POST', signal: controller.signal, body: {
            text: draft,
            ...(wording === 'exact' && { exact_wording: true }),
            ...(wording === 'phrase' && { preserve_phrase: phrase }),
          },
        });
        if (controller.signal.aborted) return;
        if (!matchesTrialWording(wording, draft, phrase, result.reviewed_body)) {
          setError('مقایسهٔ بدنهٔ تأییدشده با عبارت درخواستی ممکن نشد. دوباره بررسی کن.');
        } else setTrial(result);
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
          onSelect={wording === 'phrase' ? copySelectionToPhrase : undefined}
          aria-describedby={fieldError ? 'trial-hint trial-text-error' : 'trial-hint'}
          onChange={event => { setDraft(event.target.value); setFieldError(''); setPhraseError(''); setError(''); }} />
        <p id="trial-hint" className={styles.note}>تا ۲۸۰ حرف بنویس. شمارهٔ تماس یا نشانی خصوصی وارد نکن.</p>
        {fieldError && <p id="trial-text-error" className="field-error" role="alert">{fieldError}</p>}
        <fieldset className={`${styles.choices} ${styles.wording}`} disabled={busy}>
          <legend>کدام بخش باید عیناً بماند؟</legend>
          <div className={styles.options}>{wordingOptions.map(([value, label]) => <label key={value}>
            <input type="radio" name="trial-wording" value={value} checked={wording === value}
              onChange={() => {
                setWording(value);
                if (value === 'phrase') copySelectionToPhrase();
                setPhraseError(''); setError('');
              }} />{label}
          </label>)}</div>
        </fieldset>
        {wording === 'phrase' && <div className={styles.phrase}>
          <label htmlFor="trial-phrase">عبارت موردنظرت</label>
          <p id="trial-phrase-hint" className={styles.note}>عبارت را در متن بالا انتخاب کن یا عین آن را اینجا بنویس.</p>
          <input id="trial-phrase" ref={phraseInput} type="text" value={phrase} autoComplete="off" maxLength={280}
            disabled={busy} aria-invalid={!!phraseError} aria-describedby={phraseError ? 'trial-phrase-hint trial-phrase-error' : 'trial-phrase-hint'}
            onChange={event => { setPhrase(event.target.value); setPhraseError(''); setError(''); }} />
          {phraseError && <p id="trial-phrase-error" className="field-error" role="alert">{phraseError}</p>}
        </div>}
        {wording !== 'rewrite' && <p className={styles.note}>فقط در صورت تأیید محتوا و حفظ عین {wording === 'phrase' ? 'عبارت' : 'متن'}، پیش‌نمایش آماده می‌شود.</p>}
        <div className="form-actions"><BusyButton type="submit" className="button primary" busy={busy}>
          {busy ? 'در حال آماده‌سازی متن…' : 'دیدن پیش‌نمایش پیامک'}
        </BusyButton></div>
      </form> : <>
        <h2 ref={resultHeading} tabIndex={-1}>پیش‌نمایش پیامک تو</h2>
        <TrialComparison draft={latinDigits(draft)} trial={trial} />
        <p className={styles.note}>لینک داخل پیش‌نمایش نمونه است. لینک خصوصی گیرنده پس از انتخاب شماره جایگزین می‌شود.</p>
        <p className={styles.note}>در جمع کوچک، جزئیات یک اتفاق یا زمان ارسال می‌تواند فرستنده را برای گیرنده مشخص کند.</p>
        <div className="form-actions">
          <button type="button" className="button ghost" disabled={busy} onClick={edit}>ویرایش متن اولیه</button>
          {trial.reviewed_body && <button type="button" className="button ghost" disabled={busy} onClick={editReviewedBody}>ویرایش بدنهٔ پیامک</button>}
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
