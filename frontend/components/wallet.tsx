"use client";

import { DigitInput } from "./digit-input";
import Link from 'next/link';
import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, approvedPaymentRedirect, createIdempotencyKey, errorMessage } from '@/lib/api';
import { walletEntryLabel, topupLabel, walletToman, type WalletState, type WalletTopup } from '@/lib/wallet';
import { useApp } from './app-provider';
import { AuthGate } from './auth-gate';
import { BusyButton, ErrorBox, ServiceState } from './feedback';

export function Wallet() {
  const { data, reload } = useApp();
  const [wallet, setWallet] = useState<WalletState | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [result, setResult] = useState<WalletTopup | null>(null);
  const intent = useRef<{ amount: number; key: string } | null>(null);
  const generation = useRef(0);
  const load = useCallback(async () => {
    const current = ++generation.current;
    try { const value = await api<WalletState>('/wallet'); if (current === generation.current) { setWallet(value); setError(''); } }
    catch (e) { if (current === generation.current) setError(errorMessage(e)); }
  }, []);
  useEffect(() => { setWallet(null); setResult(null); intent.current = null; if (data?.authenticated) void load(); return () => { generation.current += 1; }; }, [data?.authenticated, data?.session_identity, load]);
  useEffect(() => {
    if (!data?.authenticated) return;
    let cancelled = false, count = 0;
    const timer = setInterval(() => { if (!cancelled) void load(); if (++count >= 24) clearInterval(timer); }, 5000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [data?.authenticated, data?.session_identity, load]);
  async function topup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget), amount = Number(form.get('amount'));
    try {
      if (!wallet) return;
      if (!intent.current) intent.current = { amount, key: createIdempotencyKey() };
      if (intent.current.amount !== amount) throw new ApiError('درخواست قبلی نیازمند بررسی است؛ مبلغ را تغییر نده و دوباره پرداخت نکن.', 'idempotency_conflict');
      const response = await api<WalletTopup>('/wallet/topups', { method: 'POST', body: { amount_toman: amount, consent: form.get('consent') === 'on', terms_version: wallet.wallet_terms_version }, idempotencyKey: intent.current.key });
      setResult(response);
      if (response.redirect_url) { window.location.assign(approvedPaymentRedirect(response.redirect_url, false)); return; }
      if (response.status === 'failed' || response.status === 'credited') intent.current = null;
      await load(); await reload();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  const hasPending = wallet?.topups.some(item => ['created', 'pending', 'unknown'].includes(item.status));
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
          <label htmlFor="wallet-amount">مبلغ شارژ (تومان)</label><DigitInput id="wallet-amount" name="amount" type="number" min={1} max={2147483647} step={1} inputMode="numeric" required disabled={busy || !!hasPending} />
          <label className="checkbox-label"><input name="consent" type="checkbox" required disabled={busy || !!hasPending} /><span>می‌پذیرم که شارژ برای خرید بستهٔ پیام است، برداشت بانکی ندارد و برگشت هزینهٔ خرید به کیف پول انجام می‌شود.</span></label>
          <BusyButton className="button primary" busy={busy} disabled={!!hasPending}>شارژ از درگاه درگاه بانکی</BusyButton>
        </form>}
        {hasPending && <p className="wallet-status" role="status">یک پرداخت در حال بررسی داری. برای جلوگیری از پرداخت تکراری، درخواست تازه ثبت نکن.</p>}
      </section>
      <section className="account-card"><div className="wallet-section-heading"><h2>گردش کیف پول</h2><button className="button secondary" type="button" disabled={busy} onClick={() => void load()}>تازه‌سازی</button></div>
        {!wallet?.entries.length ? <p className="muted">هنوز تراکنشی ثبت نشده است.</p> : <ol className="wallet-history">{wallet.entries.map(item => <li key={item.id}><div><b>{walletEntryLabel(item.kind)}</b><time>{new Intl.DateTimeFormat('fa-IR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(item.created_at))}</time></div><strong>{['order_debit','package_debit'].includes(item.kind) ? '−' : '+'} {walletToman(item.amount_toman)}</strong><small>موجودی پس از تراکنش: {walletToman(item.balance_after_toman)}</small></li>)}</ol>}
      </section>
      {!!wallet?.topups.length && <section className="account-card"><h2>درخواست‌های شارژ</h2><ol className="wallet-history">{wallet.topups.map(item => <li key={item.id}><div><b>{walletToman(item.amount_toman)}</b><span>{topupLabel(item.status)}</span></div>{item.status === 'pending' && item.redirect_url && <button className="button secondary" type="button" onClick={() => continuePayment(item.redirect_url!)}>ادامهٔ همان پرداخت</button>}</li>)}</ol></section>}
    </>}
  </div>;
}
