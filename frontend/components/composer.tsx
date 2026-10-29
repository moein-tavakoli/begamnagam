"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  api,
  createIdempotencyKey,
  ApiError,
  errorMessage,
  type Order,
  type Preview,
} from "@/lib/api";
import {
  isPending,
  latinDigits,
  normalizePhone,
  statusLabel,
  validPhone,
} from "@/lib/format";
import { useApp } from "./app-provider";
import { AuthGate } from "./auth-gate";
import { BusyButton, DeliveryReason, ErrorBox, ServiceState } from "./feedback";
import { Icon, type IconName } from "./icons";
import { FreeSendsBalance } from "./free-sends";
import { TermsDialog } from "./terms-dialog";
import { CreditPackages } from "./credit-packages";
import { draftProblem, draftTopicHint } from "@/lib/composer-draft";
import type { MessageTone } from '@/lib/message-tones';
import { MessageTonePicker } from './message-tone-picker';
import { RewriteLoading } from './rewrite-loading';
import { alternativeRequest, messageAlternatives, type MessageAlternative } from '@/lib/message-alternatives';

const categoryIcons: Record<string, IconName> = {
  body: "drop",
  breath: "breath",
  noise: "sound",
  shared_space: "space",
  appreciation: "heart",
  encouragement: "leaf",
  congratulations: "sparkle",
  punctuality: "clock",
  listening: "chat",
  conversation: "chat",
  personal_space: "shield",
  phone_etiquette: "phone",
  neighbor: "space",
  parking: "space",
  teamwork: "heart",
  apology: "heart",
  good_wishes: "sparkle",
  environment: "leaf",
};
const stepLabels = ["حرفت رو بنویس", "متن نهایی و ارسال"];

export function Composer({ onExit }: { onExit?: () => void }) {
  const { data, reload } = useApp();
  const [step, setStep] = useState(0);
  const activeStep = Math.min(step, stepLabels.length - 1);
  const [category, setCategory] = useState("");
  const [showAllCategories, setShowAllCategories] = useState(false);
  // Keep the selected topic visible when the extra options are collapsed.
  const visibleCategories = data?.categories.filter((item, index) =>
    showAllCategories || index < 7 || item.id === category) ?? [];
  const hiddenCategoryCount = (data?.categories.length ?? 0) - visibleCategories.length;
  const [text, setText] = useState("");
  const [messageTone, setMessageTone] = useState<MessageTone>('polite');
  const toneOptions = data?.message_tones ?? [];
  const tonesKey = toneOptions.map(item => item.id).join(',');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [recipient, setRecipient] = useState("");
  const [consent, setConsent] = useState(false);
  const [order, setOrder] = useState<Order | null>(null);
  const [busy, setBusy] = useState(false);
  const [preparingText, setPreparingText] = useState(false);
  const previewInFlight = useRef(false);
  const [pollingError, setPollingError] = useState("");
  const [error, setError] = useState("");
  const [alternatives, setAlternatives] = useState<MessageAlternative[]>([]);
  const [selectedAlternative, setSelectedAlternative] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const freeformRewrite = data?.rewrite_mode === "gapgpt" || data?.rewrite_mode === "ollama";
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
  const alternativesPanel = useRef<HTMLFieldSetElement>(null);

  useEffect(() => {
    if (alternatives.length > 0) alternativesPanel.current?.focus();
  }, [alternatives]);

  useEffect(() => {
    setAlternatives([]); setSelectedAlternative(null);
  }, [text, recipient, messageTone, step, data?.session_identity]);

  useEffect(() => {
    if (!data || order || toneOptions.some(item => item.id === messageTone)) return;
    const next = data.default_message_tone ?? 'polite';
    if (messageTone === next) return;
    setMessageTone(next); setPreview(null); setConsent(false); idempotencyKey.current = '';
  }, [tonesKey, data?.default_message_tone, messageTone, order?.id]);

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
          if (["free_credit_returned", "credit_returned", "wallet_returned"].includes(result.financial_status || "")) void reload();
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
    setAlternatives(messageAlternatives(error instanceof ApiError ? error.details : undefined));
    setSelectedAlternative(null);
    if (error instanceof ApiError && error.code === 'tone_unavailable') {
      setStep(0); setPreview(null); setConsent(false); idempotencyKey.current = ''; void reload();
    }
    if (error instanceof ApiError && error.code === "free_quota_changed") {
      setPreview(null);
      setConsent(false);
      idempotencyKey.current = "";
      void reload();
    }
    if (error instanceof ApiError && error.code === "authentication_required")
      void reload();
    if (error instanceof ApiError && error.code === "freeform_unavailable") {
      setStep(0);
      setPreview(null);
      setConsent(false);
      idempotencyKey.current = "";
      void reload();
    }
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
    const problem = draftProblem(text, category, data?.categories ?? [], freeformRewrite);
    if (problem) {
      setFields({ text: problem === "too_short"
        ? "منظورت را در حداقل ۳ حرف بنویس یا از یک مثال کمک بگیر."
        : "بازنویسی متن دلخواه هنوز فعال نیست؛ فعلاً یکی از مثال‌های پیشنهادی رو انتخاب کن." });
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
    if (previewInFlight.current || busy) return;
    setError("");
    setFields({});
    if (!data?.authenticated) { setError("اول شماره خودت رو تأیید کن."); return; }
    if (!validPhone(recipient)) {
      setFields({ recipient_phone: "شماره موبایل گیرنده را با ۰۹ و ۱۱ رقم وارد کن." });
      document.getElementById("quote-recipient")?.focus();
      return;
    }
    const alternative = alternatives.find(item => item.token === selectedAlternative);
    if (!alternative && text.trim().length < 3) {
      setFields({
        text: "منظورت را در حداقل ۳ حرف بنویس یا از یک مثال کمک بگیر.",
      });
      document.getElementById("message-text")?.focus();
      return;
    }
    previewInFlight.current = true;
    setBusy(true);
    setPreparingText(freeformRewrite && !alternative);
    try {
      const result = await api<Preview>("/messages/preview", {
        method: "POST",
        body: alternative ? alternativeRequest(alternative, normalizePhone(recipient)) : { category, text: text.trim(), recipient_phone: normalizePhone(recipient), source_mode: freeformRewrite ? 'freeform' : 'suggestion', message_tone: messageTone },
      });
      setPreview(result);
      setAlternatives([]); setSelectedAlternative(null);
      setConsent(false);
      idempotencyKey.current = "";
    } catch (error) {
      handleError(error);
    } finally {
      previewInFlight.current = false;
      setPreparingText(false);
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
    if (currentOrder.is_free || currentOrder.uses_purchased_credit) {
      setOrder(await api<Order>(`/orders/${currentOrder.id}/${currentOrder.uses_purchased_credit ? "confirm-credit" : "confirm-free"}`, { method: "POST", body: {} }));
      await reload();
      return;
    }
    throw new ApiError("روش خرید به بسته تغییر کرده؛ پیش‌نمایش تازه بساز.");
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
    setConsent(false);
    setError("");
    setFields({});
  }
  function startOver() {
    setStep(0);
    setPreview(null);
    setCategory("");
    setText("");
    setRecipient("");
    setConsent(false);
    setOrder(null);
    setError("");
    setFields({});
    idempotencyKey.current = "";
  }
  function renderActions(primary: ReactNode, disableBack = busy || !!order) {
    return (
      <div className="form-actions composer-actions" role="group" aria-label="ادامه یا بازگشت">
        <button type="button" className="button ghost composer-back" disabled={busy || disableBack || (!!order && !finished)}
          onClick={() => step === 0 || finished ? onExit?.() : goBack()}>
          <Icon name="arrow" size={18} /><span>قبلی</span>
        </button>
        {primary}
      </div>
    );
  }
  return (
    <section
      data-update-blocked={!!(step > 0 || text || recipient || order)}
      id="compose"
      className={`compose-section wrap ${!data?.authenticated ? "composer-auth-only" : ""}`}
      data-screen={finished ? "receipt" : step}
      aria-labelledby="compose-title"
    >
      <h1 id="compose-title" className="sr-only" tabIndex={-1} ref={heading}>
        {finished ? "رسید پیامت" : !data?.authenticated ? "اول شماره خودت رو تأیید کن" : stepLabels[activeStep]}
      </h1>
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
                        "منظور خودت، با مثال‌های اختیاری",
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
          {step === 1 && !preview && alternatives.length > 0 && <fieldset ref={alternativesPanel} tabIndex={-1} className="message-alternatives" disabled={busy}>
            <legend>به‌جایش می‌توانی یک پیام تازه انتخاب کنی</legend>
            <p className="small muted">متن اولیه تأیید نشد. این پیشنهادها پیام‌های آمادهٔ جداگانه‌اند؛ فقط اگر منظورت را می‌رسانند انتخابشان کن. پیش از ارسال، متن کامل را دوباره می‌بینی.</p>
            {alternatives.map(item => <label className="message-alternative" key={item.id}>
              <input type="radio" name="message-alternative" checked={selectedAlternative === item.token} onChange={() => setSelectedAlternative(item.token)} />
              <span><strong>{item.label}</strong><span>{item.text}</span></span>
            </label>)}
          </fieldset>}
          {step === 0 && !data?.authenticated && <AuthGate renderActions={renderActions} />}
          {step === 0 && data?.authenticated && (
            <form className="draft-form" onSubmit={advanceDraft} noValidate>
              <div className="draft-heading-row">
                <h2 className="form-heading" tabIndex={-1}>
                  چه حرفی توی دلت مونده؟
                </h2>
                <FreeSendsBalance compact />
              </div>
              <p className="muted form-intro">
                {freeformRewrite
                  ? "منظورت رو با کلمه‌های خودت بنویس."
                  : "فعلاً می‌تونی از مثال‌های آماده استفاده کنی."}
              </p>
              <div className="field-label-row">
                <label htmlFor="message-text">حرفی که می‌خوای برسونی</label>
              </div>
              <textarea
                id="message-text"
                value={text}
                onChange={(event) => {
                  const value = event.target.value;
                  setText(value);
                  setCategory(draftTopicHint(category, value, data.categories));
                  setFields({});
                  setError("");
                }}
                maxLength={280}
                rows={4}
                placeholder={freeformRewrite
                  ? "مثلاً: می‌خوام قبل از قرض گرفتن وسایلم از خودم اجازه بگیره…"
                  : "برای شروع یکی از مثال‌های پایین رو انتخاب کن…"}
                aria-describedby={`message-hint message-count${fields.text ? " message-error" : ""}`}
                aria-invalid={!!fields.text}
                disabled={!data || busy}
              />
              <div className="textarea-meta">
                <span id="message-count">
                  {new Intl.NumberFormat("fa-IR").format(text.length)} / ۲۸۰
                </span>
              </div>
              <MessageTonePicker options={toneOptions} value={messageTone} disabled={busy || !!order} onChange={tone => {
                setMessageTone(tone); setPreview(null); setConsent(false); setFields({}); setError(''); idempotencyKey.current = '';
              }} />
              {fields.text && (
                <p className="field-error" id="message-error">
                  {fields.text}
                </p>
              )}
              <div className="message-guidance" id="message-hint" role="note">
                <Icon name="info" size={19} />
                <p>
                  {freeformRewrite
                    ? "اسم، نشانی یا اطلاعات خصوصی ننویس؛ پیش از تأیید، متن نهایی رو بخون."
                    : "اسم، نشانی یا اطلاعات خصوصی کسی رو ننویس. دربارهٔ یک رفتار مشخص حرف بزن، نه شخصیت آدم‌ها."}
                </p>
              </div>
              {data.categories.length > 0 && <details className="suggestion-disclosure" open={!freeformRewrite || undefined}>
                <summary>{freeformRewrite ? <>از مثال‌های پیشنهادی کمک بگیر <span className="muted">(اختیاری)</span></> : "مثال‌های آماده برای ارسال"}</summary>
                <fieldset className="category-fieldset suggested-topics">
                <legend>یک مثال برای شروع</legend>
                <p className="small muted category-guidance">{freeformRewrite
                  ? "هر گزینه یک مثال داخل کادر می‌گذاره؛ متن خودت می‌تونه دربارهٔ موضوع دیگه‌ای باشه."
                  : "هر گزینه یک مثال داخل کادر می‌گذاره که می‌تونی برای پیامت انتخابش کنی."}</p>
                <div className="category-grid" id="message-categories">
                  {visibleCategories.map((item) => (
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
                        document.getElementById("message-text")?.focus();
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
                {data.categories.length > 7 && (
                  <button type="button" className="button secondary category-toggle"
                    aria-expanded={showAllCategories} aria-controls="message-categories"
                    disabled={busy} onClick={() => setShowAllCategories(value => !value)}>
                    {showAllCategories ? "مثال‌های کمتر" : `${new Intl.NumberFormat("fa-IR").format(hiddenCategoryCount)} مثال بیشتر`}
                  </button>
                )}
                </fieldset>
              </details>}
              {renderActions(
                <BusyButton
                  busy={busy}
                  className="button primary"
                  disabled={!data?.authenticated}
                >
                  بعدی؛ متن نهایی و ارسال <Icon name="arrow" size={19} />
                </BusyButton>,
              )}
            </form>
          )}

          {step > 0 && !finished && !data?.authenticated && <AuthGate renderActions={renderActions} />}
          {step > 0 && !finished && data?.authenticated && (
            <form className="review-form" aria-labelledby="compose-title" onSubmit={preview ? createOrder : makePreview} noValidate>
              <label htmlFor="quote-recipient">شماره موبایل گیرنده</label>
              <input id="quote-recipient" type="tel" inputMode="tel" dir="ltr"
                value={recipient}
                onChange={event => {
                  const value = latinDigits(event.target.value);
                  if (normalizePhone(value) !== normalizePhone(recipient)) {
                    setPreview(null);
                    setAlternatives([]); setSelectedAlternative(null);
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
                aria-describedby={fields.recipient_phone ? "quote-recipient-error" : undefined} />
              {fields.recipient_phone && <p className="field-error" id="quote-recipient-error">{fields.recipient_phone}</p>}
              {preview ? <>
              <div className="final-message">
                <div className="final-message-header">
                  <Icon name="leaf" size={19} />
                  <span>متن کامل پیامک؛ همین متن ارسال می‌شه</span>
                </div>
                <p>{preview.full_sms || preview.rewritten_text}</p>
                <div className="final-message-footer">
                  <Icon name="shield" size={15} /> هویت فرستنده پنهانه؛ پاسخ مستقیم فعال نیست.
                </div>
              </div>
              <div className="preview-info">
                <span>
                  <Icon name="sparkle" size={17} />
                  {preview.moderation_mode === "gapgpt" || preview.moderation_mode === "ollama" ? "متن بازنویسی و بررسی‌شده" : "متن آمادهٔ بررسی‌شده"}
                </span>
                <span>
                  مصرف: <b>{isFree ? "یک ارسال از هدیه" : "یک اعتبار از بسته"}</b> · {preview.sms_segments || "—"} بخش پیامک
                </span>
              </div>
              <label className="checkbox-label" htmlFor="respect-consent">
                <input id="respect-consent" type="checkbox" checked={consent}
                  disabled={busy || !!order}
                  onChange={event => setConsent(event.target.checked)}
                  aria-invalid={!!fields.consent}
                  aria-describedby={fields.consent ? "consent-error" : undefined} />
                <span>
                  متن نهایی رو خوندم و منظورم رو می‌رسونه. این فرد رو می‌شناسم؛ هدفم کمک و یادآوریه، نه تحقیر، تهدید یا مزاحمت.
                  {" "}<TermsDialog /> رو می‌پذیرم.
                </span>
              </label>
              {fields.consent && <p className="field-error" id="consent-error">{fields.consent}</p>}
              {!isFree && data?.authenticated && !order && (data.purchased_sends_remaining ?? 0) === 0 && <CreditPackages inline />}
              {awaitingPayment && (
                <p className="small muted" role="status">سفارش ثبت شده؛ تلاش دوباره همین سفارش رو ادامه می‌ده.</p>
              )}
              {data?.authenticated && renderActions(
                <BusyButton type="submit" className="button primary" busy={busy}
                  disabled={!data?.authenticated || (!isFree && !order && (data.purchased_sends_remaining ?? 0) === 0)}>
                  {isFree ? (awaitingPayment ? "تلاش دوباره برای ارسال رایگان" : data?.demo_mode ? "ارسال رایگان آزمایشی" : "تأیید و ارسال رایگان") : !order && (data?.purchased_sends_remaining ?? 0) === 0 ? "ابتدا بستهٔ پیام بخر" : awaitingPayment ? "تلاش دوباره برای ارسال" : "تأیید و ارسال با یک اعتبار"}
                  <Icon name="arrow" size={18} />
                </BusyButton>,
              )}
              </> : <>
                <div className="review-placeholder" role="note">
                  <Icon name="chat" size={24} />
                  <p>{alternatives.length > 0 ? "یکی از پیشنهادهای بالا را انتخاب کن تا پیش‌نمایش کامل آن را ببینی." : freeformRewrite ? "شماره رو وارد کن تا متن نهایی آماده بشه. قبل از ارسال، متن کامل پیامک رو می‌بینی." : "شماره رو وارد کن تا متن نهایی آماده بشه. هر ارسال یک اعتبار مصرف می‌کنه."}</p>
                </div>
                {data?.authenticated && renderActions(
                  <BusyButton type="submit" className="button primary" busy={busy} disabled={!data?.authenticated || (alternatives.length > 0 && !selectedAlternative)}>
                    {selectedAlternative ? 'پیش‌نمایش پیشنهاد انتخاب‌شده' : alternatives.length > 0 ? 'یک پیشنهاد را انتخاب کن' : 'آماده‌سازی متن'} <Icon name="arrow" size={18} />
                  </BusyButton>,
                )}
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
              <p className="small">مالی: {order.financial_status === 'wallet_returned' ? 'مبلغ به کیف پول برگشت داده شد' : order.financial_status === 'wallet_paid' ? 'پرداخت از کیف پول' : order.financial_status === "credit_returned" ? "اعتبار بسته برگشت داده شد" : order.uses_purchased_credit ? "یک اعتبار از بسته" : order.financial_status === "free_credit_returned" ? "رایگان؛ سهمیه برگشت داده شد" : order.is_free ? "رایگان؛ بدون پرداخت" : order.financial_status === "refunded" ? "مسترد شد" : order.financial_status === "refund_pending" ? "بازپرداخت در حال پیگیری است" : order.financial_status === "verified" ? "تأیید شد" : "در انتظار"}</p>
              <FreeSendsBalance />
              <p className="receipt-status" role="status">
                {statusLabel(order.status)}
              </p>
              <DeliveryReason order={order} />
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
              </div>
              <button className="text-button" type="button" onClick={startOver}>
                نوشتن یک پیام دیگر <Icon name="arrow" size={16} />
              </button>
              {renderActions(<Link className="button primary" href="/history">پیام‌های من</Link>, busy)}
            </div>
          )}
        </div>
      </div>
      <p className="compose-bottom">
        <Icon name="lock" size={16} /> شماره شما برای گیرنده پنهانه؛ سرویس برای
        جلوگیری از سوءاستفاده، فرستنده رو شناسایی می‌کنه.
      </p>
      {preparingText && <RewriteLoading />}
    </section>
  );
}
