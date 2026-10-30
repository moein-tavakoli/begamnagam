"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import { latinDigits, normalizePhone, phoneInput, validPhone } from "@/lib/format";
import { listenForSmsCode, validOtpCode } from "@/lib/otp-autofill";
import { useApp } from "./app-provider";
import { BusyButton, ErrorBox } from "./feedback";
import { Icon } from "./icons";
import { OtpCodeInput, type OtpPhase } from "./otp-code-input";

export function AuthGate({
  purpose = "برای ادامه، شماره خودت را تأیید کن.",
  forceReverify = false,
  renderActions,
}: {
  purpose?: string;
  forceReverify?: boolean;
  renderActions?: (primary: ReactNode, busy: boolean) => ReactNode;
}) {
  const { data, verifyOtp } = useApp();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [challenge, setChallenge] = useState("");
  const [debugCode, setDebugCode] = useState("");
  const [deliveryStatus, setDeliveryStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [otpPhase, setOtpPhase] = useState<OtpPhase>("idle");
  const mounted = useRef(true);
  const otpForm = useRef<HTMLFormElement>(null);
  const verificationInFlight = useRef(false);
  const lastAutoAttempt = useRef("");
  const stopAutofill = useRef<() => void>(() => {});
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; stopAutofill.current(); };
  }, []);
  useEffect(() => {
    if (!validOtpCode(latinDigits(code))) { lastAutoAttempt.current = ""; return; }
    if (!challenge || busy || verificationInFlight.current || (data?.authenticated && !forceReverify)) return;
    const attempt = `${challenge}:${latinDigits(code)}`;
    if (lastAutoAttempt.current === attempt || !otpForm.current?.getClientRects().length) return;
    lastAutoAttempt.current = attempt;
    otpForm.current.requestSubmit();
  }, [code, challenge, busy, data?.authenticated, forceReverify]);
  const actionRow = (primary: ReactNode) => renderActions ? renderActions(primary, busy) : primary;
  if (data?.authenticated && !forceReverify) return null;

  async function requestCode(event: React.FormEvent) {
    event.preventDefault();
    if (busy || verificationInFlight.current) return;
    setError("");
    if (!validPhone(phone)) {
      setFieldError(
        "یک شماره موبایل معتبر ایران وارد کنید؛ مانند ۰۹۱۲۳۴۵۶۷۸۹.",
      );
      document.getElementById("sender-phone")?.focus();
      return;
    }
    setFieldError("");
    setBusy(true);
    stopAutofill.current();
    setCode("");
    lastAutoAttempt.current = "";
    setOtpPhase("idle");
    // Listen before requesting the SMS, including fast provider responses.
    stopAutofill.current = listenForSmsCode(setCode);
    try {
      const result = await api<{ challenge_id: string; debug_code?: string; delivery_status?: string }>(
        "/auth/request-otp",
        { method: "POST", body: { phone: normalizePhone(phone) } },
      );
      setChallenge(result.challenge_id);
      setDebugCode(result.debug_code || "");
      setDeliveryStatus(result.delivery_status || "");
      window.setTimeout(() => document.getElementById("otp-code")?.focus(), 0);
    } catch (error) {
      stopAutofill.current();
      setCode("");
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function verify(event: React.FormEvent) {
    event.preventDefault();
    if (busy || verificationInFlight.current) return;
    setError("");
    setFieldError("");
    if (!validOtpCode(latinDigits(code))) {
      setFieldError("کد تأیید باید ۴ رقم باشد.");
      document.getElementById("otp-code")?.focus();
      return;
    }
    stopAutofill.current();
    verificationInFlight.current = true;
    lastAutoAttempt.current = `${challenge}:${latinDigits(code)}`;
    setBusy(true);
    setOtpPhase("verifying");
    const started = performance.now();
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    try {
      await verifyOtp(challenge, latinDigits(code), async result => {
          if (!result.authenticated || !mounted.current) return;
          // Only the server verdict permits the success animation.
          if (!reduceMotion) await new Promise(resolve => window.setTimeout(resolve, Math.max(0, 1200 - (performance.now() - started))));
          if (!mounted.current) return;
          setOtpPhase("success");
          if (!reduceMotion) await new Promise(resolve => window.setTimeout(resolve, 1450));
      });
      if (!mounted.current) return;
      window.setTimeout(
        () => document.querySelector<HTMLElement>(".header-phone")?.focus({ preventScroll: true }),
        0,
      );
    } catch (error) {
      if (!mounted.current) return;
      setOtpPhase("error");
      setError(errorMessage(error));
      if (
        error instanceof ApiError &&
        ["otp_expired", "challenge_expired", "session_unconfirmed"].includes(error.code)
      ) {
        setChallenge("");
        setCode("");
      }
    } finally {
      verificationInFlight.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  const content = (
    <>
      <div className="auth-title">
        <Icon name="lock" size={20} />
        <h3>{purpose}</h3>
      </div>
      <ErrorBox message={error} />
      {data?.otp_is_real && data.demo_mode && (
        <p className="muted small" role="status">
          پرداخت و ارسال پیام به گیرنده در این محیط آزمایشی‌اند.
        </p>
      )}
      {!challenge ? (
        <form className={`phone-entry-form${renderActions ? " embedded-auth-form" : ""}`} onSubmit={requestCode} noValidate>
          <label htmlFor="sender-phone">شماره موبایل خودت</label>
          <div className="inline-form">
            <input
              id="sender-phone"
              className="phone-number-input"
              name="tel"
              type="tel"
              inputMode="numeric"
              autoComplete="tel-national"
              maxLength={11}
              minLength={11}
              pattern="09[0-9]{9}"
              dir="ltr"
              placeholder="09123456789"
              value={phone}
              onChange={(e) => setPhone(phoneInput(e.target.value))}
              onPaste={event => {
                const input = event.currentTarget;
                // Normalize a complete pasted number before the native character
                // limit can truncate spaces or an international country prefix.
                if(input.selectionStart === 0 && input.selectionEnd === input.value.length){
                  event.preventDefault();
                  setPhone(phoneInput(event.clipboardData.getData("text")));
                }
              }}
              aria-invalid={!!fieldError}
              aria-describedby={fieldError ? "auth-field-error" : undefined}
            />
            {actionRow(<BusyButton
              className="button secondary"
              busy={busy}
              disabled={!data}
            >
              دریافت کد تأیید
            </BusyButton>)}
          </div>
          {fieldError && (
            <p className="field-error" id="auth-field-error">
              {fieldError}
            </p>
          )}
        </form>
      ) : (
        <form ref={otpForm} className={renderActions ? "embedded-auth-form" : undefined} onSubmit={verify} noValidate data-update-blocked="true">
          <label htmlFor="otp-code">
            کد تأیید شماره <bdi>{normalizePhone(phone)}</bdi>
          </label>
          <p className="muted small" id="otp-code-help">
            کد پیامک را وارد کن؛ با کامل‌شدن ۴ رقم، تأیید خودکار شروع می‌شود.
          </p>
          {deliveryStatus === "unknown" && (
            <p className="muted small" role="status">
              نتیجهٔ ارسال کد هنوز مشخص نیست. اگر پیامک رسید، کد را وارد کن؛ ارسال خودکار تکرار نمی‌شود.
            </p>
          )}
          {data?.demo_mode && debugCode && (
            <p className="demo-code">
              کد ورود آزمایشی: <strong dir="ltr">{debugCode}</strong> — پیامک
              واقعی ارسال نشده است.
            </p>
          )}
          <div className="inline-form otp-entry-row">
            <OtpCodeInput
              value={code}
              phase={otpPhase}
              invalid={!!fieldError}
              onChange={value => {
                stopAutofill.current();
                setCode(value);
                setOtpPhase("idle");
                setFieldError("");
                setError("");
              }}
            />
            {actionRow(<BusyButton className="button secondary" busy={busy}>
              تأیید و ادامه
            </BusyButton>)}
          </div>
          {fieldError && (
            <p className="field-error" id="auth-field-error">
              {fieldError}
            </p>
          )}
          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={() => {
              stopAutofill.current();
              setChallenge("");
              setCode("");
              setOtpPhase("idle");
              setFieldError("");
              setError("");
            }}
          >
            اصلاح شماره یا درخواست کد جدید
          </button>
        </form>
      )}
    </>
  );
  return renderActions ? content : <div className="auth-card">{content}</div>;
}
