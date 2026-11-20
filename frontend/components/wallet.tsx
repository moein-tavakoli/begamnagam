"use client";

import { DigitInput } from "./digit-input";
import Link from 'next/link';
import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, approvedPaymentRedirect, createIdempotencyKey, errorMessage } from '@/lib/api';
import { walletEntryLabel, topupLabel, walletToman, type WalletState, type WalletTopup } from '@/lib/wallet';
import { useApp } from './app-provider';
import { AuthGate } from './auth-gate';
import { BusyButton, ErrorBox, ServiceState } from './feedback';

const dateFormatter = new Intl.DateTimeFormat('fa-IR', { dateStyle: 'short', timeStyle: 'short' });
const pollInterval = 5000;
const pollLimit = 24;

function isOpenTopup(topup: WalletTopup) {
  return ['created', 'pending', 'unknown'].includes(topup.status);
}

export function Wallet() {
  const { data, reload } = useApp();
  const [wallet, setWallet] = useState<WalletState | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [result, setResult] = useState<WalletTopup | null>(null);
  const [recoveringTopup, setRecoveringTopup] = useState(false);
  const intent = useRef<{ amount: number; key: string } | null>(null);
  const read = useRef<{ controller: AbortController; done: Promise<void> } | null>(null);
  const hasPending = wallet?.topups.some(isOpenTopup) ?? false;
  const needsPolling = hasPending || recoveringTopup;
  const load = useCallback((replace = false) => {
    if (read.current && !replace) return read.current.done;
    read.current?.controller.abort();
    const controller = new AbortController();
    const done = api<WalletState>('/wallet', { signal: controller.signal }).then(value => {
      if (controller.signal.aborted) return;
      setWallet(value);
      setRecoveringTopup(false);
      setError('');
    }).catch(e => {
      if (!controller.signal.aborted) setError(errorMessage(e));
    }).finally(() => {
      if (read.current?.controller === controller) read.current = null;
    });
    read.current = { controller, done };
    return done;
  }, []);
  useEffect(() => {
    setWallet(null);
    setResult(null);
    setRecoveringTopup(false);
    setError('');
    intent.current = null;
    if (data?.authenticated) void load();
    return () => {
      read.current?.controller.abort();
      read.current = null;
    };
  }, [data?.authenticated, data?.session_identity, load]);
  useEffect(() => {
    if (!data?.authenticated || !needsPolling) return;
    let stopped = false;
    let polling = false;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout>;
    const canPoll = () => !stopped && !polling && attempts < pollLimit && !document.hidden && navigator.onLine;
    const schedule = () => {
      if (canPoll()) timer = setTimeout(poll, pollInterval);
    };
    async function poll() {
      if (!canPoll()) return;
      polling = true;
      attempts += 1;
      await load();
      polling = false;
      if (!stopped && attempts >= pollLimit) setRecoveringTopup(false);
      schedule();
    }
    function activityChanged() {
      clearTimeout(timer);
      if (canPoll()) void poll();
    }
    schedule();
    document.addEventListener('visibilitychange', activityChanged);
    window.addEventListener('online', activityChanged);
    window.addEventListener('offline', activityChanged);
    return () => {
      stopped = true;
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', activityChanged);
      window.removeEventListener('online', activityChanged);
      window.removeEventListener('offline', activityChanged);
    };
  }, [data?.authenticated, data?.session_identity, needsPolling, load]);
  async function topup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget), amount = Number(form.get('amount'));
    let submitted = false;
    try {
      if (!wallet) return;
      if (!intent.current) intent.current = { amount, key: createIdempotencyKey() };
      if (intent.current.amount !== amount) throw new ApiError('درخواست قبلی نیازمند بررسی است؛ مبلغ را تغییر نده و دوباره پرداخت نکن.', 'idempotency_conflict');
      submitted = true;
      const response = await api<WalletTopup>('/wallet/topups', { method: 'POST', body: { amount_toman: amount, consent: form.get('consent') === 'on', terms_version: wallet.wallet_terms_version }, idempotencyKey: intent.current.key });
      setResult(response);
      if (response.redirect_url) { window.location.assign(approvedPaymentRedirect(response.redirect_url, false)); return; }
      if (response.status === 'failed' || response.status === 'credited') intent.current = null;
      if (isOpenTopup(response)) setRecoveringTopup(true);
      await load(true); await reload();
    } catch (e) {
      setError(errorMessage(e));
      if (submitted && e instanceof ApiError && [
        'network_error', 'request_timeout', 'service_error', 'invalid_response', 'invalid_gateway', 'payment_reconciliation',
      ].includes(e.code)) {
        setRecoveringTopup(true);
      }
    } finally {
      setBusy(false);
    }
  }
  function continuePayment(url: string) {
    try { window.location.assign(approvedPaymentRedirect(url, false)); }
    catch (e) { setError(errorMessage(e)); }
  }
  return <div className="account-page wallet-page wrap"><div className="account-heading"><h1>کیف پول من</h1></div><ServiceState />
    {!data?.authenticated ? <div className="account-card"><AuthGate purpose="برای دیدن کیف پول، شمارهٔ خودت را تأیید کن." /></div> : <>
      <section className="account-card wallet-overview"><span>موجودی قابل استفاده</span><strong>{wallet ? walletToman(wallet.balance_toman) : 'در حال دریافت…'}</strong><p>با موجودی کیف پول بستهٔ پیام می‌خری. این اعتبار برداشت یا انتقال بانکی ندارد؛ برگشت هزینهٔ پرداخت‌های دارای این شرایط به همین کیف پول انجام می‌شود.</p><Link href="/credits" prefetch={false} className="button secondary">خرید بستهٔ پیام</Link></section>
      <section className="account-card"><h2>شارژ با درگاه بانکی</h2><ErrorBox message={error} />
        {result && <p className="wallet-status" role="status">{topupLabel(result.status)}</p>}
        {!wallet ? <button type="button" className="button secondary" onClick={() => void load()}>دریافت موجودی</button> : !wallet.wallet_enabled || !wallet.gateway_enabled ? <p className="muted">شارژ جدید کیف پول فعلاً فعال نیست. موجودی و سوابق قبلی حفظ شده‌اند.</p> : <form className="wallet-topup-form" onSubmit={topup}>
          <label htmlFor="wallet-amount">مبلغ شارژ (تومان)</label><DigitInput id="wallet-amount" name="amount" type="number" min={1} max={2147483647} step={1} inputMode="numeric" required disabled={busy || needsPolling} />
          <label className="checkbox-label"><input name="consent" type="checkbox" required disabled={busy || needsPolling} /><span>می‌پذیرم که شارژ برای خرید بستهٔ پیام است، برداشت بانکی ندارد و برگشت هزینهٔ خرید به کیف پول انجام می‌شود.</span></label>
          <BusyButton className="button primary" busy={busy} disabled={needsPolling}>شارژ از درگاه بانکی</BusyButton>
        </form>}
        {hasPending && <p className="wallet-status" role="status">یک پرداخت در حال بررسی داری. برای جلوگیری از پرداخت تکراری، درخواست تازه ثبت نکن.</p>}
        {recoveringTopup && !hasPending && <p className="wallet-status" role="status">در حال بررسی وضعیت همان درخواست شارژ…</p>}
      </section>
      <section className="account-card"><div className="wallet-section-heading"><h2>گردش کیف پول</h2><button className="button secondary" type="button" disabled={busy} onClick={() => void load()}>تازه‌سازی</button></div>
        {!wallet?.entries.length ? <p className="muted">هنوز تراکنشی ثبت نشده است.</p> : <ol className="wallet-history">{wallet.entries.map(item => <li key={item.id}><div><b>{walletEntryLabel(item.kind)}</b><time>{dateFormatter.format(new Date(item.created_at))}</time></div><strong>{['order_debit','package_debit'].includes(item.kind) ? '−' : '+'} {walletToman(item.amount_toman)}</strong><small>موجودی پس از تراکنش: {walletToman(item.balance_after_toman)}</small></li>)}</ol>}
      </section>
      {!!wallet?.topups.length && <section className="account-card"><h2>درخواست‌های شارژ</h2><ol className="wallet-history">{wallet.topups.map(item => <li key={item.id}><div><b>{walletToman(item.amount_toman)}</b><span>{topupLabel(item.status)}</span></div>{item.status === 'pending' && item.redirect_url && <button className="button secondary" type="button" onClick={() => continuePayment(item.redirect_url!)}>ادامهٔ همان پرداخت</button>}</li>)}</ol></section>}
    </>}
  </div>;
}
