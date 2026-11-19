"use client";

import Link from "next/link";
import { QRCodeCanvas } from "qrcode.react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { useApp } from "./app-provider";
import { AuthGate } from "./auth-gate";
import { BusyButton, ErrorBox, ServiceState } from "./feedback";
import { Icon } from "./icons";
import styles from "./personal-share.module.css";

const shareIntro = "اگه حرفی هست که دوست داری بهم بگی، از بگم نگم برام پیام بفرست.";
type LinkState = { url: string | null; paused?: boolean };

function downloadStory(qr: HTMLCanvasElement) {
  const canvas = document.createElement("canvas");
  canvas.width = 1080;
  canvas.height = 1920;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas is unavailable");

  ctx.fillStyle = "#fff5e6";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#412b26";
  ctx.direction = "rtl";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = "700 84px Vazirmatn, sans-serif";
  ctx.fillText("بگم نگم", 540, 427);
  ctx.font = "600 58px Vazirmatn, sans-serif";
  ctx.fillText("از اینجا برام پیام بفرست", 540, 566, 880);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(qr, 180, 680, 720, 720);
  ctx.font = "500 45px Vazirmatn, sans-serif";
  ctx.fillText("کد رو اسکن کن و حرفت رو بنویس", 540, 1530, 880);

  const download = document.createElement("a");
  download.download = "begamnagam-story.png";
  download.href = canvas.toDataURL("image/png");
  document.body.append(download);
  download.click();
  download.remove();
}

export function PersonalShare() {
  const { data } = useApp();
  const [link, setLink] = useState<LinkState>();
  const url = link?.url;
  const [busy, setBusy] = useState(false);
  const [confirmDisable, setConfirmDisable] = useState(false);
  const [canShare, setCanShare] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const linkField = useRef<HTMLInputElement>(null);
  const textField = useRef<HTMLTextAreaElement>(null);
  const qr = useRef<HTMLCanvasElement>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setError("");
    try {
      const result = await api<LinkState>("/personal-share", { signal });
      if (!signal?.aborted) setLink(result);
    } catch (err) {
      if (!signal?.aborted) setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    setCanShare(typeof navigator.share === "function");
  }, []);

  useEffect(() => {
    if (!data?.authenticated) return;
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [data?.authenticated, load]);

  async function changeLink(method: "POST" | "DELETE") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api<LinkState>("/personal-share", { method, body: {} });
      setLink(result);
      setConfirmDisable(false);
      setNotice(result.url ? "لینک شخصی آماده است." : "لینک و QR قبلی غیرفعال شدند.");
      requestAnimationFrame(() => (result.url ? linkField.current : document.getElementById("make-personal-share"))?.focus());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function copy(field: HTMLInputElement | HTMLTextAreaElement | null, message: string) {
    if (!field) return;
    try {
      await navigator.clipboard.writeText(field.value);
      setNotice(message);
    } catch {
      field.focus();
      field.select();
      setNotice("متن انتخاب شد. از منوی گوشی یا صفحه‌کلید آن را کپی کن.");
    }
  }

  async function share() {
    if (!url) return;
    setNotice("");
    try {
      await navigator.share({ title: "لینک شخصی بگم نگم", text: shareIntro, url });
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        setNotice("اشتراک مستقیم در دسترس نیست. می‌تونی لینک یا متن آماده رو کپی کنی.");
      }
    }
  }

  function saveStory() {
    if (!qr.current) return;
    try {
      downloadStory(qr.current);
      setNotice("تصویر برای دانلود آماده شد.");
    } catch {
      setNotice("دانلود تصویر انجام نشد. می‌تونی از QR نمایش‌داده‌شده عکس بگیری.");
    }
  }

  return (
    <div className={`account-page wrap ${styles.page}`} data-update-blocked={busy}>
      <div className="account-heading">
        <Link href="/profile" className={styles.back}>بازگشت به پروفایل</Link>
        <h1>لینک شخصی دریافت پیام</h1>
        <p>لینکت رو به اشتراک بذار تا دیگران بعد از تأیید شمارهٔ خودشون، برات پیام بنویسن.</p>
      </div>
      <div className="account-card">
        <ServiceState />
        {data && !data.authenticated && <AuthGate purpose="برای ساخت لینک شخصی، شمارهٔ خودت رو تأیید کن." />}
        {data?.authenticated && <>
          <ErrorBox message={error}>
            {url === undefined && <button type="button" className="text-button" onClick={() => void load()}>تلاش دوباره</button>}
          </ErrorBox>
          {url === undefined && !error && <p role="status" className="service-loading">در حال دریافت لینک…</p>}
          {url === null && <div className={styles.empty}>
            <p>مقصد پیام‌ها از لینک انتخاب می‌شه. بازدیدکننده فقط شمارهٔ پوشیدهٔ تو رو می‌بینه.</p>
            <BusyButton id="make-personal-share" type="button" className="button primary" busy={busy} onClick={() => void changeLink("POST")}>
              ساخت لینک شخصی
            </BusyButton>
          </div>}
          {url && <div className={styles.content}>
            {link.paused ? <p role="status">دریافت پیام از این لینک فعلاً برای حساب تو در دسترس نیست.</p> : <>
            <section className={styles.links} aria-labelledby="share-link-heading">
              <h2 id="share-link-heading">لینک من</h2>
              <label className="sr-only" htmlFor="share-link">آدرس لینک شخصی</label>
              <input ref={linkField} id="share-link" type="text" dir="ltr" value={url} readOnly spellCheck={false} />
              <div className={styles.actions}>
                <button type="button" className="button primary" disabled={busy} onClick={() => void copy(linkField.current, "لینک کپی شد.")}>کپی لینک</button>
                {canShare && <button type="button" className="button secondary" disabled={busy} onClick={() => void share()}><Icon name="send" size={18} /> اشتراک‌گذاری</button>}
              </div>
              <label htmlFor="share-text">متن آمادهٔ ارسال</label>
              <textarea ref={textField} id="share-text" value={shareIntro + "\n" + url} rows={4} readOnly spellCheck={false} />
              <button type="button" className="button ghost" disabled={busy} onClick={() => void copy(textField.current, "متن و لینک کپی شدند.")}>کپی متن و لینک</button>
            </section>
            <section className={styles.story} aria-labelledby="share-qr-heading">
              <h2 id="share-qr-heading">QR برای استوری</h2>
              <div className={styles.qr}>
                <QRCodeCanvas key={url} ref={qr} value={url} size={264} marginSize={4} level="Q"
                  role="img" aria-label="کد QR لینک شخصی دریافت پیام" />
              </div>
              <button type="button" className="button secondary" disabled={busy} onClick={saveStory}>دانلود تصویر استوری</button>
              <p className="small muted">تصویر رو در استوری بذار یا لینک رو به‌عنوان استیکر لینک اضافه کن.</p>
            </section>
            </>}
            <div className={styles.disable}>
              {confirmDisable ? <>
                <p>با غیرفعال کردن لینک، QR و لینک‌های قبلی از کار می‌افتند.</p>
                <div className={styles.actions}>
                  <BusyButton type="button" className="button secondary" busy={busy} onClick={() => void changeLink("DELETE")}>غیرفعال کن</BusyButton>
                  <button type="button" className="button ghost" disabled={busy} onClick={() => setConfirmDisable(false)}>انصراف</button>
                </div>
              </> : <button type="button" className="text-button" onClick={() => setConfirmDisable(true)}>غیرفعال کردن لینک</button>}
            </div>
          </div>}
          <p className="success-notice" role="status">{notice}</p>
        </>}
      </div>
    </div>
  );
}
