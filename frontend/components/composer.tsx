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
  normalizePhone,
  statusLabel,
  toman,
  validPhone,
} from "@/lib/format";
import { useApp } from "./app-provider";
import { AuthGate } from "./auth-gate";
import { BusyButton, ErrorBox, ServiceState } from "./feedback";
import { Icon, type IconName } from "./icons";

const categoryIcons: Record<string, IconName> = {
  body: "drop",
  breath: "breath",
  noise: "sound",
  shared_space: "space",
  appreciation: "heart",
  encouragement: "leaf",
  congratulations: "sparkle",
};
const stepLabels = ["حرفت رو بنویس", "شماره گیرنده", "متن نهایی", "تأیید و ارسال"];

export function Composer({ onExit }: { onExit?: () => void }) {
  const { data, reload } = useApp();
  const [step, setStep] = useState(0);
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
  }

  async function makePreview(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setFields({});
    if (!data?.authenticated) { setError("اول شماره خودت رو تأیید کن."); return; }
    if (!validPhone(recipient)) { setError("شماره گیرنده را درست وارد کن."); return; }
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
      setStep(2);
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
      document.getElementById("recipient-phone")?.focus();
      return;
    }
    if (!consent) {
      setFields({ consent: "برای ادامه، تأیید کن که هدف پیام کمک کردن است." });
      document.getElementById("respect-consent")?.focus();
      return;
    }
    if (!preview || !data?.authenticated) return;
    if (Date.parse(preview.expires_at) <= Date.now()) {
      setError(
        "مهلت پیش‌نمایش تمام شده. به مرحله قبل برگرد و متن نهایی را دوباره بساز.",
      );
      return;
    }
    setBusy(true);
    try {
      if (!idempotencyKey.current)
        idempotencyKey.current = createIdempotencyKey();
      const result = await api<Order>("/orders", {
        method: "POST",
        body: {
          preview_id: preview.preview_id,
          recipient_phone: normalizePhone(recipient),
          consent, terms_version: preview.terms_version,
        },
        idempotencyKey: idempotencyKey.current,
      });
      setOrder(result);
    } catch (error) {
      handleError(error);
    } finally {
      setBusy(false);
    }
  }

  async function payDemo() {
    if (!order) return;
    setError("");
    setBusy(true);
    try {
      if (data?.payment_backend === 'zarinpal') {
        const result = await api<{redirect_url?: string}>(`/orders/${order.id}/payments`, {
          method: 'POST', body: {}, idempotencyKey: idempotencyKey.current || (idempotencyKey.current = createIdempotencyKey()),
        });
        if (result.redirect_url) window.location.assign(approvedPaymentRedirect(result.redirect_url, !!data.demo_mode));
        else await refreshOrder();
        return;
      }
      const result = await api<Pick<Order, "id" | "status">>(
        `/orders/${order.id}/pay-demo`,
        { method: "POST", body: {} },
      );
      setOrder({ ...order, ...result });
    } catch (error) {
      handleError(error);
    } finally {
      setBusy(false);
    }
  }

  async function refreshOrder() {
    if (!order) return;
    setBusy(true);
    setPollingError("");
    try {
      setOrder(await api<Order>(`/orders/${order.id}`));
    } catch (error) {
      setPollingError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  function goBack() {
    setStep((value) => Math.max(0, value - 1));
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
      data-screen={awaitingPayment ? "payment" : finished ? "receipt" : step}
      aria-labelledby="compose-title"
    >
      <div className="compose-toolbar">
        <button type="button" className="flow-back" disabled={busy} aria-label={step === 0 || order ? "بازگشت به معرفی" : "مرحله قبل"}
          onClick={() => step === 0 || order ? onExit?.() : goBack()}>
          <Icon name="arrow" size={20} /><span>قبلی</span>
        </button>
        <h1 id="compose-title" tabIndex={-1} ref={heading}>
          {awaitingPayment ? "یک نگاه آخر" : finished ? "رسید پیامت" : !data?.authenticated ? "اول شماره خودت رو تأیید کن" : stepLabels[step]}
        </h1>
        <span className="flow-page-count">۲ از ۲</span>
      </div>
      <div className="compose-layout">
        <aside className="compose-aside">
          <div className="step-list" aria-label="مراحل ارسال">
            {stepLabels.map((label, index) => (
              <div
                className={`step-item ${step === index ? "active" : ""} ${step > index ? "complete" : ""}`}
                aria-current={step === index ? "step" : undefined}
                key={label}
              >
                <span className="step-number">
                  {step > index ? (
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
                        "یک گیرنده آشنا",
                        "یک لحن محترمانه‌تر",
                        "تأیید و پرداخت آزمایشی",
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
              {new Intl.NumberFormat("fa-IR").format(step + 1)} از ۴
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
                aria-describedby={`message-hint${fields.text ? " message-error" : ""}`}
                aria-invalid={!!fields.text}
                disabled={!data || busy}
              />
              <div className="textarea-meta">
                <span id="message-hint">
                  اسم، نشانی یا اطلاعات خصوصی کسی رو ننویس.
                </span>
                <span>
                  {new Intl.NumberFormat("fa-IR").format(text.length)} / ۲۸۰
                </span>
              </div>
              {fields.text && (
                <p className="field-error" id="message-error">
                  {fields.text}
                </p>
              )}
              <div className="rewrite-note">
                <Icon name="sparkle" size={19} />
                <p>
                  {data?.rewrite_mode === "ollama"
                    ? "انتخاب متن بررسی‌شده با کمک هوش مصنوعی."
                    : "انتخاب از متن‌های آمادهٔ بررسی‌شده."}
                </p>
              </div>
              <div className="form-actions">
                <span className="small muted">دیدن پیش‌نمایش رایگانه</span>
                <BusyButton
                  busy={busy}
                  className="button primary"
                  disabled={!data?.authenticated || !data.categories.length}
                >
                  بعدی؛ شماره گیرنده <Icon name="arrow" size={19} />
                </BusyButton>
              </div>
            </form>
          )}

          {step === 1 && (
            <form className="recipient-form" onSubmit={makePreview} noValidate>
              <h2 className="form-heading">به دست چه کسی برسه؟</h2>
              <p className="muted form-intro">شماره کسی رو وارد کن که می‌شناسی. شماره تو به او نمایش داده نمی‌شه.</p>
              <AuthGate />
              <label htmlFor="quote-recipient">شماره موبایل گیرنده</label>
              <input id="quote-recipient" type="tel" inputMode="tel" dir="ltr"
                value={recipient} onChange={e => setRecipient(e.target.value)}
                autoComplete="off" placeholder="0912 345 6789" disabled={busy}
                aria-describedby="quote-recipient-hint" />
              <p id="quote-recipient-hint" className="small muted">فقط یک شماره موبایل ایران؛ ارسال به خودت مجاز نیست.</p>
              <div className="form-actions">
                <span className="small muted">قبل از ارسال، متن نهایی و هزینه رو می‌بینی.</span>
                <BusyButton busy={busy} className="button primary full-width" disabled={!data?.authenticated}>
                  بعدی؛ دیدن متن نهایی <Icon name="arrow" size={19} />
                </BusyButton>
              </div>
            </form>
          )}

          {step === 2 && preview && (
            <div>
              <h2 className="form-heading" tabIndex={-1}>
                این‌طوری مهربون‌تره.
              </h2>
              <p className="muted form-intro">
                این متن به‌جای حرف اولیه‌ات ثبت می‌شه. قبل از ادامه با دقت
                بخونش.
              </p>
              <div className="final-message">
                <div className="final-message-header">
                  <Icon name="leaf" size={19} />
                  <span>متن نهایی پیام</span>
                </div>
                <p>{preview.full_sms || preview.rewritten_text}</p>
                <div className="final-message-footer">
                  <Icon name="shield" size={15} /> بدون نمایش شماره فرستنده به
                  گیرنده
                </div>
              </div>
              <p className="small muted">
                گیرنده امکان پاسخ یا ارتباط با فرستنده نداره. مدیریت دریافت پیام
                از صفحه «قطع دریافت» انجام می‌شه.
              </p>
              <div className="preview-info">
                <span>
                  <Icon name="sparkle" size={17} />
                  {preview.moderation_mode === "ollama_curated"
                    ? "انتخاب متن با کمک هوش مصنوعی"
                    : "متن آمادهٔ بررسی‌شده"}
                </span>
                <span>
                  هزینه: <b>{toman(preview.price_toman)}</b> · {preview.sms_segments || "—"} بخش پیامک
                </span>
              </div>
              <div className="form-actions">
                <button className="button ghost" type="button" onClick={() => { setStep(0); setError(""); setFields({}); }}>
                  اصلاح حرفم
                </button>
                <button
                  className="button primary"
                  type="button"
                  onClick={() => {
                    setStep(3);
                    setError("");
                  }}
                >
                  خوبه، ادامه می‌دم <Icon name="arrow" size={19} />
                </button>
              </div>
            </div>
          )}

          {step === 3 && preview && !order && (
            <div>
              <h2 className="form-heading" tabIndex={-1}>
                با خیال راحت تأیید کن.
              </h2>
              <p className="muted form-intro">
                شماره رو با دقت وارد کن؛ گیرنده باید همون کسی باشه که واقعاً
                می‌شناسی.
              </p>
              <form id="recipient-order-form" onSubmit={createOrder} noValidate>
                <label htmlFor="recipient-phone">شماره موبایل گیرنده</label>
                <input
                  id="recipient-phone"
                  type="tel"
                  inputMode="tel"
                  dir="ltr"
                  autoComplete="off"
                  readOnly
                  value={recipient}
                  onChange={(event) => {
                    setRecipient(event.target.value);
                    idempotencyKey.current = "";
                  }}
                  placeholder="0912 345 6789"
                  aria-invalid={!!fields.recipient_phone}
                  aria-describedby={
                    fields.recipient_phone
                      ? "recipient-error"
                      : "recipient-hint"
                  }
                />
                <p className="small muted" id="recipient-hint">
                  فقط شماره موبایل ایران. ارسال به شماره خودت مجاز نیست.
                </p>
                {fields.recipient_phone && (
                  <p className="field-error" id="recipient-error">
                    {fields.recipient_phone}
                  </p>
                )}
              </form>
              <label className="checkbox-label" htmlFor="respect-consent">
                <input
                  id="respect-consent"
                  type="checkbox"
                  form="recipient-order-form"
                  checked={consent}
                  onChange={(event) => setConsent(event.target.checked)}
                  aria-describedby={
                    fields.consent ? "consent-error" : undefined
                  }
                />
                <span>
                  این فرد رو می‌شناسم؛ هدفم کمک و یادآوریه، نه تحقیر، تهدید یا
                  مزاحمت. <Link href="/privacy">قوانین استفاده</Link> رو
                  می‌پذیرم.
                </span>
              </label>
              {fields.consent && (
                <p className="field-error" id="consent-error">
                  {fields.consent}
                </p>
              )}
              <div className="form-actions">
                <button
                  className="button ghost"
                  type="button"
                  onClick={goBack}
                  disabled={busy}
                >
                  بازگشت
                </button>
                <BusyButton
                  type="submit"
                  form="recipient-order-form"
                  className="button primary"
                  busy={busy}
                  disabled={!data?.authenticated}
                >
                  بررسی و پرداخت <Icon name="arrow" size={19} />
                </BusyButton>
              </div>
            </div>
          )}

          {awaitingPayment && order && (
            <div>
              <h2 className="form-heading" tabIndex={-1}>
                یک نگاه آخر، بعد ارسال.
              </h2>
              <div className="payment-summary">
                <div>
                  <span>شماره گیرنده</span>
                  <bdi>{normalizePhone(recipient)}</bdi>
                </div>
                <div>
                  <span>متن تأییدشده</span>
                  <p>{preview?.full_sms || preview?.rewritten_text}</p>
                </div>
                <div>
                  <span>هزینه کل</span>
                  <strong>{toman(order.amount_toman)}</strong>
                </div>
              </div>
              {data?.payment_backend !== "zarinpal" && data?.demo_mode ? (
                <div className="demo-payment-note">
                  <Icon name="info" size={20} />
                  <p>
                    این پرداخت آزمایشیه؛ پولی کم نمی‌شه و پیام واقعی به گیرنده نمی‌ره. با
                    تأیید، صف و وضعیت ارسال رو آزمایش می‌کنی.
                  </p>
                </div>
              ) : (
                <p className="error-box">
                  {data?.payment_backend === "zarinpal" ? "برای پرداخت به صفحه امن درگاه منتقل می‌شی؛ بعد از برگشت، وضعیت را در پیام‌های من ببین." : "درگاه پرداخت فعلاً فعال نیست."}
                </p>
              )}
              <BusyButton
                className="button primary full-width"
                busy={busy}
                onClick={payDemo}
                disabled={!data?.demo_mode && data?.payment_backend !== "zarinpal"}
              >
                {data?.payment_backend === "zarinpal" ? "ادامه در درگاه پرداخت" : "تأیید پرداخت آزمایشی و ثبت ارسال"} <Icon name="arrow" size={18} />
              </BusyButton>
              <p className="small muted text-center">
                برای تلاش دوباره، همین پرداخت ادامه پیدا می‌کنه و سفارش تازه
                ساخته نمی‌شه.
              </p>
            </div>
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
              <p className="small">مالی: {order.financial_status === "refunded" ? "مسترد شد" : order.financial_status === "refund_pending" ? "بازپرداخت در حال پیگیری است" : order.financial_status === "verified" ? "تأیید شد" : "در انتظار"}</p>
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
