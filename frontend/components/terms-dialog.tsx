"use client";

import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { PrivacyContent } from "./privacy-content";
import styles from "./terms-dialog.module.css";

export function TermsDialog() {
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const titleId = `${id}-title`;
  const descriptionId = `${id}-description`;

  useEffect(() => {
    if (!open || !dialog.current) return;
    if (!dialog.current.open) dialog.current.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  function close() {
    dialog.current?.close();
  }

  return (
    <>
      <button
        ref={trigger}
        type="button"
        className={styles.trigger}
        aria-haspopup="dialog"
        aria-controls={id}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setOpen(true);
        }}
      >
        قوانین استفاده
      </button>
      {open && createPortal(
        <dialog
          ref={dialog}
          id={id}
          className={styles.dialog}
          aria-labelledby={titleId}
          aria-describedby={descriptionId}
          dir="rtl"
          onClose={() => {
            setOpen(false);
            trigger.current?.focus({ preventScroll: true });
          }}
          onClick={(event) => {
            event.stopPropagation();
            if (event.target === event.currentTarget) close();
          }}
        >
          <div className={styles.header}>
            <h2 id={titleId}>قوانین استفاده و حریم خصوصی</h2>
            <button type="button" className={styles.close} onClick={close}>
              بستن
            </button>
          </div>
          <div className={styles.content}>
            <p id={descriptionId} className={styles.introduction}>
              پیش از تأیید ارسال، متن نهایی و این شرایط رو بررسی کن. شمارهٔ
              فرستنده برای گیرنده نمایش داده نمی‌شه؛ ارسال مسئولانه وظیفهٔ فرستنده است.
            </p>
            <PrivacyContent headingLevel={3} newTab />
          </div>
        </dialog>,
        document.body,
      )}
    </>
  );
}
