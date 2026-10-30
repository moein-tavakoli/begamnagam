"use client";

import { useLayoutEffect, useRef, type InputHTMLAttributes } from "react";
import { latinDigits } from "@/lib/format";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { type?: "number" | "date" };

export function DigitInput({ type = "number", min, max, step = 1, required, value, defaultValue, onChange, onBlur, ...props }: Props) {
  const ref = useRef<HTMLInputElement>(null);
  function normalize(input: HTMLInputElement) {
    const original = input.value;
    const convert = (text: string) => type === "number"
      ? latinDigits(text).replace(/[\s,٬]/g, "").replace(/٫/g, ".")
      : latinDigits(text).replace(/\//g, "-").trim();
    const next = convert(original);
    if (next !== original) {
      const start = input.selectionStart, end = input.selectionEnd;
      input.value = next;
      if (start !== null && end !== null) input.setSelectionRange(convert(original.slice(0, start)).length, convert(original.slice(0, end)).length);
    }
    // The native numeric/date validator still enforces ranges and steps. A text
    // editor is needed because number inputs discard Persian input before React.
    const probe = document.createElement("input");
    probe.type = type;
    probe.required = !!required;
    probe.defaultValue = input.defaultValue;
    if (min !== undefined) probe.min = String(min);
    if (max !== undefined) probe.max = String(max);
    probe.step = String(step);
    probe.value = next;
    const validity = probe.validity;
    const number = (bound: string | number) => new Intl.NumberFormat("fa-IR").format(Number(bound));
    let message = "";
    if (!next && required) message = "این مقدار را وارد کن.";
    else if (next && !probe.value) message = type === "date" ? "تاریخ معتبر را به شکل سال-ماه-روز وارد کن." : "عدد معتبر وارد کن.";
    else if (validity.rangeUnderflow && min !== undefined) message = type === "date" ? "تاریخ از حداقل مجاز کمتر است." : `مقدار باید حداقل ${number(min)} باشد.`;
    else if (validity.rangeOverflow && max !== undefined) message = type === "date" ? "تاریخ از حداکثر مجاز بیشتر است." : `مقدار باید حداکثر ${number(max)} باشد.`;
    else if (validity.stepMismatch) message = step === 1 ? "عدد صحیح وارد کن." : "مقدار با گام مجاز هماهنگ نیست.";
    input.setCustomValidity(message);
  }

  useLayoutEffect(() => {
    const input = ref.current;
    if (!input) return;
    normalize(input);
    const reset = () => queueMicrotask(() => { if (input.isConnected) normalize(input); });
    const form = input.form;
    form?.addEventListener("reset", reset);
    return () => form?.removeEventListener("reset", reset);
  }, [type, min, max, step, required, value, defaultValue]);

  return <input {...props} ref={ref} type="text" inputMode={type === "number" && step !== 1 ? "decimal" : "numeric"}
    data-number-input={type === "number" ? "" : undefined} data-date-input={type === "date" ? "" : undefined}
    dir={props.dir ?? "ltr"} min={min} max={max} step={step} required={required}
    value={value === undefined ? undefined : latinDigits(String(value))}
    defaultValue={defaultValue === undefined ? undefined : latinDigits(String(defaultValue))}
    onChange={event => { normalize(event.currentTarget); onChange?.(event); }}
    onBlur={event => { normalize(event.currentTarget); onBlur?.(event); }} />;
}
