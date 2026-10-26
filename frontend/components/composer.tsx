"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  api,
  createIdempotencyKey,
  ApiError,
  errorMessage,
  approvedPaymentRedirect,
  type Order,
  type Preview,
} from "@/lib/api";
import {
  isPending,
  latinDigits,
  normalizePhone,
  statusLabel,
  toman,
  validPhone,
} from "@/lib/format";
import { useApp } from "./app-provider";
import { AuthGate } from "./auth-gate";
import { BusyButton, ErrorBox, ServiceState } from "./feedback";
import { Icon, type IconName } from "./icons";
import { FreeSendsBalance } from "./free-sends";

const categoryIcons: Record<string, IconName> = {
  body: "drop",
  breath: "breath",
  noise: "sound",
  shared_space: "space",
  appreciation: "heart",
  encouragement: "leaf",
  congratulations: "sparkle",
};
const stepLabels = ["حرفت رو بنویس", "متن نهایی و ارسال"];

export function Composer({ onExit }: { onExit?: () => void }) {
  const { data, reload } = useApp();
  const [step, setStep] = useState(0);
  const activeStep = Math.min(step, stepLabels.length - 1);
  const [category, setCategory] = useState("appreciation");
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [recipient, setRecipient] = useState("");
  const [consent, setConsent] = useState(false);
  const [order, setOrder] = useState<Order | null>(null);
  const [busy, setBusy] = useState(false);
  const [pollingError, setPollingError] = useState("");
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const awaitingPayment =
    !!order &&
    ["awaiting_payment", "pending_payment", "created"].includes(order.status);
  const finished = !!order && !awaitingPayment;
  const isFree = order?.is_free ?? preview?.is_free ?? false;
  const unsuccessful =
    !!order && ["failed", "cancelled", "blocked"].includes(order.status);
  const idempotencyKey = useRef("");
  const heading = useRef<HTMLHeadingElement>(null);
  const previousStage = useRef(`${step}:${awaitingPayment}:${finished}`);

  useEffect(() => {
    const stage = `${step}:${awaitingPayment}:${finished}`;
    if (previousStage.current === stage) return;
    previousStage.current = stage;
    heading.current?.focus();
  }, [step, awaitingPayment, finished]);

  useEffect(() => {
    if (!order || !isPending(order.status)) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    async function poll() {
      if (cancelled || attempts >= 20) return;
      attempts += 1;
      try {
        const result = await api<Order>(`/orders/${order!.id}`);
        if (!cancelled) {
          setOrder(result);
          setPollingError("");
          if (result.financial_status === "free_credit_returned") void reload();
        }
        if (!cancelled && isPending(result.status) && attempts < 20)
          timer = setTimeout(poll, 2000);
      } catch (error) {
        if (!cancelled) setPollingError(errorMessage(error));
      }
    }
    timer = setTimeout(poll, 1500);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [order?.id, order?.status]);

  function handleError(error: unknown) {
    setError(errorMessage(error));
    if (error instanceof ApiError && error.code === "free_quota_changed") {
      setPreview(null);
      setConsent(false);
      idempotencyKey.current = "";
      void reload();
    }
    if (error instanceof ApiError && error.code === "authentication_required")
      void reload();
    if (error instanceof ApiError && error.fields) {
      setFields(
        Object.fromEntries(
          Object.entries(error.fields).map(([key, value]) => [
            key,
            Array.isArray(value) ? value.join(" ") : value,
          ]),
        ),
      );
    }
  }

  function advanceDraft(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setFields({});
    if (text.trim().length < 3) {
      setFields({ text: "حرفت را در حداقل ۳ حرف بنویس یا یک موضوع را انتخاب کن." });
      document.getElementById("message-text")?.focus();
      return;
    }
    setStep(1);
    setPreview(null);
    setConsent(false);
    idempotencyKey.current = "";
  }

  async function makePreview(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setFields({});
    if (!data?.authenticated) { setError("اول شماره خودت رو تأیید کن."); return; }
    if (!validPhone(recipient)) {
      setFields({ recipient_phone: "شماره موبایل گیرنده را با ۰۹ و ۱۱ رقم وارد کن." });
      document.getElementById("quote-recipient")?.focus();
      return;
    }
    if (text.trim().length < 3) {
      setFields({
        text: "حرفت را در حداقل ۳ حرف بنویس یا از مثال موضوع استفاده کن.",
      });
      document.getElementById("message-text")?.focus();
      return;
    }
    setBusy(true);
    try {
      const result = await api<Preview>("/messages/preview", {
        method: "POST",
        body: { category, text: text.trim(), recipient_phone: normalizePhone(recipient) },
      });
      setPreview(result);
      setConsent(false);
      idempotencyKey.current = "";
    } catch (error) {
      handleError(error);
    } finally {
      setBusy(false);
    }
  }

  async function createOrder(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setFields({});
    if (!validPhone(recipient)) {
      setFields({
        recipient_phone: "شماره موبایل گیرنده را با ۰۹ و ۱۱ رقم وارد کن.",
      });
      document.getElementById("quote-recipient")?.focus();
      return;
    }
    if (!consent) {
      setFields({ consent: "برای ادامه، تأیید کن که هدف پیام کمک کردن است." });
      document.getElementById("respect-consent")?.focus();
      return;
    }
    if (!preview || !data?.authenticated) return;
    if (!order && Date.parse(preview.expires_at) <= Date.now()) {
      setError(
        "مهلت پیش‌نمایش تمام شده. شماره یا متن را ویرایش کن تا پیش‌نمایش تازه ساخته شود.",
      );
      return;
    }
    setBusy(true);
    try {
      let currentOrder = order;
      if (!currentOrder) {
        if (!idempotencyKey.current)
          idempotencyKey.current = createIdempotencyKey();
        currentOrder = await api<Order>("/orders", {
          method: "POST",
          body: {
            preview_id: preview.preview_id,
            recipient_phone: normalizePhone(recipient),
            consent, terms_version: preview.terms_version,
          },
          idempotencyKey: idempotencyKey.current,
        });
        setOrder(currentOrder);
      }
      // Continue the same reviewed order on a retry, without another confirmation screen.
      if (["awaiting_payment", "pending_payment", "created"].includes(currentOrder.status))
        await payOrder(currentOrder);
    } catch (error) {
      handleError(error);
    } finally {
      setBusy(false);
    }
  }

  async function payOrder(currentOrder: Order) {
    if (currentOrder.is_free) {
      setOrder(await api<Order>(`/orders/${currentOrder.id}/confirm-free`, { method: "POST", body: {} }));
      await reload();
      return;
    }
    if (data?.payment_backend === 'zarinpal') {
      const result = await api<{redirect_url?: string}>(`/orders/${currentOrder.id}/payments`, {
        method: 'POST', body: {}, idempotencyKey: idempotencyKey.current || (idempotencyKey.current = createIdempotencyKey()),
      });
      if (result.redirect_url) window.location.assign(approvedPaymentRedirect(result.redirect_url, !!data.demo_mode));
      else setOrder(await api<Order>(`/orders/${currentOrder.id}`));
      return;
    }
    const result = await api<Pick<Order, "id" | "status">>(
      `/orders/${currentOrder.id}/pay-demo`,
      { method: "POST", body: {} },
    );
    setOrder({ ...currentOrder, ...result });
  }


  async function refreshOrder() {
    if (!order) return;
    setBusy(true);
    setPollingError("");
    try {
      setOrder(await api<Order>(`/orders/${order.id}`));
      if (order.is_free) await reload();
    } catch (error) {
      setPollingError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  function goBack() {
    setStep(0);
    setError("");
    setFields({});
  }
  function startOver() {
    setStep(0);
    setPreview(null);
    setText("");
    setRecipient("");
    setConsent(false);
    setOrder(null);
    setError("");
    setFields({});
    idempotencyKey.current = "";
  }
  return (
    <section
      data-update-blocked={!!(step > 0 || text || recipient || order)}
      id="compose"
      className={`compose-section wrap ${!data?.authenticated ? "composer-auth-only" : ""}`}
      data-screen={finished ? "receipt" : step}
      aria-labelledby="compose-title"
    >
      <div className="compose-toolbar">
        <button type="button" className="flow-back" disabled={busy} aria-label={step === 0 || order ? "بازگشت به معرفی" : "مرحله قبل"}
          onClick={() => step === 0 || order ? onExit?.() : goBack()}>
          <Icon name="arrow" size={20} /><span>قبلی</span>
        </button>
        <h1 id="compose-title" tabIndex={-1} ref={heading}>
          {finished ? "رسید پیامت" : !data?.authenticated ? "اول شماره خودت رو تأیید کن" : stepLabels[activeStep]}
        </h1>
        <span className="flow-page-count">۲ از ۲</span>
      </div>
      <div className="compose-layout">
        <aside className="compose-aside">
          <div className="step-list" aria-label="مراحل ارسال">
            {stepLabels.map((label, index) => (
              <div
                className={`step-item ${activeStep === index ? "active" : ""} ${activeStep > index ? "complete" : ""}`}
                aria-current={activeStep === index ? "step" : undefined}
                key={label}
              >
                <span className="step-number">
                  {activeStep > index ? (
                    <Icon name="check" size={18} />
                  ) : (
                    new Intl.NumberFormat("fa-IR").format(index + 1)
                  )}
                </span>
                <div>
                  <b>{label}</b>
                  <small>
                    {
                      [
                        "موضوع و منظور اصلی",
                        "گیرنده، متن، هزینه و تأیید ارسال",
                      ][index]
                    }
                  </small>
                </div>
              </div>
            ))}
          </div>
          <div className="aside-note">
            <Icon name="leaf" size={28} />
            <h3>نیت خوب، کلمه‌های خوب.</h3>
            <p>
              درباره یک رفتار مشخص بنویس، نه شخصیت آدم‌ها. تعریف و قدردانی هم
              همیشه جا داره.
            </p>
            <Link href="/help">
              راهنمای پیام خوب <Icon name="arrow" size={15} />
            </Link>
          </div>
        </aside>
        <div className="compose-panel">
          <div className="panel-top">
            <span>یک پیام، یک فرصت برای حال بهتر</span>
            <span className="step-count">
              {new Intl.NumberFormat("fa-IR").format(activeStep + 1)} از ۲
            </span>
          </div>
          <ServiceState />
          <ErrorBox message={error} />
          {step === 0 && !data?.authenticated && <AuthGate />}
          {step === 0 && data?.authenticated && (
            <form className="draft-form" onSubmit={advanceDraft} noValidate>
              <h2 className="form-heading" tabIndex={-1}>
                چه حرفی توی دلت مونده؟
              </h2>
              <FreeSendsBalance />
              <p className="muted form-intro">
                اول موضوع رو انتخاب کن؛ بعد خیلی ساده منظورت رو بنویس.
              </p>
              <fieldset className="category-fieldset">
                <legend>موضوع پیام</legend>
                <div className="category-grid">
                  {data?.categories.map((item) => (
                    <button
                      data-category={item.id}
                      className={`category-card ${category === item.id ? "selected" : ""}`}
                      key={item.id}
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        setCategory(item.id);
                        setText(item.example);
                        setFields({});
                        setError("");
                      }}
                      aria-pressed={category === item.id}
                    >
                      <Icon name={categoryIcons[item.id] || "chat"} />
                      <span>{item.label}</span>
                      {category === item.id && (
                        <span className="category-check">
                          <Icon name="check" size={11} />
                        </span>
                      )}
                    </button>
                  ))}
                </div>
                {data && data.categories.length === 0 && (
                  <p className="field-error">
                    موضوعی برای ارسال فعال نیست؛ لطفاً بعداً مراجعه کن.
                  </p>
                )}
              </fieldset>
              <div className="field-label-row">
                <label htmlFor="message-text">حرفی که می‌خوای برسونی</label>
              </div>
              <textarea
                id="message-text"
                value={text}
                onChange={(event) => setText(event.target.value)}
                maxLength={280}
                rows={4}
                placeholder="مثلاً: می‌خوام از دوستم بابت مهربونی و کمکش تشکر کنم…"
                aria-describedby={`message-hint message-count${fields.text ? " message-error" : ""}`}
                aria-invalid={!!fields.text}
                disabled={!data || busy}
              />
              <div className="textarea-meta">
                <span id="message-count">
                  {new Intl.NumberFormat("fa-IR").format(text.length)} / ۲۸۰
                </span>
              </div>
              {fields.text && (
                <p className="field-error" id="message-error">
                  {fields.text}
                </p>
              )}
              <div className="message-guidance" id="message-hint" role="note">
                <Icon name="info" size={19} />
                <p>
                  اسم، نشانی یا اطلاعات خصوصی کسی رو ننویس. دربارهٔ یک رفتار مشخص حرف بزن، نه شخصیت آدم‌ها.
                </p>
              </div>
              <div className="form-actions">
                <span className="small muted">دیدن پیش‌نمایش رایگانه</span>
                <BusyButton
                  busy={busy}
                  className="button primary"
                  disabled={!data?.authenticated || !data.categories.length}
                >
                  بعدی؛ متن نهایی و ارسال <Icon name="arrow" size={19} />
                </BusyButton>
              </div>
            </form>
          )}

          {step > 0 && !finished && (
            <form className="review-form" aria-labelledby="compose-title" onSubmit={preview ? createOrder : makePreview} noValidate>
              {!data?.authenticated && <AuthGate />}
              <label htmlFor="quote-recipient">شماره موبایل گیرنده</label>
              <input id="quote-recipient" type="tel" inputMode="tel" dir="ltr"
                value={recipient}
                onChange={event => {
                  const value = latinDigits(event.target.value);
                  if (normalizePhone(value) !== normalizePhone(recipient)) {
                    setPreview(null);
                    setConsent(false);
                    idempotencyKey.current = "";
                  }
                  setRecipient(value);
                  setFields({});
                  setError("");
                }}
                autoComplete="off" placeholder="0912 345 6789" disabled={busy}
                readOnly={!!order}
                aria-invalid={!!fields.recipient_phone}
                aria-describedby={`quote-recipient-hint${fields.recipient_phone ? " quote-recipient-error" : ""}`} />
              <p id="quote-recipient-hint" className="small muted review-phone-hint">فقط یک شماره موبایل ایران؛ ارسال به خودت مجاز نیست.</p>
              {fields.recipient_phone && <p className="field-error" id="quote-recipient-error">{fields.recipient_phone}</p>}
              {preview ? <>
              <div className="final-message">
                <div className="final-message-header">
                  <Icon name="leaf" size={19} />
                  <span>متن نهایی پیام</span>
                </div>
                <p>{preview.full_sms || preview.rewritten_text}</p>
                <div className="final-message-footer">
                  <Icon name="shield" size={15} /> هویت فرستنده پنهانه؛ پاسخ مستقیم فعال نیست.
                </div>
              </div>
              <div className="preview-info">
                <span>
                  <Icon name="sparkle" size={17} />
                  {preview.moderation_mode === "ollama_curated" ? "انتخاب با کمک هوش مصنوعی" : "متن آمادهٔ بررسی‌شده"}
                </span>
                <span>
                  هزینه: <b>{isFree ? "رایگان؛ از سهمیهٔ هدیه" : toman(order?.amount_toman ?? preview.price_toman)}</b> · {preview.sms_segments || "—"} بخش پیامک
                </span>
              </div>
              <label className="checkbox-label" htmlFor="respect-consent">
                <input id="respect-consent" type="checkbox" checked={consent}
                  disabled={busy || !!order}
                  onChange={event => setConsent(event.target.checked)}
                  aria-invalid={!!fields.consent}
                  aria-describedby={fields.consent ? "consent-error" : undefined} />
                <span>
                  این فرد رو می‌شناسم؛ هدفم کمک و یادآوریه، نه تحقیر، تهدید یا مزاحمت.
                  {" "}<Link href="/privacy">قوانین استفاده</Link> رو می‌پذیرم.
                </span>
              </label>
              {fields.consent && <p className="field-error" id="consent-error">{fields.consent}</p>}
              {!isFree && data && (!data.demo_mode || data.payment_backend === "zarinpal") && (
                <p className="small muted">
                  {data?.payment_backend === "zarinpal" ? "برای پرداخت به درگاه امن منتقل می‌شی." : "۳ ارسال هدیه‌ات تمام شده. ارسال پولی فعلاً بسته است؛ تا فعال‌شدن پرداخت نمی‌تونی پیام تازه بفرستی."}
                </p>
              )}
              {awaitingPayment && (
                <p className="small muted" role="status">سفارش ثبت شده؛ تلاش دوباره همین سفارش رو ادامه می‌ده.</p>
              )}
              <div className="form-actions review-actions">
                <button className="button ghost" type="button" disabled={busy || !!order}
                  onClick={() => { setStep(0); setConsent(false); setError(""); setFields({}); }}>
                  اصلاح حرفم
                </button>
                <BusyButton type="submit" className="button primary" busy={busy}
                  disabled={!data?.authenticated || (!isFree && !data.demo_mode && data.payment_backend !== "zarinpal")}>
                  {isFree ? (awaitingPayment ? "تلاش دوباره برای ارسال رایگان" : data?.demo_mode ? "ارسال رایگان آزمایشی" : "تأیید و ارسال رایگان") : !data?.demo_mode && data?.payment_backend === "disabled" ? "ارسال پولی فعلاً بسته است" : awaitingPayment ? "تلاش دوباره برای پرداخت" : data?.payment_backend === "zarinpal" ? "تأیید و پرداخت" : "تأیید و ارسال آزمایشی"}
                  <Icon name="arrow" size={18} />
                </BusyButton>
              </div>
              </> : <>
                <div className="review-placeholder" role="note">
                  <Icon name="chat" size={24} />
                  <p>شماره رو وارد کن تا متن نهایی و هزینهٔ همین پیام آماده بشه.</p>
                </div>
                <div className="form-actions review-actions">
                  <button className="button ghost" type="button" disabled={busy} onClick={goBack}>اصلاح حرفم</button>
                  <BusyButton type="submit" className="button primary" busy={busy} disabled={!data?.authenticated}>
                    آماده‌سازی متن <Icon name="arrow" size={18} />
                  </BusyButton>
                </div>
              </>}
            </form>
          )}

          {finished && order && (
            <div className="receipt-panel">
              <div
                className={`receipt-icon ${unsuccessful ? "has-failed" : ""}`}
              >
                <Icon
                  name={
                    isPending(order.status)
                      ? "clock"
                      : unsuccessful
                        ? "info"
                        : "check"
                  }
                  size={32}
                />
              </div>
              <h2 className="form-heading" tabIndex={-1}>
                {isPending(order.status)
                  ? "پیامت در مسیر پردازشه."
                  : unsuccessful
                    ? "ارسال انجام نشد."
                    : data?.demo_mode
                      ? "آزمایش ارسال ثبت شد."
                      : "وضعیت پیامت ثبت شد."}
              </h2>
              <p className="small">مالی: {order.financial_status === "free_credit_returned" ? "رایگان؛ سهمیه برگشت داده شد" : order.is_free ? "رایگان؛ بدون پرداخت" : order.financial_status === "refunded" ? "مسترد شد" : order.financial_status === "refund_pending" ? "بازپرداخت در حال پیگیری است" : order.financial_status === "verified" ? "تأیید شد" : "در انتظار"}</p>
              <FreeSendsBalance />
              <p className="receipt-status" role="status">
                {statusLabel(order.status)}
              </p>
              <p className="muted">
                {data?.demo_mode
                  ? "این نتیجه مربوط به محیط آزمایشی است. پیام واقعی به گیرنده ارسال نشده و هزینه‌ای دریافت نشده است."
                  : "وضعیت ارسال را اینجا یا در پیام‌های من بررسی کن. وضعیت پیام به معنی خوانده‌شدن آن نیست."}
              </p>
              <div className="receipt-id">
                <span>شناسه پیگیری</span>
                <bdi>{order.id}</bdi>
              </div>
              <ErrorBox message={pollingError} focus={false} />
              <div className="receipt-actions">
                <BusyButton
                  className="button secondary"
                  busy={busy}
                  onClick={refreshOrder}
                >
                  <Icon name="refresh" size={17} /> به‌روزرسانی وضعیت
                </BusyButton>
                <Link className="button ghost" href="/history">
                  پیام‌های من
                </Link>
              </div>
              <button className="text-button" type="button" onClick={startOver}>
                نوشتن یک پیام دیگر <Icon name="arrow" size={16} />
              </button>
            </div>
          )}
        </div>
      </div>
      <p className="compose-bottom">
        <Icon name="lock" size={16} /> شماره شما برای گیرنده پنهانه؛ سرویس برای
        جلوگیری از سوءاستفاده، فرستنده رو شناسایی می‌کنه.
      </p>
    </section>
  );
}
