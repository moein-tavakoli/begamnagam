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
  normalizePhone,
  phoneInput,
  validPhone,
} from "@/lib/format";
import { useApp } from "./app-provider";
import { AuthGate } from "./auth-gate";
import { BusyButton, DeliveryReason, ErrorBox, ServiceState } from "./feedback";
import { Icon, type IconName } from "./icons";
import { TermsDialog } from "./terms-dialog";
import { CreditPackages } from "./credit-packages";
import { draftProblem, draftTopicHint } from "@/lib/composer-draft";
import type { MessageTone } from '@/lib/message-tones';
import { MessageTonePicker } from './message-tone-picker';
import { RewriteLoading } from './rewrite-loading';
import { RecipientPhoneField } from "./recipient-phone-field";
import { ExampleFilters } from './example-filters';
import { PaperDartButton, type PaperDartHandle } from './paper-dart-button';
import { sendFeedback } from '@/lib/send-feedback';
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

type InitialReview =
  | { source: "purchase"; preview: Preview }
  | { source: "text-trial"; preview: Preview; recipientPhone: string };

export function Composer({ active = true, focusOnActivate = false, onExit, replyToken, onReplyUnavailable, sharedRecipient, initialReview }: {
  initialReview?: InitialReview;
  active?: boolean;
  focusOnActivate?: boolean;
  onExit?: () => void;
  replyToken?: string;
  onReplyUnavailable?: (message: string) => void;
  sharedRecipient?: { token: string; maskedPhone: string };
}) {
  const { data, reload } = useApp();
  const initialPreview = initialReview?.preview;
  const trialRecipient = initialReview?.source === "text-trial" ? initialReview.recipientPhone : undefined;
  const isReply = !!replyToken || !!initialPreview?.is_reply;
  const isShared = !!sharedRecipient || !!initialPreview?.is_shared_destination;
  const needsPhone = !isReply && !isShared && (!initialPreview || !!trialRecipient);
  const [draftStep, setDraftStep] = useState(initialPreview ? 1 : 0);
  const [category, setCategory] = useState("");
  const [exampleGroup, setExampleGroup] = useState<number | null>(null);
  const [text, setText] = useState("");
  const toneOptions = data?.message_tones ?? [];
  const defaultTone = toneOptions.find(item => item.id === data?.default_message_tone)?.id
    ?? toneOptions[0]?.id ?? data?.default_message_tone ?? 'firm';
  const [chosenTone, setMessageTone] = useState<MessageTone>(defaultTone);
  const messageTone = isReply && toneOptions.some(item => item.id === chosenTone) ? chosenTone : defaultTone;
  const [preview, setPreview] = useState<Preview | null>(initialPreview ?? null);
  const step = isReply ? (preview ? 1 : 0) : draftStep;
  const activeStep = Math.min(step, stepLabels.length - 1);
  const [recipient, setRecipient] = useState(trialRecipient ?? "");
  const [consent, setConsent] = useState(false);
  const [order, setOrder] = useState<Order | null>(null);
  const [busy, setBusy] = useState(false);
  const [preparingText, setPreparingText] = useState(false);
  const [sendAnimating, setSendAnimating] = useState(false);
  const sendButton = useRef<PaperDartHandle>(null);
  const orderInFlight = useRef(false);
  const previewInFlight = useRef(false);
  const [error, setError] = useState("");
  const [alternatives, setAlternatives] = useState<MessageAlternative[]>([]);
  const [selectedAlternative, setSelectedAlternative] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const freeformRewrite = data?.rewrite_mode === "gapgpt" || data?.rewrite_mode === "ollama";
  const shortDraftMessage = isReply
    ? "پاسخت را در حداقل ۳ حرف بنویس."
    : "منظورت را در حداقل ۳ حرف بنویس یا از یک مثال کمک بگیر.";
  const activeGroup = data?.category_groups?.some(group => group.id === exampleGroup) ? exampleGroup : null;
  const visibleExamples = (data?.categories ?? []).filter(item => activeGroup === null || item.group_id === activeGroup);
  const awaitingPayment =
    !!order &&
    ["awaiting_payment", "pending_payment", "created"].includes(order.status);
  const finished = !!order && !awaitingPayment && !sendAnimating;
  const isFree = order?.is_free ?? preview?.is_free ?? false;
  const needsPackage = !!preview && !isFree && !order && (data?.purchased_sends_remaining ?? 0) === 0;
  const offerBeforeConsent = needsPackage && (data?.conversion_experiment?.inline_checkout ?? true);
  const unsuccessful =
    !!order && sendFeedback(order.status) === "rejected";
  const idempotencyKey = useRef("");
  const heading = useRef<HTMLHeadingElement>(null);
  const previousStage = useRef(`${step}:${awaitingPayment}:${finished}`);
  useEffect(() => {
    if (active && focusOnActivate) heading.current?.focus({ preventScroll: true });
  }, [active, focusOnActivate]);

  useEffect(() => {
    setAlternatives([]); setSelectedAlternative(null);
  }, [text, recipient, messageTone, step, data?.session_identity]);

  useEffect(() => {
    if (initialPreview || !data || order || chosenTone === messageTone) return;
    setMessageTone(messageTone); setPreview(null); setConsent(false); idempotencyKey.current = '';
  }, [data, chosenTone, messageTone, order?.id, initialPreview]);

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
          if (["free_credit_returned", "credit_returned", "wallet_returned"].includes(result.financial_status || "")) void reload();
        }
        if (!cancelled && isPending(result.status) && attempts < 20)
          timer = setTimeout(poll, 2000);
      } catch {
        // Retain the last confirmed outcome; history exposes refresh/errors.
      }
    }
    timer = setTimeout(poll, 1500);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [order?.id, order?.status]);

  function handleError(error: unknown) {
    if (onReplyUnavailable && error instanceof ApiError && error.code === 'reply_unavailable') {
      onReplyUnavailable(errorMessage(error));
      return;
    }
    setError(errorMessage(error));
    setAlternatives(messageAlternatives(error instanceof ApiError ? error.details : undefined));
    setSelectedAlternative(null);
    if (initialPreview) {
      if (error instanceof ApiError && ['authentication_required', 'credit_required', 'free_quota_changed'].includes(error.code)) void reload();
      return;
    }
    if (error instanceof ApiError && error.code === 'tone_unavailable') {
      setDraftStep(0); setPreview(null); setConsent(false); idempotencyKey.current = ''; void reload();
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
      setDraftStep(0);
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
    if (previewInFlight.current || busy) return;
    setError("");
    setFields({});
    const problem = draftProblem(text, category, data?.categories ?? [], freeformRewrite);
    if (problem) {
      setFields({ text: problem === "too_short"
        ? shortDraftMessage
        : isReply ? "بازبینی پاسخ موقتاً در دسترس نیست."
          : "بازنویسی متن دلخواه هنوز فعال نیست؛ فعلاً یکی از مثال‌های پیشنهادی رو انتخاب کن." });
      document.getElementById("message-text")?.focus();
      return;
    }
    if (isReply) {
      void makePreview();
      return;
    }
    setDraftStep(1);
    setPreview(null);
    setConsent(false);
    idempotencyKey.current = "";
  }

  function changeRecipient(raw: string) {
    const value = phoneInput(raw);
    if (normalizePhone(value) !== normalizePhone(recipient)) {
      setPreview(null);
      setAlternatives([]); setSelectedAlternative(null);
      setConsent(false);
      idempotencyKey.current = "";
    }
    setRecipient(value);
    setFields({});
    setError("");
  }

  async function makePreview(event?: React.FormEvent) {
    event?.preventDefault();
    if (previewInFlight.current || busy) return;
    setError("");
    setFields({});
    if (!data?.authenticated) { setError("اول شماره خودت رو تأیید کن."); return; }
    if (needsPhone && !validPhone(recipient)) {
      setFields({ recipient_phone: "شماره موبایل گیرنده را با ۰۹ و ۱۱ رقم وارد کن." });
      document.getElementById("quote-recipient")?.focus();
      return;
    }
    const alternative = alternatives.find(item => item.token === selectedAlternative);
    if (!alternative && text.trim().length < 3) {
      setFields({ text: shortDraftMessage });
      document.getElementById("message-text")?.focus();
      return;
    }
    previewInFlight.current = true;
    setBusy(true);
    setPreparingText(freeformRewrite && !alternative);
    try {
      const destination = sharedRecipient ? { share_token: sharedRecipient.token } : { recipient_phone: normalizePhone(recipient) };
      const result = await api<Preview>("/messages/preview", {
        method: "POST",
        body: isReply
          ? { reply_token: replyToken, text: text.trim(), source_mode: 'freeform', message_tone: messageTone }
          : alternative ? alternativeRequest(alternative, destination)
          : { category, text: text.trim(), ...destination,
              source_mode: freeformRewrite ? 'freeform' : 'suggestion', message_tone: messageTone },
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
    if (busy || orderInFlight.current) return;
    setError("");
    setFields({});
    if (needsPhone && !validPhone(recipient)) {
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
        "مهلت پیش‌نمایش تمام شده. به مرحلهٔ قبل برگرد و متن نهایی را دوباره آماده کن.",
      );
      return;
    }
    orderInFlight.current = true;
    setBusy(true);
    setSendAnimating(true);
    sendButton.current?.start();
    try {
      let currentOrder = order;
      if (!currentOrder) {
        if (!idempotencyKey.current)
          idempotencyKey.current = createIdempotencyKey();
        currentOrder = await api<Order>("/orders", {
          method: "POST",
          body: {
            preview_id: preview.preview_id,
            ...(needsPhone && { recipient_phone: normalizePhone(recipient) }),
            consent, terms_version: preview.terms_version,
          },
          idempotencyKey: idempotencyKey.current,
        });
        setOrder(currentOrder);
      }
      // Continue the same reviewed order on a retry, without another confirmation screen.
      if (["awaiting_payment", "pending_payment", "created"].includes(currentOrder.status))
        currentOrder = await payOrder(currentOrder);
      await sendButton.current?.settle(sendFeedback(currentOrder.status));
    } catch (error) {
      await sendButton.current?.settle("uncertain");
      handleError(error);
    } finally {
      orderInFlight.current = false;
      setSendAnimating(false);
      setBusy(false);
    }
  }

  async function payOrder(currentOrder: Order) {
    if (currentOrder.is_free || currentOrder.uses_purchased_credit) {
      const confirmed = await api<Order>(`/orders/${currentOrder.id}/${currentOrder.uses_purchased_credit ? "confirm-credit" : "confirm-free"}`, { method: "POST", body: {} });
      setOrder(confirmed);
      void reload();
      return confirmed;
    }
    throw new ApiError("روش خرید به بسته تغییر کرده؛ پیش‌نمایش تازه بساز.");
  }


  function goBack() {
    if (initialPreview) { onExit?.(); return; }
    setDraftStep(0);
    if (isReply) {
      setPreview(null);
      idempotencyKey.current = "";
    }
    setConsent(false);
    setError("");
    setFields({});
  }

  function editRejectedMessage() {
    setOrder(null);
    setPreview(null);
    idempotencyKey.current = '';
    goBack();
  }
  function renderActions(primary: ReactNode, disableBack = busy || !!order) {
    return (
      <div className="form-actions composer-actions" role="group" aria-label="ادامه یا بازگشت"
        onPointerDown={event => {
          // Keep the focused input and dock position stable until click submits.
          if (document.activeElement?.matches("input, textarea")) event.preventDefault();
        }}>
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
      data-update-blocked={busy || (!finished && !!(step > 0 || text || recipient || messageTone !== defaultTone))}
      id="compose"
      className={`compose-section wrap ${!data?.authenticated ? "composer-auth-only" : ""}`}
      data-screen={finished ? "receipt" : step}
      aria-labelledby="compose-title"
    >
      <h1 id="compose-title" className="sr-only" tabIndex={-1} ref={heading}>
        {finished ? "رسید پیامت" : !data?.authenticated ? "اول شماره خودت رو تأیید کن" : stepLabels[activeStep]}
      </h1>
      <div className="compose-layout">
        <div className="compose-panel">
          <div className="panel-top">
            <span>{isReply ? "پاسخ ناشناس" : isShared ? "پیام به صاحب لینک شخصی" : "یک پیام، یک فرصت برای حال بهتر"}</span>
            <span className="step-count">
              {new Intl.NumberFormat("fa-IR").format(activeStep + 1)} از ۲
            </span>
          </div>
          <ServiceState />
          <ErrorBox message={error} />
          {step === 1 && !preview && alternatives.length > 0 && <fieldset className="message-alternatives" disabled={busy}>
            <legend>پیشنهادهای مرتبط با پیامت</legend>
            <p className="small muted">اگر یکی از پیشنهادها منظورت را می‌رساند، انتخابش کن. پیش از ارسال متن کامل را می‌بینی.</p>
            {alternatives.map(item => <label className="message-alternative" key={item.id}>
              <input type="radio" name="message-alternative" checked={selectedAlternative === item.token} onChange={() => setSelectedAlternative(item.token)} />
              <span><strong>{item.label}</strong><span>{item.text}</span></span>
            </label>)}
            <button type="button" className="text-button" onClick={goBack}>ویرایش متن اولیه</button>
          </fieldset>}
          {step === 0 && !data?.authenticated && <AuthGate renderActions={renderActions} />}
          {step === 0 && data?.authenticated && (
            <form className="draft-form" onSubmit={advanceDraft} noValidate>
              <p className="muted form-intro">
                {isReply ? "پاسخت رو با کلمه‌های خودت بنویس."
                  : freeformRewrite
                  ? "منظورت رو با کلمه‌های خودت بنویس."
                  : "فعلاً می‌تونی از مثال‌های آماده استفاده کنی."}
              </p>
              <textarea
                id="message-text"
                aria-label="متن پیام"
                value={text}
                onChange={(event) => {
                  const value = event.target.value;
                  setText(value);
                  if (!isReply) setCategory(draftTopicHint(category, value, data.categories));
                  setFields({});
                  setError("");
                }}
                maxLength={280}
                rows={4}
                placeholder={isReply ? "پاسخت رو بنویس…"
                  : freeformRewrite
                  ? "مثلاً: می‌خوام قبل از قرض گرفتن وسایلم از خودم اجازه بگیره…"
                  : "برای شروع یکی از مثال‌های پایین رو انتخاب کن…"}
                aria-describedby={`message-hint message-count${fields.text ? " message-error" : ""}`}
                aria-invalid={!!fields.text}
                disabled={!data || busy}
              />
              <div className="textarea-meta message-input-meta">
                <p className="message-helper" id="message-hint">
                  {freeformRewrite
                    ? "اسم، نشانی یا اطلاعات خصوصی ننویس؛ پیش از تأیید، متن نهایی رو بخون."
                    : "شمارهٔ تماس، نشانی یا اطلاعات خصوصی کسی رو ننویس. دربارهٔ یک رفتار مشخص حرف بزن، نه شخصیت آدم‌ها."}
                </p>
                <span id="message-count">
                  {new Intl.NumberFormat("fa-IR").format(text.length)} / ۲۸۰
                </span>
              </div>
              {isReply && toneOptions.length > 1 && <MessageTonePicker options={toneOptions} value={messageTone} disabled={busy || !!order} onChange={tone => {
                setMessageTone(tone); setPreview(null); setConsent(false); setFields({}); setError(''); idempotencyKey.current = '';
              }} />}
              {fields.text && (
                <p className="field-error" id="message-error">
                  {fields.text}
                </p>
              )}
              {!isReply && data.categories.length > 0 && <fieldset className="category-fieldset suggested-topics">
                <legend className="sr-only">مثال‌های پیشنهادی برای شروع</legend>
                {!!data.category_groups?.length && <ExampleFilters groups={data.category_groups} value={activeGroup} onChange={setExampleGroup} />}
                <div className="category-grid" id="message-categories">
                  {visibleExamples.map((item) => (
                    <button
                      data-category={item.id}
                      className={`category-card ${category === item.id && text === item.example ? "selected" : ""}`}
                      key={item.key ?? item.id}
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        setCategory(item.id);
                        setText(item.example);
                        setFields({});
                        setError("");
                        document.getElementById("message-text")?.focus();
                      }}
                      aria-pressed={category === item.id && text === item.example}
                    >
                      <Icon name={categoryIcons[item.id] || "chat"} />
                      <span>{item.label}</span>
                      {category === item.id && text === item.example && (
                        <span className="category-check">
                          <Icon name="check" size={11} />
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </fieldset>}
              {renderActions(
                <BusyButton
                  busy={busy}
                  className="button primary composer-next"
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
              {initialPreview ? <p className="shared-destination" role="note">
                {isReply ? "مقصد همان گیرندهٔ پاسخ است." : isShared ? "مقصد همان صاحب لینک شخصی است." :
                  <>گیرندهٔ همین پیام <bdi dir="ltr">{trialRecipient ?? initialPreview.recipient_masked}</bdi></>}
                {" "}پیش از ارسال، متن و گیرنده را بررسی کن.
              </p> : sharedRecipient ? <div className="shared-destination">
                <label htmlFor="quote-recipient">شمارهٔ مقصد</label>
                <input id="quote-recipient" className="phone-number-input" dir="ltr" type="text" readOnly
                  autoComplete="off" value={sharedRecipient.maskedPhone} aria-describedby="shared-destination-help" />
                <p id="shared-destination-help" className="small muted">مقصد از لینک شخصی انتخاب شده و شماره به‌صورت پوشیده نمایش داده می‌شه.</p>
              </div> : !isReply && (
                <RecipientPhoneField value={recipient} onChange={changeRecipient} active={active}
                  disabled={busy} readOnly={!!order} error={fields.recipient_phone} />
              )}
              {preview ? <>
              <div className="final-message">
                <div className="final-message-header">
                  <Icon name="leaf" size={19} />
                  <span>{isReply ? "متن پاسخ پیش از ارسال" : isShared ? "متن پیامک پیش از ارسال" : "متن کامل پیامک؛ همین متن ارسال می‌شه"}</span>
                </div>
                <p>{preview.full_sms || preview.rewritten_text}</p>
                <div className="final-message-footer">
                  <Icon name="shield" size={15} /> {isReply || isShared ? "نشانی لینک‌های گیرنده فقط در پیامک دیده می‌شه." : "بگم نگم اطلاعات حسابت رو به پیامک اضافه نمی‌کنه."}
                </div>
              </div>
              <div className="preview-info">
                <span>
                  <Icon name="sparkle" size={17} />
                  {preview.moderation_mode === "gapgpt" || preview.moderation_mode === "ollama" ? "متن بازنویسی و بررسی‌شده" : "متن آمادهٔ بررسی‌شده"}
                </span>
                <span>
                  مصرف: <b>{isFree ? "ارسال رایگان" : "یک اعتبار از بسته"}</b> · {preview.sms_segments ? new Intl.NumberFormat("fa-IR").format(preview.sms_segments) : "—"} بخش پیامک
                </span>
              </div>
              {(preview.sms_segments ?? 0) > 3 && <p className="small muted" role="note">این متن بیش از ۳ بخش پیامک می‌شود. می‌تونی همین متن رو تأیید کنی یا قبل از ارسال کوتاهش کنی.</p>}
              {!offerBeforeConsent && <label className="checkbox-label" htmlFor="respect-consent">
                <input id="respect-consent" type="checkbox" checked={consent}
                  disabled={busy || !!order}
                  onChange={event => setConsent(event.target.checked)}
                  aria-invalid={!!fields.consent}
                  aria-describedby={fields.consent ? "consent-error" : undefined} />
                <span>
                  {isReply
                    ? "متن نهایی رو خوندم و منظورم رو می‌رسونه. پاسخ رو با احترام و بدون تحقیر، تهدید یا مزاحمت می‌فرستم."
                    : isShared ? "متن نهایی رو خوندم. این پیام رو برای صاحب لینک و بدون تحقیر، تهدید یا مزاحمت می‌فرستم."
                      : "متن نهایی رو خوندم و منظورم رو می‌رسونه. این فرد رو می‌شناسم؛ هدفم کمک و یادآوریه، نه تحقیر، تهدید یا مزاحمت."}
                  {" "}<TermsDialog /> رو می‌پذیرم.
                </span>
              </label>}
              {fields.consent && <p className="field-error" id="consent-error">{fields.consent}</p>}
              {needsPackage && <CreditPackages inline previewId={preview.preview_id} preservePreview={!!trialRecipient} />}
              {awaitingPayment && (
                <p className="small muted" role="status">سفارش ثبت شده؛ تلاش دوباره همین سفارش رو ادامه می‌ده.</p>
              )}
              {data?.authenticated && renderActions(
                !offerBeforeConsent && <PaperDartButton ref={sendButton} type="submit" className="button primary composer-next"
                  disabled={busy || !data?.authenticated || (!isFree && !order && (data.purchased_sends_remaining ?? 0) === 0)}>
                  {isFree ? (awaitingPayment ? "تلاش دوباره برای ارسال رایگان" : data?.demo_mode ? "ارسال رایگان آزمایشی" : "تأیید و ارسال رایگان") : !order && (data?.purchased_sends_remaining ?? 0) === 0 ? "ابتدا بستهٔ پیام بخر" : awaitingPayment ? "تلاش دوباره برای ارسال" : "تأیید و ارسال با یک اعتبار"}
                  <Icon name="arrow" size={18} />
                </PaperDartButton>,
              )}
              </> : <>
                <div className="review-placeholder" role="note">
                  <Icon name="chat" size={24} />
                  <p>{alternatives.length > 0 ? "یکی از پیشنهادهای بالا را انتخاب کن تا پیش‌نمایش آن را ببینی." : isShared ? "متن نهایی رو آماده کن و پیش از ارسال مرورش کن." : freeformRewrite ? "شماره رو وارد کن تا متن نهایی آماده بشه. قبل از ارسال، متن کامل پیامک رو می‌بینی." : "شماره رو وارد کن تا متن نهایی آماده بشه. هر ارسال یک اعتبار مصرف می‌کنه."}</p>
                </div>
                {data?.authenticated && renderActions(
                  <BusyButton type="submit" className="button primary composer-next" busy={busy} disabled={!data?.authenticated || (alternatives.length > 0 && !selectedAlternative)}>
                    {selectedAlternative ? 'پیش‌نمایش پیشنهاد انتخاب‌شده' : alternatives.length > 0 ? 'یک پیشنهاد را انتخاب کن' : 'آماده‌سازی متن'} <Icon name="arrow" size={18} />
                  </BusyButton>,
                )}
              </>}
            </form>
          )}

          {finished && order && (
            <div className="receipt-panel compact-receipt">
              <div
                className={`receipt-icon ${sendFeedback(order.status) === "accepted" ? "has-succeeded" : unsuccessful ? "has-failed" : "is-uncertain"}`}
              >
                <Icon
                  name={
                    sendFeedback(order.status) === "accepted"
                      ? "shield"
                      : unsuccessful
                        ? "info"
                        : "clock"
                  }
                  size={32}
                />
              </div>
              <h2 className="form-heading" tabIndex={-1}>
                {unsuccessful ? "ارسال پیام انجام نشد." : sendFeedback(order.status) !== "accepted"
                  ? "نتیجهٔ ارسال در حال بررسی است؛ دوباره ارسال نکن."
                  : data?.demo_mode ? "درخواست آزمایشی ثبت شد."
                  : "پیام شما با موفقیت در صف ارسال قرار گرفت."}
              </h2>
              <DeliveryReason order={order} />
              {order.status_reason?.code === 'moderation_rejected' && <button type="button" className="button secondary" onClick={editRejectedMessage}>ویرایش و آماده‌سازی دوباره</button>}
              <Link className="button primary composer-next" href="/history">پیام‌های من</Link>
            </div>
          )}
        </div>
      </div>
      <p className="compose-bottom">
        <Icon name="lock" size={16} /> شماره‌ات پنهونه؛ فقط با درخواست گیرنده و تأیید خودت در پروفایل، برای همون فرد دیده می‌شه. سرویس برای جلوگیری از سوءاستفاده، فرستنده رو شناسایی می‌کنه.
      </p>
      {preparingText && <RewriteLoading />}
    </section>
  );
}
