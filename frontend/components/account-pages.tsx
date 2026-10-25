"use client";
import { FreeSendsBalance } from "./free-sends";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, errorMessage, type Message } from "@/lib/api";
import { statusLabel, toman } from "@/lib/format";
import { useApp } from "./app-provider";
import { AuthGate } from "./auth-gate";
import { BusyButton, ErrorBox, ServiceState } from "./feedback";
import { Icon } from "./icons";

export function Preferences() {
  const { data } = useApp();
  const [blocked, setBlocked] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api<{ blocked: boolean }>("/preferences");
      setBlocked(result.blocked);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    if (data?.authenticated) void load();
    else setBlocked(null);
  }, [data?.authenticated, load]);

  async function save() {
    if (blocked === null) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api<{ blocked: boolean }>("/preferences", {
        method: "POST",
        body: { blocked: !blocked },
      });
      setBlocked(result.blocked);
      setNotice(
        result.blocked
          ? "دریافت پیام برای شماره شما متوقف شد."
          : "دریافت پیام برای شماره شما دوباره فعال شد.",
      );
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="account-page wrap">
      <Link href="/" className="back-link">
        بازگشت به خانه <Icon name="arrow" size={16} />
      </Link>
      <div className="account-heading">
        <span className="eyebrow">انتخاب با توست</span>
        <h1>حقت هست که نشنوی.</h1>
        <p>
          اگر نمی‌خوای از بگم نگم پیام دریافت کنی، شماره خودت رو تأیید کن و
          دریافت رو برای همه فرستنده‌ها متوقف کن.
        </p>
      </div>
      <div className="account-card">
        <ServiceState />
        <AuthGate purpose="شماره‌ای که می‌خوای دریافتش متوقف بشه، تأیید کن." />
        {data?.authenticated && (
          <div className="preferences-state">
            {!data.recent_auth && <AuthGate forceReverify purpose="برای فعال‌سازی دوباره یا درخواست حذف، شماره خودت را مجدداً تأیید کن."/>}
            <ErrorBox message={error}>
              {blocked === null && (
                <button className="text-button" onClick={() => void load()}>
                  تلاش دوباره
                </button>
              )}
            </ErrorBox>
            {loading && (
              <p role="status" className="service-loading">
                <span className="spinner" /> در حال دریافت تنظیمات…
              </p>
            )}
            {!loading && blocked !== null && (
              <>
                <div
                  className={`preference-status ${blocked ? "blocked" : ""}`}
                >
                  <span className="preference-icon">
                    <Icon name={blocked ? "shield" : "chat"} size={25} />
                  </span>
                  <div>
                    <h2>
                      {blocked ? "دریافت پیام متوقف شده" : "دریافت پیام فعاله"}
                    </h2>
                    <p>
                      {blocked
                        ? "ارسال‌های جدید بگم نگم به شماره شما متوقف می‌شوند."
                        : "در حال حاضر دریافت پیام از بگم نگم برای شماره شما مجازه."}
                    </p>
                  </div>
                </div>
                <BusyButton
                  className={`button ${blocked ? "secondary" : "primary"} full-width`}
                  busy={busy}
                  disabled={!!blocked && !data.recent_auth}
                  onClick={save}
                >
                  {blocked
                    ? "فعال‌کردن دوباره دریافت پیام"
                    : "توقف دریافت تمام پیام‌ها"}
                </BusyButton>
                <p className="small muted">
                  این تنظیم برای شماره تأییدشده در کل سرویس اعمال می‌شه و هر وقت
                  بخوای قابل تغییره.
                </p>
              </>
            )}
            <details className="recipient-report"><summary>درخواست حذف داده‌های حساب</summary><p>ارسال جدید حساب متوقف می‌شود و شماره قابل‌بازیابی حداکثر۳۰روز بعد حذف می‌شود. سوابق مالی حداقلی و توقف دریافت مستقل حفظ می‌شوند.</p><label className="checkbox-label"><input type="checkbox" checked={deleteConfirmed} onChange={e=>setDeleteConfirmed(e.target.checked)}/><span>می‌خواهم حذف داده‌های حسابم ثبت شود.</span></label><BusyButton className="button secondary" busy={busy} disabled={!deleteConfirmed || !data.recent_auth} onClick={()=>{setBusy(true);setError("");void api("/account/deletion",{method:"POST",body:{}}).then(()=>{setNotice("درخواست حذف ثبت شد؛ ارسال جدید حساب متوقف است.");setDeleteConfirmed(false);}).catch(e=>setError(errorMessage(e))).finally(()=>setBusy(false));}}>ثبت درخواست حذف</BusyButton>{!data.recent_auth && <p>ابتدا با تأیید دوباره شماره وارد شو.</p>}</details>
            <p className="success-notice" role="status">
              {notice}
            </p>
          </div>
        )}
      </div>
      <div className="account-bottom-note">
        <Icon name="lock" size={19} />
        <p>
          از این صفحه نمی‌شه هویت فرستنده یا اطلاعات فرد دیگری رو دید. تأیید
          شماره برای اطمینان از مالکیت همون شماره است.
        </p>
      </div>
    </div>
  );
}

export function History() {
  const { data, reload } = useApp();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api<{ results: Message[] }>("/messages");
      setMessages(result.results);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    if (data?.authenticated) void load();
    else setMessages([]);
  }, [data?.authenticated, load]);

  async function logout() {
    setLoggingOut(true);
    setError("");
    try {
      await api("/auth/logout", { method: "POST", body: {} });
      setMessages([]);
      await reload();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <div className="account-page history-page wrap">
      <Link href="/" className="back-link">
        بازگشت به خانه <Icon name="arrow" size={16} />
      </Link>
      <div className="account-heading">
        <span className="eyebrow">پیگیری بدون ابهام</span>
        <h1>پیام‌های من.</h1>
        <FreeSendsBalance />
        <p>
          درخواست‌های ثبت‌شده و وضعیت پردازش اون‌ها رو اینجا ببین. این وضعیت‌ها
          نشون نمی‌دن که گیرنده پیام رو خونده یا نه.
        </p>
      </div>
      <div className="account-card">
        <ServiceState />
        <AuthGate purpose="برای دیدن پیام‌هات، شماره خودت رو تأیید کن." />
        {data?.authenticated && (
          <>
            <div className="history-toolbar">
              <h2>درخواست‌های ارسال شما</h2>
              <BusyButton
                className="button ghost compact"
                busy={loading}
                onClick={() => void load()}
              >
                <Icon name="refresh" size={17} /> تازه‌سازی
              </BusyButton>
            </div>
            <ErrorBox message={error} />
            {loading ? (
              <p className="service-loading" role="status">
                <span className="spinner" /> در حال دریافت پیام‌ها…
              </p>
            ) : messages.length > 0 ? (
              <div className="message-list">
                {messages.map((message) => (
                  <article key={message.id} className="history-message">
                    <div className="history-message-top">
                      <span className="recipient-label">
                        <Icon name="phone" size={17} /> برای{" "}
                        <bdi>{message.recipient_masked}</bdi>
                      </span>
                      <span
                        className={`status-pill ${message.status === "failed" ? "failed" : ""}`}
                      >
                        {statusLabel(message.status)}
                        {data.demo_mode ? " · آزمایشی" : ""}
                      </span>
                    </div>
                    <p>{message.text || "متن این پیام طبق سیاست نگهداری حذف شده است."}</p>
                    <p className="small muted">مالی: {message.financial_status === "free_credit_returned" ? "رایگان؛ سهمیه برگشت داده شد" : message.is_free ? "رایگان؛ بدون پرداخت" : message.financial_status === "refund_pending" ? "بازپرداخت در حال پیگیری است" : message.financial_status === "refunded" ? "مسترد شد" : message.financial_status === "verified" ? "تأیید شد" : message.financial_status === "unknown" ? "نیازمند بررسی؛ دوباره پرداخت نکن" : "در انتظار"}</p>
                    <div className="history-message-bottom">
                      <time dateTime={message.created_at}>
                        {new Intl.DateTimeFormat("fa-IR", {
                          dateStyle: "medium",
                          timeStyle: "short",
                          timeZone: "Asia/Tehran",
                        }).format(new Date(message.created_at))}
                      </time>
                      <span>{message.is_free ? "رایگان" : toman(message.amount_toman)}</span>
                    </div>
                    <details className="order-details">
                      <summary>شناسه پیگیری</summary>
                      <bdi>{message.id}</bdi>
                    </details>
                  </article>
                ))}
              </div>
            ) : (
              !error && (
                <div className="empty-state">
                  <Icon name="receipt" size={40} />
                  <h3>هنوز پیامی ثبت نکردی.</h3>
                  <p>
                    هر وقت حرفی از سرِ توجه داشتی، از یک پیام کوتاه شروع کن.
                  </p>
                  <Link href="/#compose" className="button primary">
                    نوشتن اولین پیام <Icon name="arrow" size={17} />
                  </Link>
                </div>
              )
            )}
            <div className="account-signout">
              <BusyButton
                className="text-button"
                busy={loggingOut}
                onClick={logout}
              >
                خروج از حساب
              </BusyButton>
              <span className="small muted">
                روی دستگاه مشترک، بعد از استفاده خارج شو.
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
