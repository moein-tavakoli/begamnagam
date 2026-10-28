"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, approvedPaymentRedirect, createIdempotencyKey, errorMessage, type CreditPurchase, type MessagePackage } from "@/lib/api";
import { toman } from "@/lib/format";
import { useApp } from "./app-provider";
import { AuthGate } from "./auth-gate";
import { ErrorBox, ServiceState } from "./feedback";
import { walletToman } from '@/lib/wallet';
import { purchaseIntentAfterResponse, settledPurchase, type PurchaseIntent } from '@/lib/credit-purchases';

const number = new Intl.NumberFormat("fa-IR");
const purchaseStatus: Record<string, string> = { credited: "پرداخت تأیید شد و اعتبار اضافه شد", wallet_returned: "بسته تخصیص نیافت؛ مبلغ به کیف پول برگشت", unknown: "پرداخت نیازمند بررسی است؛ دوباره پرداخت نکن", pending: "در انتظار نتیجهٔ پرداخت", created: "خرید ثبت شده", failed: "پرداخت تأیید نشد؛ اعتباری اضافه نشده" };

export function CreditPackages({ inline = false }: { inline?: boolean }) {
  const { data, reload } = useApp();
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [purchase, setPurchase] = useState<CreditPurchase | null>(null);
  const key = useRef<PurchaseIntent | null>(null);
  const [pending, setPending] = useState<CreditPurchase[]>([]);
  const [method, setMethod] = useState<'wallet'|'gateway'>('gateway'), [walletConsent, setWalletConsent] = useState(false);
  useEffect(() => { if (data?.payment_options?.wallet_enabled && !data.payment_options.gateway_enabled) setMethod('wallet'); }, [data?.payment_options?.wallet_enabled,data?.payment_options?.gateway_enabled]);
  const generation = useRef(0);
  useEffect(() => {
    if (!data?.authenticated) return;
    const controller = new AbortController();
    void api<{ purchases: CreditPurchase[] }>("/credit-purchases", { signal: controller.signal }).then(result => {
      setPending(result.purchases.filter(p => ["pending", "unknown", "created"].includes(p.status)));
      const id = new URLSearchParams(window.location.search).get("purchase");
      const returned = result.purchases.find(p => p.id === id);
      if (returned) setPurchase(returned);
    }).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); });
    return () => controller.abort();
  }, [data?.authenticated]);

  async function buy(item: MessagePackage) {
    setBusy(true); setError("");
    if (!key.current || key.current.packageId !== item.id) key.current = { packageId: item.id, value: createIdempotencyKey() };
    try {
      const result = await api<CreditPurchase>("/credit-purchases", { method: "POST", body: { package_id: item.id, package_revision: item.revision, payment_method: method, wallet_consent: walletConsent, wallet_terms_version: data?.payment_options?.wallet_terms_version }, idempotencyKey: key.current.value });
      setPurchase(result);
      key.current = purchaseIntentAfterResponse(key.current, result);
      if (result.redirect_url) window.location.assign(approvedPaymentRedirect(result.redirect_url, !!data?.demo_mode));
      else if (settledPurchase(result.status)) {
        setPending(v => v.filter(p => p.id !== result.id)); await reload();
      }
      else setPending(v => [result, ...v.filter(p => p.id !== result.id)]);
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  async function refresh(item: CreditPurchase) {
    setBusy(true); setError("");
    const current = ++generation.current;
    try {
      const result = await api<CreditPurchase>(`/credit-purchases/${item.id}`);
      if (current !== generation.current) return;
      if (key.current?.purchaseId === result.id) key.current = purchaseIntentAfterResponse(key.current, result);
      setPurchase(result); setPending(v => v.map(p => p.id === result.id ? result : p).filter(p => ["pending", "unknown", "created"].includes(p.status)));
      await reload();
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  const hasPending = pending.some(p => ["pending", "unknown", "created"].includes(p.status));
  return <section className={inline ? "credit-packages" : "account-card credit-packages"} aria-label="خرید بستهٔ پیام">
    <h2>خرید بستهٔ پیام</h2>
    {!inline && <ServiceState />}
    <p className="small muted">هر پیام یک اعتبار؛ تعداد بخش‌های پیامک از اعتبار بیشتری کم نمی‌کند. ابتدا هدیه‌ها مصرف می‌شوند و اعتبار ارسال ناموفق قطعی برمی‌گردد.</p>
    {data?.authenticated ? <p className="credit-balance" role="status">هدیه: <b>{number.format(data.free_sends_remaining ?? 0)}</b> · اعتبار بسته: <b>{number.format(data.purchased_sends_remaining ?? 0)} پیام</b>{data.demo_mode && " (آزمایشی)"}</p> : <AuthGate purpose="برای خرید بسته، شمارهٔ خودت را تأیید کن." />}
    {purchase && <div className="notice" role="status"><strong>{purchaseStatus[purchase.status] || purchase.status}</strong><p>{purchase.name} · {number.format(purchase.message_count)} پیام · {toman(purchase.amount_toman)}</p>{data?.demo_mode && <p>این خرید شبیه‌سازی شده و برداشتی انجام نشده است.</p>}</div>}
    {pending.map(item => <div className="notice" key={item.id}><p>{item.name} — {purchaseStatus[item.status]}</p>{item.redirect_url && <a className="button ghost" href={approvedPaymentRedirect(item.redirect_url, !!data?.demo_mode)}>ادامهٔ همان پرداخت</a>}<button className="button ghost" type="button" disabled={busy} onClick={() => void refresh(item)}>بررسی وضعیت پرداخت</button></div>)}
    {!data?.package_checkout_enabled && <p className="small" role="status">خرید بسته فعلاً بسته است؛ بسته‌های فعال را می‌توانی ببینی.</p>}
    <ErrorBox message={error} />
    {data?.authenticated && <div className="wallet-package-payment"><label>روش پرداخت<select disabled={busy || hasPending} value={method} onChange={e => {setMethod(e.target.value as 'wallet'|'gateway');setWalletConsent(false);}}><option value="gateway" disabled={!data.payment_options?.gateway_enabled && !data.demo_mode}>زرین‌پال</option><option value="wallet" disabled={!data.payment_options?.wallet_enabled}>کیف پول · {walletToman(data.wallet_balance_toman ?? '0')}</option></select></label><label className="checkbox-label"><input type="checkbox" checked={walletConsent} disabled={busy || hasPending} onChange={e => setWalletConsent(e.target.checked)} /><span>اعتبار خرید برای خدمات سایت است و برداشت بانکی ندارد. برگشت هزینهٔ پرداخت پولی به کیف پول انجام می‌شود؛ اعتبار ارسال ناموفق بسته به بسته برمی‌گردد.</span></label><Link href="/wallet" prefetch={false}>مشاهده و شارژ کیف پول</Link></div>}
    <div className="credit-package-grid">{(data?.message_packages ?? []).map(item => <article className="credit-package" key={item.id}><h3>{item.name}</h3><p className="credit-units">{number.format(item.message_count)} <small>پیام</small></p><p>{toman(item.price_toman)}</p><button type="button" className="button primary" disabled={busy || hasPending || !data?.authenticated || !data.package_checkout_enabled || !walletConsent || (method === 'gateway' && !data.payment_options?.gateway_enabled && !data.demo_mode) || (method === 'wallet' && !data.payment_options?.wallet_enabled)} onClick={() => void buy(item)}>{busy ? "در حال بررسی…" : data?.demo_mode ? "خرید بستهٔ آزمایشی" : method === 'wallet' ? "خرید از کیف پول" : "خرید با زرین‌پال"}</button></article>)}</div>
    {data && !data.message_packages?.length && <p>فعلاً بستهٔ فعالی تعریف نشده است.</p>}
    {!inline && <Link className="button ghost" href="/#compose">نوشتن و ارسال پیام</Link>}
  </section>;
}
