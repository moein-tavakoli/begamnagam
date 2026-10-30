"use client";

import { DigitInput } from "./digit-input";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import { managementActions, managementDate, managementNumber, managementState,
  type LimitRule, type LimitSettings, type ManagementAction, type ManagementDashboard,
  type ManagementRecords, type ManagementSession } from "@/lib/management";
import { Brand } from "./chrome";
import { Icon } from "./icons";
import { ProviderBalances } from "./provider-balances";
import { AISettings } from "./ai-settings";
import { ManualPaymentSettings } from "./manual-payment-settings";
import { ManualPaymentDialog } from "./manual-payment-dialog";
import { SupportInbox, useSupportBadge } from "./support-inbox";
import type { SupportWorkspaceMemory } from "@/lib/support";
import supportStyles from "./support-chat.module.css";
import { PackageSettings } from "./package-settings";
import { ExampleSettings } from "./example-settings";
import { walletToman } from '@/lib/wallet';

function Failure({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="manage-error" role="alert"><span>{message}</span>{retry && <button className="manage-button secondary" onClick={retry}>تلاش دوباره</button>}</div>;
}
function Loading() { return <p className="manage-loading" role="status">در حال دریافت اطلاعات…</p>; }

export function ManagementConsole() {
  const [session, setSession] = useState<ManagementSession | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("dashboard");
  const [menu, setMenu] = useState(false);
  const [busy, setBusy] = useState(false);
  const [epoch, setEpoch] = useState(0);
  const [action, setAction] = useState<ManagementAction | null>(null);
  const sessionGeneration = useRef(0);
  const supportIdentity = useRef<string|undefined>(undefined);
  const supportMemory = useRef<SupportWorkspaceMemory>({thread:null,composer:{draft:"",pending:null}});
  const loadSession = useCallback(async () => {
    const generation = ++sessionGeneration.current;
    setSession(null); setAction(null); setError("");
    try {
      const current = await api<ManagementSession>("/manage/session");
      if (generation === sessionGeneration.current) {
        if (!current.authenticated || supportIdentity.current !== current.session_identity) supportMemory.current={thread:null,composer:{draft:"",pending:null}};
        supportIdentity.current=current.session_identity;
        setSession(current);
      }
    }
    catch (e) { if (generation === sessionGeneration.current) setError(errorMessage(e)); }
  }, []);
  useEffect(() => {
    void loadSession();
    const refresh = () => { void loadSession(); };
    const visible = () => { if (document.visibilityState === "visible") refresh(); };
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", visible);
    return () => {
      sessionGeneration.current += 1;
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [loadSession]);
  const failed = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.code === "management_login_required") setSession({ authenticated: false });
  }, []);
  async function signOut() {
    setBusy(true); setError("");
    try { await api("/manage/logout", { method: "POST", body: {} }); setSession({ authenticated: false }); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  const supportFailure = useCallback((e:unknown) => { failed(e); if(e instanceof ApiError && e.code === 'forbidden') setSession({authenticated:false}); },[failed]);
  const supportCount = useSupportBadge(!!session?.authenticated,supportFailure);
  const permissions = session?.permissions || [];
  const navigation = [
    ...(permissions.includes("view_operations") ? [{ key: "dashboard", title: "نمای کلی" }] : []),
    ...(session?.authenticated ? [{key:"support",title:"پشتیبانی"}] : []),
    ...(session?.resources || []),
    ...(permissions.includes("manage_site_limits") ? [{ key: "limits", title: "تنظیمات سایت" }] : []),
    ...(permissions.includes("manage_message_packages") ? [{ key: "packages", title: "بسته‌های پیام" }] : []),
    ...(permissions.includes("manage_message_examples") ? [{ key: "examples", title: "پیام‌های نمونه" }] : []),
    ...(permissions.includes("manage_manual_payments") ? [{ key: "manual-settings", title: "کارت و دریافت رسید" }] : []),
    ...(permissions.includes("manage_ai") ? [{ key: "ai", title: "هوش مصنوعی" }] : []),
  ];
  const active = navigation.some(item => item.key === tab) ? tab : session?.resources?.[0]?.key || navigation[0]?.key;
  const title = navigation.find(item => item.key === active)?.title || "مدیریت";
  return <div className="manage-app" data-update-blocked="true">
    {!session || !session.authenticated ? <div className="manage-login-wrap"><Brand />
      <section className="manage-login"><span className="manage-kicker"><Icon name="shield" size={19} /> پنل مدیریت</span><h1>مدیریت بگم نگم</h1>
        <p>با نام کاربری و رمز حساب مدیر وارد شوید.</p>
        {error && <Failure message={error} retry={() => void loadSession()} />}
        {!session ? <Loading /> : <Login onLogin={setSession} />}
        <Link href="/" className="manage-site-link">مشاهدهٔ سایت</Link>
      </section></div> : <>
      <aside className={`manage-sidebar ${menu ? "is-open" : ""}`}>
        <Brand /><span className="manage-kicker">مدیریت محصول</span>
        <nav id="manage-navigation" aria-label="بخش‌های مدیریت">{navigation.map(item => <button key={item.key} aria-current={active === item.key ? "page" : undefined} onClick={() => { setTab(item.key); setMenu(false); }}>{item.title}{item.key === "support" && supportCount>0 && <span className={supportStyles.navBadge} aria-label={`${supportCount.toLocaleString("fa-IR")} گفت‌وگوی نیازمند توجه`}>{supportCount.toLocaleString("fa-IR")}</span>}</button>)}</nav>
        <a className="manage-advanced" href="/admin/">مدیریت پیشرفتهٔ جنگو ↗</a>
      </aside>
      <div className="manage-workspace">
        <header className="manage-topbar"><div className="manage-heading"><button className="manage-button secondary manage-menu" aria-expanded={menu} aria-controls="manage-navigation" onClick={() => setMenu(!menu)}>{menu ? "بستن منو" : "بخش‌ها"}</button><h1>{title}</h1></div>
          <div className="manage-session"><span><Icon name="user" size={17} /><bdi>{session.username}</bdi></span><Link href="/" className="manage-button secondary">سایت</Link><button className="manage-button secondary" disabled={busy} onClick={() => void signOut()}>خروج</button></div>
        </header>
        {permissions.includes("view_operations") && <ProviderBalances onFailure={failed} />}
        <span className="sr-only" role="status" aria-atomic="true">{supportCount>0 ? `${supportCount.toLocaleString("fa-IR")} گفت‌وگوی پشتیبانی تازه یا بی‌پاسخ داری.` : ""}</span>
        <div className="manage-content">{error && <Failure message={error} />}
          {!active && <section className="manage-card"><p>برای این حساب بخشی مجاز نشده است. مجوزها از مدیریت پیشرفتهٔ جنگو قابل تنظیم‌اند.</p></section>}
          {active === "examples" ? <ExampleSettings onFailure={failed} /> : active === "support" ? <SupportInbox onFailure={supportFailure} memory={supportMemory} /> : active === "dashboard" ? <Dashboard key={`dashboard-${epoch}`} canOperate={permissions.includes("operate_safety")} onAction={setAction} onFailure={failed} /> : active === "limits" ? <Limits onFailure={failed} /> : active === "ai" ? <AISettings onFailure={failed} /> : active === "manual-settings" ? <ManualPaymentSettings onFailure={failed} /> : active === "packages" ? <PackageSettings onFailure={failed} /> : active && <Records key={`${active}-${epoch}`} resource={active} permissions={permissions} onAction={setAction} onFailure={failed} />}
          <p className="manage-footnote">زمان‌ها به وقت تهران · تغییرات مدیریتی با دلیل و سابقه ثبت می‌شوند.</p>
        </div>
      </div>
      {action && (["grant_package","approve_card","reject_card"].includes(action.name) ? <ManualPaymentDialog action={action} onClose={() => setAction(null)} onComplete={() => { setAction(null); setEpoch(v => v + 1); }} onFailure={failed} /> : <ActionDialog action={action} onClose={() => setAction(null)} onComplete={() => { setAction(null); setEpoch(v => v + 1); }} onFailure={failed} />)}
    </>}
  </div>;
}

function Login({ onLogin }: { onLogin: (session: ManagementSession) => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError("");
    try { onLogin(await api<ManagementSession>("/manage/login", { method: "POST", body: { username: form.get("username"), password: form.get("password") } })); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  return <form onSubmit={submit} className="manage-form">{error && <Failure message={error} />}
    <label>نام کاربری<input name="username" autoComplete="username" dir="ltr" maxLength={150} required /></label>
    <label>رمز عبور<input name="password" type="password" autoComplete="current-password" dir="ltr" maxLength={512} required /></label>
    <button className="manage-button primary" disabled={busy}>{busy ? "در حال ورود…" : "ورود به مدیریت"}</button>
  </form>;
}

function Dashboard({ canOperate, onAction, onFailure }: { canOperate: boolean; onAction: (a: ManagementAction) => void; onFailure: (e: unknown) => void }) {
  const [data, setData] = useState<ManagementDashboard | null>(null), [error, setError] = useState("");
  const load = useCallback(async () => { setError(""); try { setData(await api<ManagementDashboard>("/manage/dashboard")); } catch (e) { setError(errorMessage(e)); onFailure(e); } }, [onFailure]);
  useEffect(() => { void load(); }, [load]);
  if (!data) return error ? <Failure message={error} retry={() => void load()} /> : <Loading />;
  const totals: [string, string][] = [["accounts", "حساب کاربری"], ["orders", "درخواست پیام"], ["delivered", "پیامک رسیده"], ["invitations", "دعوت ثبت‌شده"], ["registered_invitations", "عضویت با دعوت"], ["active_alerts", "هشدار فعال"]];
  const metrics: [string, string][] = [["outbox_pending", "در انتظار ارسال"], ["delivery_unknown", "تحویل نیازمند تطبیق"], ["payment_unknown", "پرداخت نیازمند تطبیق"], ["refund_open", "بازپرداخت باز"], ["reports_open", "گزارش باز"], ["oldest_queue_seconds", "عمر قدیمی‌ترین صف (ثانیه)"]];
  return <><div className="manage-section-heading"><div><p className="manage-kicker">وضعیت فعلی محصول</p><h2>آنچه در سایت می‌گذرد</h2></div><button className="manage-button secondary" onClick={() => void load()}>تازه‌سازی</button></div>
    {error && <Failure message={error} />}
    <div className="manage-stats">{totals.map(([key, label]) => <article className="manage-stat" key={key}><span>{label}</span><strong>{managementNumber(data.totals[key])}</strong></article>)}</div>
    <section className="manage-card"><div className="manage-section-heading"><h2>ارسال و صف پردازش</h2><span className={`manage-badge ${data.operations.sending_halted ? "warn" : "good"}`}>{data.operations.sending_halted ? "ارسال متوقف است" : "ارسال باز است"}</span></div>
      <div className="manage-metrics">{metrics.map(([key, label]) => <div key={key}><span>{label}</span><strong>{managementNumber(data.operations[key])}</strong></div>)}</div>
      {canOperate && <button className={`manage-button ${data.operations.sending_halted ? "primary" : "danger"}`} onClick={() => onAction({ name: data.operations.sending_halted ? "resume" : "halt", label: data.operations.sending_halted ? "ازسرگیری ارسال" : "توقف ارسال جدید", object_id: "global" })}>{data.operations.sending_halted ? "ازسرگیری ارسال" : "توقف ارسال جدید"}</button>}
    </section>
    <div className="manage-two-columns"><section className="manage-card"><h2>اتصال سرویس‌ها</h2><dl className="manage-definition"><div><dt>محیط</dt><dd>{data.environment.demo ? "آزمایشی" : "واقعی"}</dd></div><div><dt>پیامک</dt><dd><bdi>{data.environment.sms}</bdi></dd></div><div><dt>کد ورود</dt><dd><bdi>{data.environment.otp}</bdi></dd></div><div><dt>پرداخت پولی</dt><dd>{data.environment.paid_enabled ? "فعال" : "بسته"}</dd></div></dl></section>
      <section className="manage-card manage-budget"><h2>دفتر هزینهٔ پیامک</h2><p>رزرو ثبت‌شدهٔ امروز</p><strong>{managementNumber(data.operations.provider_budget_reserved_rial)} <small>ریال</small></strong><p>سقف روزانه: {data.operations.provider_budget_unlimited ? "بدون سقف" : `${managementNumber(data.operations.provider_budget_limit_rial)} ریال`}</p><small>رزرو هزینه با صورتحساب قطعی سرویس پیامک یکسان نیست.</small></section></div>
    <p className="manage-muted">آخرین دریافت: {managementDate(data.updated_at)}</p>
  </>;
}

function Cell({ value, kind }: { value: unknown; kind: string }) {
  if (value === null || value === undefined || value === "") return <>—</>;
  if (kind === "bool") return <span className={`manage-badge ${value ? "good" : "neutral"}`}>{value ? "بله" : "خیر"}</span>;
  if (kind === "date") return <span className="manage-nowrap">{managementDate(value)}</span>;
  if (kind === "number") return <>{managementNumber(value)}</>;
  if (kind === "money") return <>{walletToman(String(value))}</>;
  if (kind === "status") return <span className="manage-badge">{managementState(value)}</span>;
  if (kind === "json") return <details><summary>مشاهدهٔ مقادیر</summary><pre className="manage-json" dir="ltr">{JSON.stringify(value, null, 2)}</pre></details>;
  if (kind === "id") return <bdi className="manage-record-id" title={String(value)}>{String(value)}</bdi>;
  return <bdi>{String(value)}</bdi>;
}

function Records({ resource, permissions, onAction, onFailure }: { resource: string; permissions: string[]; onAction: (a: ManagementAction) => void; onFailure: (e: unknown) => void }) {
  const [data, setData] = useState<ManagementRecords | null>(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState({ page: 1, query: "", status: "" });
  useEffect(() => {
    const controller = new AbortController(); setBusy(true); setError("");
    void api<ManagementRecords>(`/manage/records/${resource}`, { method: "POST", body: filter, signal: controller.signal }).then(setData).catch(e => { if (controller.signal.aborted) return; setError(errorMessage(e)); onFailure(e); }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [resource, filter, onFailure]);
  function search(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); setFilter({ page: 1, query: String(form.get("query") || ""), status: String(form.get("status") || "") }); }
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return <section className="manage-card manage-records"><form className="manage-search" onSubmit={search}>
    <label>جست‌وجو<input name="query" maxLength={100} placeholder={resource === "accounts" || resource === "invitations" ? "شماره موبایل یا شناسه" : "شناسه، وضعیت یا کد"} /></label>
    {!!data?.statuses.length && <label>وضعیت<select name="status" defaultValue=""><option value="">همهٔ وضعیت‌ها</option>{data.statuses.map(([key, label]) => <option key={key} value={key}>{managementState(key) === key ? label : managementState(key)}</option>)}</select></label>}
    <button className="manage-button primary" disabled={busy}>جست‌وجو</button><button className="manage-button secondary" type="button" disabled={busy} onClick={() => setFilter(v => ({ ...v }))}>تازه‌سازی</button>
  </form>
    {error && <Failure message={error} retry={() => setFilter(v => ({ ...v }))} />}
    {busy && <Loading />}
    {data && !busy && !error && <><div className="manage-table-info"><span>{managementNumber(data.total)} رکورد</span><span>صفحهٔ {managementNumber(data.page)} از {managementNumber(pages)}</span></div>
      {!data.rows.length ? <div className="manage-empty"><Icon name="receipt" size={32} /><h2>رکوردی پیدا نشد</h2><p>پس از ثبت فعالیت، اطلاعات این بخش نمایش داده می‌شود.</p></div> : <div className="manage-table-scroll" tabIndex={0} role="region" aria-label={data.title}><table><caption className="sr-only">{data.title}</caption><thead><tr>{data.columns.map(col => <th scope="col" key={col.key}>{col.label}</th>)}{data.rows.some(row => managementActions(resource, row, permissions).length > 0) && <th scope="col">اقدام</th>}</tr></thead><tbody>{data.rows.map(row => <tr key={row.record_id}>{data.columns.map(col => <td key={col.key}><Cell value={row[col.key]} kind={col.type} /></td>)}{data.rows.some(r => managementActions(resource, r, permissions).length > 0) && <td><div className="manage-row-actions">{managementActions(resource, row, permissions).map(item => <button key={item.name} className="manage-button secondary" onClick={() => onAction(item)}>{item.label}</button>)}</div></td>}</tr>)}</tbody></table></div>}
      <nav className="manage-pagination" aria-label="صفحه‌بندی رکوردها"><button className="manage-button secondary" disabled={filter.page <= 1} onClick={() => setFilter(v => ({ ...v, page: v.page - 1 }))}>صفحهٔ قبل</button><button className="manage-button secondary" disabled={filter.page >= pages} onClick={() => setFilter(v => ({ ...v, page: v.page + 1 }))}>صفحهٔ بعد</button></nav>
    </>}
  </section>;
}

function Limits({ onFailure }: { onFailure: (e: unknown) => void }) {
  const [data, setData] = useState<LimitSettings | null>(null), [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const onSaved = (updated: LimitSettings) => { setData(updated); setSaved(true); };
  const load = useCallback(async () => { setError(""); try { setData(await api<LimitSettings>("/manage/limits")); } catch (e) { setError(errorMessage(e)); onFailure(e); } }, [onFailure]);
  useEffect(() => { void load(); }, [load]);
  return <>{error && <Failure message={error} retry={() => void load()} />}{saved && <p className="manage-success" role="status">تنظیمات ذخیره شد.</p>}{!data ? !error && <Loading /> : <><div className="manage-notice">سه ارسال هدیهٔ اولیه رایگان می‌مانند؛ روش‌های پرداخت از این بخش تنظیم می‌شوند. صفر در بازه‌های شمارش ساعتی و فاصله‌ها، همان محدودیت را خاموش می‌کند. در ساعت شروع و پایان، صفر یعنی نیمه‌شب؛ برای ارسال در تمام شبانه‌روز، تیک «ارسال فقط در ساعت مجاز» را بردارید.</div>{data.gateway_problem && <p className="manage-notice">درگاه آمادهٔ فعال‌سازی نیست: {data.gateway_problem}</p>}<SiteLimits key={`site-${data.revision}`} data={data} onSaved={onSaved} onFailure={onFailure} /><RequestLimits rules={data.requests} onSaved={onSaved} onFailure={onFailure} /></>}</>;
}

function SiteLimits({ data, onSaved, onFailure }: { data: LimitSettings; onSaved: (d: LimitSettings) => void; onFailure: (e: unknown) => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [message, setMessage] = useState("");
  const [fields, setFields] = useState<Record<string, string | string[]>>({});
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); const values: Record<string, number | boolean> = {};
    for (const [key, value] of Object.entries(data.values)) values[key] = typeof value === "boolean" ? form.get(key) === "on" : Number(form.get(key));
    setBusy(true); setError(""); setMessage(""); setFields({});
    try { const updated = await api<LimitSettings>("/manage/limits", { method: "POST", body: { values, revision: data.revision, reason: form.get("reason") } }); onSaved(updated); setMessage("تنظیمات ذخیره شد."); }
    catch (e) { setError(errorMessage(e)); if (e instanceof ApiError) setFields(e.fields || {}); onFailure(e); }
    finally { setBusy(false); }
  }
  return <form className="manage-card manage-form" onSubmit={save}><div className="manage-section-heading"><h2>تنظیمات مشترک سایت</h2><span className="manage-muted">نسخهٔ {managementNumber(data.revision)}</span></div>
    {error && <Failure message={error} />}{message && <p className="manage-success" role="status">{message}</p>}
    {fields.__all__ && <Failure message={String(fields.__all__)} />}
    <fieldset disabled={busy} className="manage-fieldset">{data.sections.map((section, i) => <details className="manage-settings-section" key={section.title} open={i < 2}><summary>{section.title}</summary><div className="manage-settings-grid">{section.fields.map(field => <label key={field.key} className={field.type === "bool" ? "manage-checkbox" : ""} htmlFor={`limit-${field.key}`}>
      <span>{field.label}</span>{field.type === "bool" ? <input id={`limit-${field.key}`} name={field.key} type="checkbox" role={["wallet_enabled","gateway_enabled"].includes(field.key) ? "switch" : undefined} defaultChecked={Boolean(data.values[field.key])} aria-invalid={!!fields[field.key]} aria-describedby={field.help || fields[field.key] ? `help-${field.key}` : undefined} /> : <DigitInput id={`limit-${field.key}`} name={field.key} type="number" min={field.min ?? 0} step={1} max={field.max ?? Number.MAX_SAFE_INTEGER} defaultValue={Number(data.values[field.key])} required aria-invalid={!!fields[field.key]} aria-describedby={field.help || fields[field.key] ? `help-${field.key}` : undefined} />}
      {(field.help || fields[field.key]) && <small id={`help-${field.key}`} className={fields[field.key] ? "manage-field-error" : ""}>{fields[field.key] ? String(fields[field.key]) : field.help}</small>}
    </label>)}</div></details>)}
      <label>دلیل تغییر<input name="reason" required minLength={3} maxLength={200} placeholder="دلیل کوتاه؛ اطلاعات خصوصی ننویسید" /></label>
      <div className="manage-form-actions"><button className="manage-button primary">{busy ? "در حال ذخیره…" : "ذخیرهٔ تنظیمات"}</button><button type="button" className="manage-button secondary" onClick={() => window.location.reload()}>دریافت آخرین تنظیمات</button></div>
    </fieldset>
  </form>;
}

function RequestLimits({ rules, onSaved, onFailure }: { rules: LimitRule[]; onSaved: (d: LimitSettings) => void; onFailure: (e: unknown) => void }) {
  const [scope, setScope] = useState(rules[0]?.scope || "");
  return <section className="manage-card"><h2>کنترل تعداد درخواست‌ها</h2><p className="manage-muted">کنترل ورود مدیر، حدس کد، لینک خصوصی، شارژ کیف پول و بازگشت پرداخت باید فعال بماند. مقدار تعداد و بازه قابل تنظیم است.</p><label className="manage-rule-picker">نوع درخواست<select value={scope} onChange={e => setScope(e.target.value)}>{rules.map(rule => <option key={rule.scope} value={rule.scope}>{rule.label} · {rule.enabled ? "فعال" : "بدون سقف"}</option>)}</select></label>{rules.find(rule => rule.scope === scope) && <RequestRule key={`${scope}:${rules.find(rule => rule.scope === scope)!.revision}`} rule={rules.find(rule => rule.scope === scope)!} onSaved={onSaved} onFailure={onFailure} />}</section>;
}

function RequestRule({ rule, onSaved, onFailure }: { rule: LimitRule; onSaved: (d: LimitSettings) => void; onFailure: (e: unknown) => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError("");
    try { onSaved(await api<LimitSettings>(`/manage/request-limits/${rule.scope}`, { method: "POST", body: { revision: rule.revision, reason: form.get("reason"), values: { enabled: rule.protected || form.get("enabled") === "on", maximum: Number(form.get("maximum")), window_seconds: Number(form.get("window_seconds")) } } })); }
    catch (e) { setError(errorMessage(e)); onFailure(e); } finally { setBusy(false); }
  }
  return <form className="manage-form" onSubmit={save}>{error && <Failure message={error} />}<fieldset className="manage-fieldset" disabled={busy}><label className="manage-checkbox"><span>کنترل فعال باشد</span><input name="enabled" type="checkbox" defaultChecked={rule.enabled} disabled={rule.protected} /></label><div className="manage-settings-grid"><label>حداکثر تعداد<DigitInput name="maximum" type="number" min={1} step={1} defaultValue={rule.maximum} required /></label><label>بازه (ثانیه)<DigitInput name="window_seconds" type="number" min={1} step={1} defaultValue={rule.window_seconds} required /></label></div><label>دلیل تغییر<input name="reason" minLength={3} maxLength={200} required /></label><button className="manage-button primary">{busy ? "در حال ذخیره…" : "ذخیرهٔ این کنترل"}</button></fieldset></form>;
}

function ActionDialog({ action, onClose, onComplete, onFailure }: { action: ManagementAction; onClose: () => void; onComplete: () => void; onFailure: (e: unknown) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [report, setReport] = useState<{ details: string; reviewed_text: string; reason: string; status: string } | null>(null);
  const [texts, setTexts] = useState<{ original_text: string; original_available: boolean; final_text: string; mode: string } | null>(null);
  useEffect(() => { const previous = document.activeElement as HTMLElement | null; ref.current?.showModal(); return () => { previous?.focus(); }; }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError("");
    try {
      const countValues = Object.fromEntries(['sender_daily_limit', 'rewrite_daily_limit'].map(key => [key,
        form.get(`${key}_mode`) === 'site' ? null : form.get(`${key}_mode`) === 'unlimited' ? 0 : Number(form.get(key))]));
      const values = { action: action.name, object_id: action.object_id, value: action.value, reason: form.get("reason"), reference: form.get("reference") || "",
        ...(action.name === 'account_limits' ? { values: countValues } : {}) };
      if (action.name === "review") setReport(await api(`/manage/reports/${action.object_id}/review`, { method: "POST", body: values }));
      else if (action.name === "message_texts") setTexts(await api(`/manage/orders/${action.object_id}/texts`, { method: "POST", body: values }));
      else { await api("/manage/actions", { method: "POST", body: values }); onComplete(); }
    } catch (e) { setError(errorMessage(e)); onFailure(e); } finally { setBusy(false); }
  }
  return <dialog ref={ref} className={`manage-dialog${action.name === 'account_limits' ? ' manage-account-limits' : ''}`} aria-labelledby="manage-dialog-title" onCancel={e => { e.preventDefault(); if (!busy) onClose(); }}><div className="manage-section-heading"><h2 id="manage-dialog-title">{action.label}</h2><button className="manage-button secondary" onClick={onClose} disabled={busy} aria-label="بستن پنجره">بستن</button></div><p className="manage-muted">رکورد: <bdi className="manage-dialog-id">{action.object_id}</bdi></p>
    {error && <Failure message={error} />}
    {texts ? <div className="manage-report"><span className="manage-badge">فقط مدیریت · {texts.mode === "ollama" ? "Ollama" : texts.mode === "gapgpt" ? "GapGPT" : "متن آماده"}</span><h3>متن اولیهٔ کاربر</h3><p>{texts.original_available ? texts.original_text : "متن اولیه برای این سابقه موجود نیست؛ ممکن است قدیمی یا پاک‌سازی‌شده باشد."}</p><h3>متن نهایی بررسی‌شده</h3><p>{texts.final_text || "متن طبق سیاست نگهداری حذف شده است."}</p><p className="manage-muted">مشاهدهٔ متن‌ها در سوابق مدیریت ثبت شد.</p></div> : report ? <div className="manage-report"><span className="manage-badge">{managementState(report.status)}</span><h3>موضوع گزارش</h3><p>{report.reason}</p><h3>توضیحات دریافت‌کننده</h3><p>{report.details || "توضیحی ثبت نشده است."}</p><h3>متن بررسی‌شدهٔ مرتبط</h3><p>{report.reviewed_text}</p><p className="manage-muted">مشاهدهٔ این پرونده در سوابق مدیریت ثبت شد.</p></div> : <form className="manage-form" onSubmit={submit}>
      {action.name === 'account_limits' && <fieldset disabled={busy} className="manage-fieldset">
        <p className="manage-notice">تنظیم فقط برای همین حساب است. تعداد نامحدود، اعتبار پیام یا کنترل‌های محتوا، گیرنده و سقف کل بازنویسی را حذف نمی‌کند؛ مصرف قبلی هم پاک نمی‌شود.</p>
        <AccountLimitInput name="sender_daily_limit" label="ارسال در ۲۴ ساعت" value={action.accountLimits?.sender_daily_limit ?? null} />
        <AccountLimitInput name="rewrite_daily_limit" label="بازنویسی در روز" value={action.accountLimits?.rewrite_daily_limit ?? null} />
      </fieldset>}
      {action.name === "confirm_refund" && <><p className="manage-notice">ابتدا بازپرداخت را خارج از سایت انجام دهید؛ این اقدام فقط ثبت سند بازپرداخت است.</p><label>مرجع سند بازپرداخت<input name="reference" minLength={3} maxLength={100} required /></label></>}
      <label>دلیل {action.name === "message_texts" ? "مشاهدهٔ متن‌ها" : action.name === "review" ? "مشاهدهٔ پرونده" : "اقدام"}<textarea name="reason" minLength={3} maxLength={200} rows={3} required placeholder="دلیل کوتاه؛ شماره یا اطلاعات خصوصی ننویسید" autoFocus /></label>
      <button className="manage-button primary" disabled={busy}>{busy ? "در حال ثبت…" : action.name === "message_texts" ? "ثبت مشاهده و نمایش متن‌ها" : action.name === "review" ? "ثبت مشاهده و بازکردن پرونده" : "تأیید و ثبت اقدام"}</button>
    </form>}
  </dialog>;
}

function AccountLimitInput({ name, label, value }: { name: string; label: string; value: number | null }) {
  const [mode, setMode] = useState(value === null ? 'site' : value === 0 ? 'unlimited' : 'custom');
  return <div className="manage-settings-grid"><label>{label}<select name={`${name}_mode`} value={mode} onChange={event => setMode(event.target.value)}>
    <option value="site">طبق تنظیم سایت</option><option value="custom">عدد اختصاصی</option><option value="unlimited">تعداد نامحدود</option>
  </select></label>{mode === 'custom' && <label>حداکثر {label}<DigitInput name={name} type="number" min={1} max={1000000} step={1} defaultValue={value || 1000} required /></label>}</div>;
}
