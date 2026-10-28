"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, createIdempotencyKey, errorMessage } from "@/lib/api";
import { latinDigits, normalizePhone, validPhone } from "@/lib/format";
import { Invitation, InvitationList, invitationDeliveryLabel, resendExplanation } from "@/lib/invitations";
import { useApp } from "./app-provider";
import { FreeSendsBalance } from "./free-sends";
import { AuthGate } from "./auth-gate";
import { BusyButton, ErrorBox, ServiceState } from "./feedback";
import { Icon } from "./icons";

const number = (n: number) => new Intl.NumberFormat("fa-IR").format(n);
const date = (value: string) => new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Tehran" }).format(new Date(value));

export function Invitations() {
  const { data, reload } = useApp();
  const [list, setList] = useState<InvitationList | null>(null);
  const [phone, setPhone] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [notice, setNotice] = useState("");
  const keys = useRef(new Map<string, string>());
  const load = useCallback(async (offset = 0, quiet = false) => {
    if (!quiet) { setLoading(true); setError(""); }
    try {
      const result = await api<InvitationList>(`/invitations?offset=${offset}`);
      setList(previous => offset && previous ? { ...result, results: [...previous.results, ...result.results] } : result);
      if (!quiet) void reload();
    } catch (e) {
      if (!quiet) setError(errorMessage(e));
    } finally { if (!quiet) setLoading(false); }
  }, [reload]);
  useEffect(() => {
    if (data?.authenticated) void load();
    else setList(null);
  }, [data?.authenticated, load]);
  useEffect(() => {
    if (!data?.authenticated || busy || (list?.results.length ?? 0) > 50) return;
    const refresh = () => { if (document.visibilityState === "visible") void load(0, true); };
    const timer = window.setInterval(refresh, 30000);
    window.addEventListener("focus", refresh);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", refresh); };
  }, [data?.authenticated, busy, list?.results.length, load]);

  async function send(event?: React.FormEvent, invitation?: Invitation) {
    event?.preventDefault();
    if (busy || !list) return;
    setError(""); setNotice(""); setFieldError("");
    if (!invitation && !validPhone(phone)) {
      setFieldError("شماره موبایل معتبر ایران را وارد کن؛ مانند 09123456789.");
      document.getElementById("invite-phone")?.focus(); return;
    }
    if (!consent) { setError("تأیید کن که مخاطب آشنای توست و مایل به دریافت دعوت است."); return; }
    const target = invitation?.id || normalizePhone(phone);
    const key = keys.current.get(target) || createIdempotencyKey();
    keys.current.set(target, key);
    setBusy(invitation?.id || "new");
    try {
      const result = await api<Invitation>(invitation ? `/invitations/${invitation.id}/resend` : "/invitations", {
        method: "POST", idempotencyKey: key,
        body: { phone: invitation ? undefined : normalizePhone(phone), consent: true, consent_version: list.consent_version },
      });
      keys.current.delete(target);
      if (!invitation) setPhone("");
      setNotice(result.status === "registered" ? "مخاطب ثبت‌نام کرده است؛ دعوت دوباره‌ای ارسال نشد." : "درخواست دعوت ثبت شد. وضعیت پیامک را در فهرست زیر ببین.");
      await load();
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(""); }
  }

  return <div className="account-page invitations-page wrap">
    <div className="account-heading">
      <h1>دوستت رو دعوت کن.</h1>
      <p>شماره‌اش رو اضافه کن؛ با اولین ثبت‌نامش، تو ۳ ارسال جایزه می‌گیری و او ۳ ارسال اولیه. هیچ کد معرفی لازم نیست.</p>
      <FreeSendsBalance />
    </div>
    <div className="account-card">
      <ServiceState />
      <AuthGate purpose="برای دعوت آشنایانت، شمارهٔ خودت را تأیید کن." />
      {data?.authenticated && <>
        {data.demo_mode && <p className="demo-code">در این محیط دعوت‌ها شبیه‌سازی می‌شوند؛ پیامک واقعی ارسال نمی‌شود.</p>}
        <div className="invitation-stats" aria-label="خلاصه دعوت‌ها">
          <div><strong>{number(list?.total ?? 0)}</strong><span>مخاطب دعوت‌شده</span></div>
          <div><strong>{number(list?.registered ?? 0)}</strong><span>ثبت‌نام کرده‌اند</span></div>
          <div><strong>{list ? list.daily_remaining === null ? "بدون سقف" : number(list.daily_remaining) : "…"}</strong><span>{list?.daily_limit === null ? "تعداد درخواست دعوت" : `درخواست باقی‌مانده در ${number(list?.window_hours ?? 24)} ساعت`}</span></div>
        </div>
        <form className="invitation-form" onSubmit={e => void send(e)} noValidate>
          <h2>افزودن یک آشنا</h2>
          <label htmlFor="invite-phone">شماره موبایل مخاطب</label>
          <div className="inline-form">
            <input id="invite-phone" type="tel" inputMode="tel" autoComplete="off" dir="ltr" maxLength={32}
              placeholder="0912 345 6789" value={phone} disabled={!!busy} onChange={e => { setPhone(latinDigits(e.target.value)); setFieldError(""); }}
              aria-invalid={!!fieldError} aria-describedby={fieldError ? "invite-phone-error invite-rules" : "invite-rules"} />
            <BusyButton className="button primary" busy={busy === "new"} disabled={!list || !!busy || !consent || list.daily_remaining === 0}>افزودن و دعوت</BusyButton>
          </div>
          {fieldError && <p className="field-error" id="invite-phone-error">{fieldError}</p>}
          <label className="checkbox-label invitation-consent"><input type="checkbox" checked={consent} disabled={!!busy}
            onChange={e => setConsent(e.target.checked)} /><span>این مخاطب را می‌شناسم و او مایل به دریافت پیام دعوت است. این تأیید برای دعوت دوباره هم برقرار است.</span></label>
          <p id="invite-rules" className="small muted">هر شماره فقط توسط یک نفر قابل دعوت است. شمارهٔ خودت و اعضای قبلی قابل افزودن نیستند.</p>
          <details className="invitation-rules"><summary>متن پیامک و قوانین دعوت</summary>
            <p className="invitation-sms">نمیدونم بهت بگم یا نگم؟{"\n"}یکی از آشناهایت به بگم نگم دعوتت کرده. با ثبت‌نام ۳ ارسال رایگان داری: begamnagam.ir{"\n"}لینک لغو دریافت هم به پیام اضافه می‌شود.</p>
            <p>با اولین تأیید شماره و ساخت حساب مخاطب پس از دعوت، ۳ ارسال جایزه یک‌بار به سهمیهٔ تو اضافه می‌شود. ورود دوباره جایزه ندارد و ثبت‌نام از هر مسیر سایت پذیرفته است.</p>
            {list && <p>{list.max_sends === null ? "تعداد درخواست برای هر مخاطب بدون سقف است." : `حداکثر ${number(list.max_sends ?? 3)} درخواست برای هر مخاطب.`} {list.cooldown_hours ? `فاصلهٔ دو درخواست حداقل ${number(list.cooldown_hours)} ساعت است.` : "فاصلهٔ اجباری بین درخواست‌ها وجود ندارد."} {list.daily_limit === null ? "تعداد درخواست‌های حساب بدون سقف است." : `حداکثر ${number(list.daily_limit ?? 5)} درخواست در ${number(list.window_hours ?? 24)} ساعت.`} {list.validity_days ? `فرصت درخواست مجدد ${number(list.validity_days)} روز است.` : "درخواست مجدد مهلت زمانی ندارد."} دعوت از سهمیهٔ ارسال پیام تو کم نمی‌کند.</p>}
            <p>شماره یا نام تو در پیام دعوت نیست. نتیجهٔ ثبت‌نام مخاطب به تو نمایش داده می‌شود. مخاطب می‌تواند دریافت را لغو کند. پیامک در ساعت مجاز ارسال می‌شود و هر درخواست حداکثر ۴۸ ساعت در صف می‌ماند.</p>
          </details>
        </form>
        <ErrorBox message={error} />
        <p className="success-notice" role="status">{notice}</p>
        <div className="history-toolbar"><h2>دعوت‌های من</h2><BusyButton className="button ghost compact" busy={loading} disabled={!!busy} onClick={() => void load()}><Icon name="refresh" size={17} /> تازه‌سازی</BusyButton></div>
        {loading && !list && <p role="status" className="service-loading"><span className="spinner" /> در حال دریافت دعوت‌ها…</p>}
        {list && (list.results.length ? <div className="message-list">{list.results.map(item => <article key={item.id} className="history-message invitation-item">
          <div className="history-message-top"><span className="recipient-label"><Icon name="phone" size={17} /><bdi>{item.phone_masked}</bdi></span>
            <span className={`status-pill ${item.status === "registered" ? "invitation-registered" : ""}`}>{item.status === "registered" ? "ثبت‌نام کرد" : item.status === "expired" ? "مهلت دعوت تمام شده" : "منتظر ثبت‌نام"}</span></div>
          <p>{item.registered_at ? `ثبت‌نام و دریافت سهمیهٔ اولیه در ${date(item.registered_at)}` : invitationDeliveryLabel(item.delivery_status)}</p>
          {item.reward_credits > 0 && <p className="invitation-reward"><Icon name="sparkle" size={17} /> {number(item.reward_credits)} ارسال جایزه به سهمیه‌ات اضافه شد.</p>}
          {item.reward_pending && <p className="small muted">جایزهٔ ثبت‌نام در حال بررسی و افزودن است.</p>}
          {item.reason && <p className="small muted">{item.reason}</p>}
          <div className="invitation-progress"><span>{number(item.send_count)}{item.max_sends == null ? " نوبت درخواست" : ` از ${number(item.max_sends)} نوبت درخواست`}</span><span>{item.sends_remaining === null ? "بدون سقف تعداد" : `${number(item.sends_remaining)} نوبت باقی‌مانده`}</span></div>
          <div className="invitation-actions"><BusyButton className="button secondary compact" busy={busy === item.id}
            disabled={!item.can_resend || !!busy || !consent || list.daily_remaining === 0} aria-describedby={`invite-state-${item.id}`} onClick={() => void send(undefined, item)}>دعوت دوباره</BusyButton>
            <p id={`invite-state-${item.id}`} className="small muted">{resendExplanation(item) || (!consent ? "برای دعوت دوباره، تأیید بالای فرم را بزن." : list.daily_remaining === 0 ? "سقف روزانهٔ دعوت تکمیل شده است." : "دعوت دوباره با پیامک ارسال می‌شود.")}</p></div>
          <details className="order-details"><summary>نوبت‌های دعوت</summary>{item.sends.map(s => <p key={s.number}>نوبت {number(s.number)} · {invitationDeliveryLabel(s.status)}<br /><time dateTime={s.created_at}>{date(s.created_at)}</time></p>)}</details>
        </article>)}</div> : <div className="empty-state"><Icon name="heart" size={38} /><h3>اولین دعوتت رو ثبت کن.</h3><p>شمارهٔ یکی از آشنایانت را در فرم بالا اضافه کن؛ نتیجه‌اش همین‌جا می‌ماند.</p></div>)}
        {list?.next_offset != null && <BusyButton className="button ghost full-width" busy={loading} disabled={!!busy} onClick={() => void load(list.next_offset!)}>دعوت‌های بیشتر</BusyButton>}
      </>}
    </div>
  </div>;
}
