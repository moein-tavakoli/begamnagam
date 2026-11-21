"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import styles from "./rewrite-loading.module.css";

export function RewriteStatus({ id, className }: { id?: string; className?: string }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setSlow(true), 8_000);
    return () => window.clearTimeout(timer);
  }, []);

  return <p id={id} className={className} role="status" aria-atomic="true">
    {slow ? "هنوز منتظر پیش‌نمایش هستیم. متنت در این صفحه می‌ماند و نیازی به درخواست دوباره نیست."
      : "پس از بررسی متن، پیش‌نمایش را همین‌جا می‌بینی."}
  </p>;
}

export function RewriteLoading() {
  const dialog = useRef<HTMLDialogElement>(null);
  const id = useId();

  useLayoutEffect(() => {
    const element = dialog.current;
    if (!element) return;
    const previousOverflow = document.body.style.overflow;
    element.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      element.close();
      document.body.style.overflow = previousOverflow;
      // The prepare button is disabled while waiting and may disappear on
      // success. ErrorBox focuses any failure in its subsequent effect.
      document.getElementById("compose-title")?.focus({ preventScroll: true });
    };
  }, []);

  return (
    <dialog ref={dialog} className={styles.dialog} dir="rtl"
      aria-labelledby={`${id}-title`} aria-describedby={`${id}-description`}
      onCancel={event => event.preventDefault()}>
      <div className={styles.symbol} aria-hidden="true">
        <span className={styles.spinner} />
        <Icon name="chat" size={25} />
      </div>
      <h2 id={`${id}-title`} tabIndex={-1} autoFocus>در حال آماده‌سازی متن…</h2>
      <RewriteStatus id={`${id}-description`} />
    </dialog>
  );
}
