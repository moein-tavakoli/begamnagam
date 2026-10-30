"use client";

import { useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { latinDigits } from "@/lib/format";
import { OTP_LENGTH } from "@/lib/otp-autofill";
import styles from "./otp-code-input.module.css";

export type OtpPhase = "idle" | "verifying" | "success" | "error";

const positions = Array.from({ length: OTP_LENGTH }, (_, index) => {
  const angle = (index * 360 / OTP_LENGTH - 90) * Math.PI / 180;
  return {
    "--row": index - (OTP_LENGTH - 1) / 2,
    "--orbit-x": Math.cos(angle).toFixed(4),
    "--orbit-y": Math.sin(angle).toFixed(4),
  } as CSSProperties;
});

export function OtpCodeInput({
  value,
  onChange,
  phase,
  invalid,
}: {
  value: string;
  onChange: (value: string) => void;
  phase: OtpPhase;
  invalid: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(false);
  const [cursor, setCursor] = useState(0);
  const locked = phase === "verifying" || phase === "success";

  function selectSlot(event: PointerEvent<HTMLInputElement>) {
    if (locked) return;
    event.preventDefault();
    const bounds = event.currentTarget.getBoundingClientRect();
    const index = Math.min(value.length, OTP_LENGTH - 1, Math.max(0,
      Math.floor((event.clientX - bounds.left) / (bounds.width / OTP_LENGTH))));
    input.current?.focus({ preventScroll: true });
    input.current?.setSelectionRange(index, Math.min(index + 1, value.length));
    setCursor(index);
  }

  return (
    <div className={styles.field}>
      <div className={styles.stage} style={{ "--slot-count": OTP_LENGTH } as CSSProperties} data-phase={phase} data-invalid={invalid || undefined}>
        <div className={styles.visuals} aria-hidden="true">
          <svg className={styles.orbit} viewBox="0 0 160 160" fill="none">
            <circle cx="80" cy="80" r="77" />
          </svg>
          <span className={styles.hub} />
          <div className={styles.rotor}>
            {positions.map((position, index) => (
              <span
                key={index}
                className={styles.slot}
                style={position}
                data-active={focused && !locked && cursor === index || undefined}
                data-filled={!!value[index] || undefined}
              >
                <svg className={styles.focusTrack} fill="none" focusable="false">
                  <rect className={styles.focusLine} x="3%" y="3%" width="94%" height="94%" rx="22%" pathLength="100" />
                </svg>
                {value[index] && <span key={value[index]} className={styles.digit}>{value[index]}</span>}
                {!value[index] && <span className={styles.caret} />}
              </span>
            ))}
          </div>
          <div className={styles.celebration}>
            {Array.from({ length: 12 }, (_, index) => (
              <i key={index} className={styles.spark} style={{ "--angle": `${index * 30}deg`, "--distance": `${54 + index % 3 * 13}px` } as CSSProperties} />
            ))}
            <span className={styles.badge}>
              <svg viewBox="0 0 32 32" fill="none"><path d="m9 16 5 5 10-11" /></svg>
            </span>
          </div>
        </div>
        <input
          ref={input}
          className={styles.capture}
          id="otp-code"
          name="otp"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          autoCapitalize="off"
          spellCheck={false}
          pattern={`[0-9]{${OTP_LENGTH}}`}
          maxLength={OTP_LENGTH}
          dir="ltr"
          value={value}
          readOnly={locked}
          aria-invalid={invalid || phase === "error"}
          aria-describedby={`otp-code-help${invalid ? " auth-field-error" : ""}`}
          onChange={event => {
            const next = latinDigits(event.target.value).replace(/\D/g, "").slice(0, OTP_LENGTH);
            setCursor(Math.min(event.target.selectionStart ?? next.length, OTP_LENGTH - 1));
            onChange(next);
          }}
          onPaste={event => {
            if (locked) return;
            const pasted = latinDigits(event.clipboardData.getData("text")).replace(/\D/g, "").slice(0, OTP_LENGTH);
            event.preventDefault();
            if (!pasted) return;
            const start = input.current?.selectionStart ?? value.length;
            const end = input.current?.selectionEnd ?? start;
            const next = pasted.length === OTP_LENGTH ? pasted : (value.slice(0, start) + pasted + value.slice(end)).slice(0, OTP_LENGTH);
            onChange(next);
            const position = pasted.length === OTP_LENGTH ? OTP_LENGTH : Math.min(start + pasted.length, OTP_LENGTH);
            setCursor(Math.min(position, OTP_LENGTH - 1));
            requestAnimationFrame(() => input.current?.setSelectionRange(position, position));
          }}
          onFocus={() => { setFocused(true); setCursor(Math.min(input.current?.selectionStart ?? value.length, OTP_LENGTH - 1)); }}
          onBlur={() => setFocused(false)}
          onSelect={event => setCursor(Math.min(event.currentTarget.selectionStart ?? value.length, OTP_LENGTH - 1))}
          onPointerDown={selectSlot}
        />
        <p className={styles.status} role="status" aria-live="polite" aria-atomic="true">
          {phase === "verifying" ? "در حال بررسی کد…" : phase === "success" ? "شماره تأیید شد" : ""}
        </p>
      </div>
    </div>
  );
}
