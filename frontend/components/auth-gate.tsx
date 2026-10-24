"use client";

import { useRef, useState } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import { latinDigits, normalizePhone, validPhone } from "@/lib/format";
import { useApp } from "./app-provider";
import { BusyButton, ErrorBox } from "./feedback";
import { Icon } from "./icons";

export function AuthGate({
  purpose = "برای ادامه، شماره خودت را تأیید کن.",
}: {
  purpose?: string;
}) {
  const { data, authenticate } = useApp();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [challenge, setChallenge] = useState("");
  const [debugCode, setDebugCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const confirmation = useRef<HTMLDivElement>(null);
  if (data?.authenticated)
    return (
      <div
        className="auth-confirmed"
        ref={confirmation}
        tabIndex={-1}
        role="status"
      >
        <Icon name="shield" size={20} />
        <span>
          شماره شما تأیید شده: <bdi>{data.phone_masked}</bdi>
        </span>
      </div>
    );

  async function requestCode(event: React.FormEvent) {
    event.preventDefault();
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
    try {
      const result = await api<{ challenge_id: string; debug_code?: string }>(
        "/auth/request-otp",
        { method: "POST", body: { phone: normalizePhone(phone) } },
      );
      setChallenge(result.challenge_id);
      setDebugCode(result.debug_code || "");
      window.setTimeout(() => document.getElementById("otp-code")?.focus(), 0);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function verify(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setFieldError("");
    if (!/^\d{6}$/.test(latinDigits(code))) {
      setFieldError("کد تأیید باید ۶ رقم باشد.");
      document.getElementById("otp-code")?.focus();
      return;
    }
    setBusy(true);
    try {
      const result = await api<{
        authenticated: boolean;
        phone_masked: string;
      }>("/auth/verify-otp", {
        method: "POST",
        body: { challenge_id: challenge, code: latinDigits(code) },
      });
      authenticate(result.phone_masked);
      window.setTimeout(
        () => confirmation.current?.focus({ preventScroll: true }),
        0,
      );
    } catch (error) {
      setError(errorMessage(error));
      if (
        error instanceof ApiError &&
        ["otp_expired", "challenge_expired"].includes(error.code)
      ) {
        setChallenge("");
        setCode("");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-card">
      <div className="auth-title">
        <Icon name="lock" size={20} />
        <h3>{purpose}</h3>
      </div>
      <p className="muted small">
        شماره شما به گیرنده نمایش داده نمی‌شود. تأیید شماره برای جلوگیری از
        سوءاستفاده است.
      </p>
      <ErrorBox message={error} />
      {!challenge ? (
        <form onSubmit={requestCode} noValidate>
          <label htmlFor="sender-phone">شماره موبایل خودت</label>
          <div className="inline-form">
            <input
              id="sender-phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              dir="ltr"
              placeholder="0912 345 6789"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              aria-invalid={!!fieldError}
              aria-describedby={fieldError ? "auth-field-error" : undefined}
            />
            <BusyButton
              className="button secondary"
              busy={busy}
              disabled={!data}
            >
              دریافت کد تأیید
            </BusyButton>
          </div>
          {fieldError && (
            <p className="field-error" id="auth-field-error">
              {fieldError}
            </p>
          )}
        </form>
      ) : (
        <form onSubmit={verify} noValidate>
          <label htmlFor="otp-code">
            کد تأیید شماره <bdi>{normalizePhone(phone)}</bdi>
          </label>
          {data?.demo_mode && debugCode && (
            <p className="demo-code">
              کد ورود آزمایشی: <strong dir="ltr">{debugCode}</strong> — پیامک
              واقعی ارسال نشده است.
            </p>
          )}
          <div className="inline-form">
            <input
              id="otp-code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              dir="ltr"
              placeholder="------"
              value={code}
              onChange={(e) => setCode(latinDigits(e.target.value))}
              aria-invalid={!!fieldError}
              aria-describedby={fieldError ? "auth-field-error" : undefined}
            />
            <BusyButton className="button secondary" busy={busy}>
              تأیید و ادامه
            </BusyButton>
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
              setChallenge("");
              setCode("");
              setFieldError("");
              setError("");
            }}
          >
            اصلاح شماره یا درخواست کد جدید
          </button>
        </form>
      )}
    </div>
  );
}
