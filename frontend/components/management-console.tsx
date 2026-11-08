"use client";

import { ManagementButton, ManagementInput, ManagementSelect, ManagementDigitInput, ManagementDialog } from "./management-ui";



import Link from "next/link";
import Card from '@mui/material/Card';
import Alert from '@mui/material/Alert';
import CircularProgress from '@mui/material/CircularProgress';
import Table from '@mui/material/Table';
import TableHead from '@mui/material/TableHead';
import TableBody from '@mui/material/TableBody';
import TableRow from '@mui/material/TableRow';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import IconButton from '@mui/material/IconButton';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import { usePathname, useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useId, useRef, useState } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import { managementActions, managementDate, managementNumber, managementState, managementNavigation, managementRoute, managementHref, managementUserHref, managementReason,
  managementExplanation, managementDisplayValue, type LimitRule, type LimitSettings, type ManagementAction, type ManagementDashboard,
  type ManagementRecords, type ManagementSession, type ManagementActivity, type ManagementRow } from "@/lib/management";
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
  return <Alert severity="error" className="manage-error"><span>{message}</span>{retry && <ManagementButton className="manage-button secondary" onClick={retry}>تلاش دوباره</ManagementButton>}</Alert>;
}
function Loading() { return <div className="manage-loading" role="status"><CircularProgress size={22} aria-hidden="true" /> در حال دریافت اطلاعات…</div>; }

export function ManagementConsole({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const route = managementRoute(pathname);
  const [session, setSession] = useState<ManagementSession | null>(null);
  const [error, setError] = useState("");
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
    if (e instanceof ApiError && e.code === "management_login_required") { supportMemory.current={thread:null,composer:{draft:"",pending:null}}; supportIdentity.current=undefined; setSession({ authenticated: false }); }
  }, []);
  async function signOut() {
    setBusy(true); setError("");
    try { await api("/manage/logout", { method: "POST", body: {} }); supportMemory.current={thread:null,composer:{draft:"",pending:null}}; supportIdentity.current=undefined; setSession({ authenticated: false }); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  const supportFailure = useCallback((e:unknown) => { failed(e); if(e instanceof ApiError && e.code === 'forbidden') setSession({authenticated:false}); },[failed]);
  const supportCount = useSupportBadge(!!session?.authenticated,supportFailure);
  const permissions = session?.permissions || [];
  const navigation = managementNavigation(session || { authenticated: false });
  const active = route.resource;
  const allowed = navigation.some(item => item.key === active) || session?.resources?.some(item => item.key === active);
  const title = route.userId ? "پروندهٔ کاربر" : navigation.find(item => item.key === active)?.title || session?.resources?.find(item => item.key === active)?.title || "مدیریت";
  useEffect(() => { setMenu(false); setAction(null); }, [pathname]);
  return <div className="manage-app" data-update-blocked="true">
    {!session || !session.authenticated ? <div className="manage-login-wrap"><Brand />
      <Card component="section" className="manage-login"><span className="manage-kicker"><Icon name="shield" size={19} /> پنل مدیریت</span><h1>مدیریت بگم نگم</h1>
        <p>با نام کاربری و رمز حساب مدیر وارد شوید.</p>
        {error && <Failure message={error} retry={() => void loadSession()} />}
        {!session ? <Loading /> : <Login onLogin={current => { if (supportIdentity.current !== current.session_identity) supportMemory.current={thread:null,composer:{draft:"",pending:null}}; supportIdentity.current=current.session_identity; setSession(current); }} />}
        <Link href="/" className="manage-site-link">مشاهدهٔ سایت</Link>
      </Card></div> : <>
      <aside className={`manage-sidebar ${menu ? "is-open" : ""}`}>
        <Brand /><span className="manage-kicker">مدیریت محصول</span>
        <List component="nav" id="manage-navigation" aria-label="بخش‌های مدیریت">{navigation.map(item => <ListItemButton component={Link} selected={active === item.key} key={item.key} href={managementHref(item.key)} aria-current={active === item.key ? "page" : undefined} onClick={() => setMenu(false)}>{item.title}{item.key === "support" && supportCount>0 && <span className={supportStyles.navBadge} aria-label={`${supportCount.toLocaleString("fa-IR")} گفت‌وگوی نیازمند توجه`}>{supportCount.toLocaleString("fa-IR")}</span>}</ListItemButton>)}</List>
        <a className="manage-advanced" href="/admin/">مدیریت پیشرفتهٔ جنگو ↗</a>
      </aside>
      <div className="manage-workspace">
        <header className="manage-topbar"><div className="manage-heading"><ManagementButton className="manage-button secondary manage-menu" aria-expanded={menu} aria-controls="manage-navigation" onClick={() => setMenu(!menu)}>{menu ? "بستن منو" : "بخش‌ها"}</ManagementButton><h1>{title}</h1></div>
          <div className="manage-session"><span><Icon name="user" size={17} /><bdi>{session.username}</bdi></span><Link href="/" className="manage-button secondary">سایت</Link><ManagementButton className="manage-button secondary" disabled={busy} onClick={() => void signOut()}>خروج</ManagementButton></div>
        </header>
        {permissions.includes("view_operations") && <ProviderBalances onFailure={failed} />}
        <span className="sr-only" role="status" aria-atomic="true">{supportCount>0 ? `${supportCount.toLocaleString("fa-IR")} گفت‌وگوی پشتیبانی تازه یا بی‌پاسخ داری.` : ""}</span>
        <div className="manage-content">{error && <Failure message={error} />}
          {!allowed && <Card component="section" className="manage-card"><p>این بخش برای حساب شما در دسترس نیست. از فهرست بخش‌های مجاز انتخاب کنید.</p></Card>}
          {allowed && (route.userId ? <UserActivity key={`${route.userId}-${epoch}`} userId={route.userId} permissions={permissions} resources={session.resources || []} onAction={setAction} onFailure={failed} /> : active === "examples" ? <ExampleSettings onFailure={failed} /> : active === "support" ? <SupportInbox onFailure={supportFailure} memory={supportMemory} /> : active === "dashboard" ? <Dashboard key={`dashboard-${epoch}`} canOperate={permissions.includes("operate_safety")} onAction={setAction} onFailure={failed} /> : active === "limits" ? <Limits onFailure={failed} /> : active === "ai" ? <AISettings onFailure={failed} /> : active === "manual-settings" ? <ManualPaymentSettings onFailure={failed} /> : active === "packages" ? <PackageSettings onFailure={failed} /> : active && <Records key={`${active}-${epoch}`} resource={active} permissions={permissions} onAction={setAction} onFailure={failed} />)}
          {children}
          <p className="manage-footnote">زمان‌ها به وقت تهران · اقدام‌های مدیریتی در سابقه ثبت می‌شوند.</p>
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
    <label>نام کاربری<ManagementInput name="username" autoComplete="username" dir="ltr" maxLength={150} required /></label>
    <label>رمز عبور<ManagementInput name="password" type="password" autoComplete="current-password" dir="ltr" maxLength={512} required /></label>
    <ManagementButton className="manage-button primary" disabled={busy}>{busy ? "در حال ورود…" : "ورود به مدیریت"}</ManagementButton>
  </form>;
}

function Dashboard({ canOperate, onAction, onFailure }: { canOperate: boolean; onAction: (a: ManagementAction) => void; onFailure: (e: unknown) => void }) {
  const [data, setData] = useState<ManagementDashboard | null>(null), [error, setError] = useState("");
  const load = useCallback(async () => { setError(""); try { setData(await api<ManagementDashboard>("/manage/dashboard")); } catch (e) { setError(errorMessage(e)); onFailure(e); } }, [onFailure]);
  useEffect(() => { void load(); }, [load]);
  if (!data) return error ? <Failure message={error} retry={() => void load()} /> : <Loading />;
  const totals: [string, string][] = [["accounts", "حساب کاربری"], ["orders", "درخواست پیام"], ["delivered", "پیامک رسیده"], ["invitations", "دعوت ثبت‌شده"], ["registered_invitations", "عضویت با دعوت"], ["active_alerts", "هشدار فعال"]];
  const metrics: [string, string][] = [["outbox_pending", "در انتظار ارسال"], ["delivery_unknown", "تحویل نیازمند تطبیق"], ["payment_unknown", "پرداخت نیازمند تطبیق"], ["refund_open", "بازپرداخت باز"], ["reports_open", "گزارش باز"], ["oldest_queue_seconds", "عمر قدیمی‌ترین صف (ثانیه)"]];
  return <><div className="manage-section-heading"><div><p className="manage-kicker">وضعیت فعلی محصول</p><h2>آنچه در سایت می‌گذرد</h2></div><ManagementButton className="manage-button secondary" onClick={() => void load()}>تازه‌سازی</ManagementButton></div>
    {error && <Failure message={error} />}
    <div className="manage-stats">{totals.map(([key, label]) => <article className="manage-stat" key={key}><span>{label}</span><strong>{managementNumber(data.totals[key])}</strong></article>)}</div>
    <Card component="section" className="manage-card"><div className="manage-section-heading"><h2>ارسال و صف پردازش</h2><span className={`manage-badge ${data.operations.sending_halted ? "warn" : "good"}`}>{data.operations.sending_halted ? "ارسال متوقف است" : "ارسال باز است"}</span></div>
      <div className="manage-metrics">{metrics.map(([key, label]) => <div key={key}><span>{label}</span><strong>{managementNumber(data.operations[key])}</strong></div>)}</div>
      {canOperate && <ManagementButton className={`manage-button ${data.operations.sending_halted ? "primary" : "danger"}`} onClick={() => onAction({ name: data.operations.sending_halted ? "resume" : "halt", label: data.operations.sending_halted ? "ازسرگیری ارسال" : "توقف ارسال جدید", object_id: "global" })}>{data.operations.sending_halted ? "ازسرگیری ارسال" : "توقف ارسال جدید"}</ManagementButton>}
    </Card>
    <div className="manage-two-columns"><Card component="section" className="manage-card"><h2>اتصال سرویس‌ها</h2><dl className="manage-definition"><div><dt>محیط</dt><dd>{data.environment.demo ? "آزمایشی" : "واقعی"}</dd></div><div><dt>پیامک</dt><dd><>{String(managementDisplayValue("provider", data.environment.sms))}</></dd></div><div><dt>کد ورود</dt><dd><>{String(managementDisplayValue("provider", data.environment.otp))}</></dd></div><div><dt>پرداخت پولی</dt><dd>{data.environment.paid_enabled ? "فعال" : "بسته"}</dd></div></dl></Card>
      <Card component="section" className="manage-card manage-budget"><h2>دفتر هزینهٔ پیامک</h2><p>رزرو ثبت‌شدهٔ امروز</p><strong>{managementNumber(data.operations.provider_budget_reserved_rial)} <small>ریال</small></strong><p>سقف روزانه: {data.operations.provider_budget_unlimited ? "بدون سقف" : `${managementNumber(data.operations.provider_budget_limit_rial)} ریال`}</p><small>رزرو هزینه با صورتحساب قطعی سرویس پیامک یکسان نیست.</small></Card></div>
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
  return <Card component="section" className="manage-card manage-records"><form className="manage-search" onSubmit={search}>
    <label>جست‌وجو<ManagementInput name="query" maxLength={100} aria-describedby={resource === "accounts" ? "manage-phone-search-help" : undefined} placeholder={resource === "accounts" || resource === "invitations" || resource === "blacklist" ? "همه یا بخشی از شماره موبایل یا شناسه" : "شناسه، وضعیت یا کد"} /></label>
    {!!data?.statuses.length && <label>وضعیت<ManagementSelect name="status" defaultValue=""><option value="">همهٔ وضعیت‌ها</option>{data.statuses.map(([key, label]) => <option key={key} value={key}>{managementState(key)}</option>)}</ManagementSelect></label>}
    <ManagementButton className="manage-button primary" disabled={busy}>جست‌وجو</ManagementButton><ManagementButton className="manage-button secondary" type="button" disabled={busy} onClick={() => setFilter(v => ({ ...v }))}>تازه‌سازی</ManagementButton>
  </form>
    {resource === "blacklist" && <p className="manage-muted">فقط لغو دریافتِ فعال نمایش داده می‌شود؛ بازکردن لینک به‌تنهایی لغو نیست. این فهرست شامل شماره‌های بدون حساب هم هست و امکان فعال‌کردن دریافت از اینجا وجود ندارد.</p>}
    {resource === "accounts" && <p id="manage-phone-search-help" className="manage-muted">شمارهٔ کامل یا بخشی از آن را وارد کنید؛ ارقام فارسی و لاتین پذیرفته می‌شوند.</p>}
    {error && <Failure message={error} retry={() => setFilter(v => ({ ...v }))} />}
    {busy && <Loading />}
    {data && !busy && !error && <><div className="manage-table-info"><span>{managementNumber(data.total)} رکورد</span><span>صفحهٔ {managementNumber(data.page)} از {managementNumber(pages)}</span></div>
      {!data.rows.length ? <div className="manage-empty"><Icon name="receipt" size={32} /><h2>رکوردی پیدا نشد</h2><p>پس از ثبت فعالیت، اطلاعات این بخش نمایش داده می‌شود.</p></div> : <TableContainer className="manage-table-scroll" tabIndex={0} role="region" aria-label={data.title}><Table size="small"><caption className="sr-only">{data.title}</caption><TableHead><TableRow>{data.columns.map(col => <TableCell component="th" scope="col" key={col.key}>{col.label}</TableCell>)}{(resource === "accounts" || data.rows.some(row => managementActions(resource, row, permissions).length > 0)) && <TableCell component="th" scope="col" className="manage-action-column">عملیات</TableCell>}</TableRow></TableHead><TableBody>{data.rows.map(row => <TableRow key={row.record_id}>{data.columns.map(col => <TableCell key={col.key}>{resource === "accounts" && ["id", "phone"].includes(col.key) ? <Link className="manage-record-link" href={managementUserHref(row.record_id)}><Cell value={managementDisplayValue(col.key, row[col.key])} kind={col.type} /></Link> : <Cell value={managementDisplayValue(col.key, row[col.key])} kind={col.type} />}</TableCell>)}{(resource === "accounts" || data.rows.some(r => managementActions(resource, r, permissions).length > 0)) && <TableCell className="manage-action-column"><RowActions resource={resource} row={row} permissions={permissions} onAction={onAction} /></TableCell>}</TableRow>)}</TableBody></Table></TableContainer>}
      <nav className="manage-pagination" aria-label="صفحه‌بندی رکوردها"><ManagementButton className="manage-button secondary" disabled={filter.page <= 1} onClick={() => setFilter(v => ({ ...v, page: v.page - 1 }))}>صفحهٔ قبل</ManagementButton><ManagementButton className="manage-button secondary" disabled={filter.page >= pages} onClick={() => setFilter(v => ({ ...v, page: v.page + 1 }))}>صفحهٔ بعد</ManagementButton></nav>
    </>}
  </Card>;
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
    try { const updated = await api<LimitSettings>("/manage/limits", { method: "POST", body: { values, revision: data.revision, reason: managementReason("limits") } }); onSaved(updated); setMessage("تنظیمات ذخیره شد."); }
    catch (e) { setError(errorMessage(e)); if (e instanceof ApiError) setFields(e.fields || {}); onFailure(e); }
    finally { setBusy(false); }
  }
  return <form className="manage-card manage-form" onSubmit={save}><div className="manage-section-heading"><h2>تنظیمات مشترک سایت</h2><span className="manage-muted">نسخهٔ {managementNumber(data.revision)}</span></div>
    {error && <Failure message={error} />}{message && <p className="manage-success" role="status">{message}</p>}
    {fields.__all__ && <Failure message={String(fields.__all__)} />}
    <fieldset disabled={busy} className="manage-fieldset">{data.sections.map((section, i) => <details className="manage-settings-section" key={section.title} open={i < 2}><summary>{section.title}</summary><div className="manage-settings-grid">{section.fields.map(field => <label key={field.key} className={field.type === "bool" ? "manage-checkbox" : ""} htmlFor={`limit-${field.key}`}>
      <span>{field.label}</span>{field.type === "bool" ? <ManagementInput id={`limit-${field.key}`} name={field.key} type="checkbox" role={["wallet_enabled","gateway_enabled"].includes(field.key) ? "switch" : undefined} defaultChecked={Boolean(data.values[field.key])} aria-invalid={!!fields[field.key]} aria-describedby={field.help || fields[field.key] ? `help-${field.key}` : undefined} /> : <ManagementDigitInput id={`limit-${field.key}`} name={field.key} type="number" min={field.min ?? 0} step={1} max={field.max ?? Number.MAX_SAFE_INTEGER} defaultValue={Number(data.values[field.key])} required aria-invalid={!!fields[field.key]} aria-describedby={field.help || fields[field.key] ? `help-${field.key}` : undefined} />}
      {(field.help || fields[field.key]) && <small id={`help-${field.key}`} className={fields[field.key] ? "manage-field-error" : ""}>{fields[field.key] ? String(fields[field.key]) : field.help}</small>}
    </label>)}</div></details>)}

      <div className="manage-form-actions"><ManagementButton className="manage-button primary">{busy ? "در حال ذخیره…" : "ذخیرهٔ تنظیمات"}</ManagementButton><ManagementButton type="button" className="manage-button secondary" onClick={() => window.location.reload()}>دریافت آخرین تنظیمات</ManagementButton></div>
    </fieldset>
  </form>;
}

function RequestLimits({ rules, onSaved, onFailure }: { rules: LimitRule[]; onSaved: (d: LimitSettings) => void; onFailure: (e: unknown) => void }) {
  const [scope, setScope] = useState(rules[0]?.scope || "");
  return <Card component="section" className="manage-card"><h2>کنترل تعداد درخواست‌ها</h2><p className="manage-muted">کنترل ورود مدیر، حدس کد، لینک خصوصی، شارژ کیف پول و بازگشت پرداخت باید فعال بماند. مقدار تعداد و بازه قابل تنظیم است.</p><label className="manage-rule-picker">نوع درخواست<ManagementSelect value={scope} onChange={e => setScope(e.target.value)}>{rules.map(rule => <option key={rule.scope} value={rule.scope}>{rule.label} · {rule.enabled ? "فعال" : "بدون سقف"}</option>)}</ManagementSelect></label>{rules.find(rule => rule.scope === scope) && <RequestRule key={`${scope}:${rules.find(rule => rule.scope === scope)!.revision}`} rule={rules.find(rule => rule.scope === scope)!} onSaved={onSaved} onFailure={onFailure} />}</Card>;
}

function RequestRule({ rule, onSaved, onFailure }: { rule: LimitRule; onSaved: (d: LimitSettings) => void; onFailure: (e: unknown) => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError("");
    try { onSaved(await api<LimitSettings>(`/manage/request-limits/${rule.scope}`, { method: "POST", body: { revision: rule.revision, reason: managementReason("request_limits"), values: { enabled: rule.protected || form.get("enabled") === "on", maximum: Number(form.get("maximum")), window_seconds: Number(form.get("window_seconds")) } } })); }
    catch (e) { setError(errorMessage(e)); onFailure(e); } finally { setBusy(false); }
  }
  return <form className="manage-form" onSubmit={save}>{error && <Failure message={error} />}<fieldset className="manage-fieldset" disabled={busy}><label className="manage-checkbox"><span>کنترل فعال باشد</span><ManagementInput name="enabled" type="checkbox" defaultChecked={rule.enabled} disabled={rule.protected} /></label><div className="manage-settings-grid"><label>حداکثر تعداد<ManagementDigitInput name="maximum" type="number" min={1} step={1} defaultValue={rule.maximum} required /></label><label>بازه (ثانیه)<ManagementDigitInput name="window_seconds" type="number" min={1} step={1} defaultValue={rule.window_seconds} required /></label></div><ManagementButton className="manage-button primary">{busy ? "در حال ذخیره…" : "ذخیرهٔ این کنترل"}</ManagementButton></fieldset></form>;
}

function ActionDialog({ action, onClose, onComplete, onFailure }: { action: ManagementAction; onClose: () => void; onComplete: () => void; onFailure: (e: unknown) => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [report, setReport] = useState<{ details: string; reviewed_text: string; reason: string; status: string } | null>(null);
  const [texts, setTexts] = useState<{ original_text: string; original_available: boolean; final_text: string; mode: string } | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError("");
    try {
      const countValues = Object.fromEntries(['sender_daily_limit', 'rewrite_daily_limit'].map(key => [key,
        form.get(`${key}_mode`) === 'site' ? null : form.get(`${key}_mode`) === 'unlimited' ? 0 : Number(form.get(key))]));
      const values = { action: action.name, object_id: action.object_id, value: action.value, reason: managementReason(action.name), reference: form.get("reference") || "",
        ...(action.name === 'account_limits' ? { values: countValues } : {}) };
      if (action.name === "review") setReport(await api(`/manage/reports/${action.object_id}/review`, { method: "POST", body: values }));
      else if (action.name === "attempt_texts") { const result = await api<{ original_text: string; original_available?: boolean; reviewed_text: string | null }>(`/manage/users/${action.userId}/attempts/${action.object_id}/texts`, { method: "POST", body: values }); setTexts({ original_text: result.original_text, original_available: result.original_available ?? !!result.original_text, final_text: result.reviewed_text || "", mode: "attempt" }); }
      else if (action.name === "message_texts") setTexts(await api(`/manage/orders/${action.object_id}/texts`, { method: "POST", body: values }));
      else { await api("/manage/actions", { method: "POST", body: values }); onComplete(); }
    } catch (e) { setError(errorMessage(e)); onFailure(e); } finally { setBusy(false); }
  }
  return <ManagementDialog title={action.label} onClose={onClose} busy={busy}><p className="manage-muted">رکورد: <bdi className="manage-dialog-id">{action.object_id}</bdi></p>
    {error && <Failure message={error} />}
    {texts ? <div className="manage-report"><span className="manage-badge">فقط مدیریت · {texts.mode === "ollama" ? "Ollama" : texts.mode === "gapgpt" ? "GapGPT" : texts.mode === "attempt" ? "تلاش ساخت پیام" : "متن آماده"}</span><h3>متن اولیهٔ کاربر</h3><p>{texts.original_available ? texts.original_text : "متن اولیه برای این سابقه موجود نیست؛ ممکن است قدیمی یا پاک‌سازی‌شده باشد."}</p><h3>متن نهایی بررسی‌شده</h3><p>{texts.final_text || (texts.mode === "attempt" ? "متن نهایی تأییدشده‌ای برای این سابقه موجود نیست." : "متن طبق سیاست نگهداری حذف شده است.")}</p><p className="manage-muted">مشاهدهٔ متن‌ها در سوابق مدیریت ثبت شد.</p></div> : report ? <div className="manage-report"><span className="manage-badge">{managementState(report.status)}</span><h3>موضوع گزارش</h3><p>{report.reason}</p><h3>توضیحات دریافت‌کننده</h3><p>{report.details || "توضیحی ثبت نشده است."}</p><h3>متن بررسی‌شدهٔ مرتبط</h3><p>{report.reviewed_text}</p><p className="manage-muted">مشاهدهٔ این پرونده در سوابق مدیریت ثبت شد.</p></div> : <form className="manage-form" onSubmit={submit}>
      {action.name === 'free_sending' && <p className="manage-notice">{action.value ? 'این حساب بدون مصرف هدیه یا اعتبار بسته ارسال می‌کند و هزینهٔ واقعی بر عهدهٔ سرویس است.' : 'ارسال‌های بعدی از هدیه و اعتبار بسته مصرف می‌کنند؛ سفارش‌های قبلی تغییر نمی‌کنند.'} سقف روزانه، کنترل گیرنده و محتوا مستقل‌اند.</p>}
      {action.name === 'account_limits' && <fieldset disabled={busy} className="manage-fieldset">
        <p className="manage-notice">تنظیم فقط برای همین حساب است. تعداد نامحدود، اعتبار پیام یا کنترل‌های محتوا، گیرنده و سقف کل بازنویسی را حذف نمی‌کند؛ مصرف قبلی هم پاک نمی‌شود.</p>
        <AccountLimitInput name="sender_daily_limit" label="سقف تعداد ارسال در ۲۴ ساعت؛ بدون افزایش اعتبار" value={action.accountLimits?.sender_daily_limit ?? null} />
        <AccountLimitInput name="rewrite_daily_limit" label="بازنویسی در روز" value={action.accountLimits?.rewrite_daily_limit ?? null} />
      </fieldset>}
      {action.name === "confirm_refund" && <><p className="manage-notice">ابتدا بازپرداخت را خارج از سایت انجام دهید؛ این اقدام فقط ثبت سند بازپرداخت است.</p><label>مرجع سند بازپرداخت<ManagementInput name="reference" minLength={3} maxLength={100} required /></label></>}
      <ManagementButton className="manage-button primary" disabled={busy}>{busy ? "در حال ثبت…" : ["message_texts", "attempt_texts"].includes(action.name) ? "ثبت مشاهده و نمایش متن‌ها" : action.name === "review" ? "ثبت مشاهده و بازکردن پرونده" : "تأیید و ثبت اقدام"}</ManagementButton>
    </form>}
  </ManagementDialog>;
}

function AccountLimitInput({ name, label, value }: { name: string; label: string; value: number | null }) {
  const [mode, setMode] = useState(value === null ? 'site' : value === 0 ? 'unlimited' : 'custom');
  return <div className="manage-settings-grid"><label>{label}<ManagementSelect name={`${name}_mode`} value={mode} onChange={event => setMode(event.target.value)}>
    <option value="site">طبق تنظیم سایت</option><option value="custom">عدد اختصاصی</option><option value="unlimited">تعداد نامحدود</option>
  </ManagementSelect></label>{mode === 'custom' && <label>حداکثر {label}<ManagementDigitInput name={name} type="number" min={1} max={1000000} step={1} defaultValue={value || 1000} required /></label>}</div>;
}

function RowActions({ resource, row, permissions, onAction }: { resource: string; row: ManagementRow; permissions: string[]; onAction: (a: ManagementAction) => void }) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const id = useId();
  const actions = managementActions(resource, row, permissions);
  if (resource !== "accounts" && !actions.length) return null;
  const close = () => setAnchor(null);
  return <>
    <IconButton id={`${id}-button`} aria-label={`عملیات رکورد ${row.record_id}`} aria-haspopup="menu" aria-expanded={!!anchor} aria-controls={anchor ? `${id}-menu` : undefined} onClick={event => setAnchor(event.currentTarget)} className="manage-row-trigger">
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>
    </IconButton>
    <Menu id={`${id}-menu`} dir="rtl" anchorEl={anchor} open={!!anchor} onClose={close} anchorOrigin={{vertical:'bottom',horizontal:'left'}} transformOrigin={{vertical:'top',horizontal:'left'}} slotProps={{list:{'aria-labelledby':`${id}-button`}}}>
      {resource === "accounts" && [
        <MenuItem key="profile" component={Link} href={managementUserHref(row.record_id)} onClick={close}>پروندهٔ کاربر</MenuItem>,
        <MenuItem key="messages" component={Link} href={managementUserHref(row.record_id, "messages")} onClick={close}>پیام‌های کاربر</MenuItem>,
        <MenuItem key="invitations" component={Link} href={managementUserHref(row.record_id, "invitations")} onClick={close}>دعوت‌های کاربر</MenuItem>,
      ]}
      {actions.map(item => <MenuItem key={item.name} onClick={() => { close(); onAction(item); }}>{item.label}</MenuItem>)}
    </Menu>
  </>;
}

function UserActivity({ userId, permissions, resources, onAction, onFailure }: {
  userId: string; permissions: string[]; resources: { key: string; title: string }[];
  onAction: (a: ManagementAction) => void; onFailure: (e: unknown) => void;
}) {
  const searchParams = useSearchParams();
  const section = searchParams.get("section") === "invitations" ? "invitations" : searchParams.get("section") === "messages" || resources.some(item => item.key === "orders") ? "messages" : "invitations";
  const requestedPage = Number(searchParams.get("page"));
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const [data, setData] = useState<ManagementActivity | null>(null);
  const [account, setAccount] = useState<ManagementActivity["account"] | null>(null);
  const [error, setError] = useState(""), [busy, setBusy] = useState(true), [epoch, setEpoch] = useState(0);
  const canRead = resources.some(item => item.key === (section === "messages" ? "orders" : "invitations"));
  useEffect(() => {
    const controller = new AbortController();
    void api<{ account: ManagementActivity["account"] }>(`/manage/users/${userId}`, { signal: controller.signal }).then(result => setAccount(result.account)).catch(e => { if (!controller.signal.aborted) { setError(errorMessage(e)); onFailure(e); } });
    return () => controller.abort();
  }, [userId, epoch, onFailure]);
  useEffect(() => {
    const controller = new AbortController(); setError(""); setData(null); setBusy(canRead);
    if (canRead) void api<ManagementActivity>(`/manage/users/${userId}/activity`, { method: "POST", body: { section, page }, signal: controller.signal })
      .then(result => { setData(result); setAccount(result.account); }).catch(e => { if (!controller.signal.aborted) { setError(errorMessage(e)); onFailure(e); } })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [userId, section, page, canRead, epoch, onFailure]);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const kinds: Record<string, string> = { order: "سفارش پیام", attempt: "تلاش ساخت پیام", moderation: "بررسی محتوای قدیمی", invitation: "دعوت" };
  const pageHref = (number: number) => `${managementUserHref(userId, section)}&page=${number}`;
  return <>
    <Link className="manage-record-link" href="/manage/users">بازگشت به کاربران</Link>
    <Card component="section" className="manage-card"><div className="manage-section-heading"><div><p className="manage-kicker">پروندهٔ کاربر</p><h2>{account ? <bdi>{account.phone || account.phone_masked}</bdi> : `کاربر ${Number(userId).toLocaleString("fa-IR")}`}</h2></div><ManagementButton className="manage-button secondary" disabled={busy} onClick={() => setEpoch(value => value + 1)}>تازه‌سازی</ManagementButton></div>
      {account && <p>شناسه: {managementNumber(account.id)} · <span className={`manage-badge ${account.suspended ? "warn" : "good"}`}>{account.suspended ? "تعلیق‌شده" : "فعال"}</span></p>}
      <Tabs value={canRead ? section : false} aria-label="فعالیت کاربر">{([{ key: "messages", resource: "orders", title: "پیام‌ها" }, { key: "invitations", resource: "invitations", title: "دعوت‌ها" }] as const).filter(tab => resources.some(item => item.key === tab.resource)).map(tab => <Tab component={Link} key={tab.key} value={tab.key} label={tab.title} href={managementUserHref(userId, tab.key)} />)}</Tabs>
    </Card>
    {error && <Failure message={error} retry={() => setEpoch(value => value + 1)} />}
    {!canRead && <p className="manage-notice">مجوز مشاهدهٔ این فعالیت را ندارید. از بخش‌های مجاز پرونده انتخاب کنید.</p>}
    {busy && <Loading />}
    {data && !busy && !error && <Card component="section" className="manage-card"><div className="manage-table-info"><span>{managementNumber(data.total)} رکورد</span><span>صفحهٔ {managementNumber(data.page)} از {managementNumber(pages)}</span></div>
      {!data.rows.length ? <p className="manage-empty">فعالیتی در این بخش ثبت نشده است.</p> : <div className="manage-activity-list">{data.rows.map(row => <article key={`${row.kind}-${row.record_id}`}>
        <div className="manage-section-heading"><strong>{kinds[row.kind] || row.kind}</strong><span className="manage-badge">{managementState(row.status)}</span></div>
        <p className="manage-muted">{managementDate(row.created_at)}</p>
        {row.phone && <p>مخاطب: <bdi>{row.phone}</bdi></p>}
        {row.reason_code && <p>علت: {managementExplanation(row.reason_code)}</p>}
        {row.kind === "invitation" && <><p>ثبت‌نام مخاطب: {row.registered_at ? managementDate(row.registered_at) : "هنوز ثبت‌نام نکرده است"}</p><p>جایزهٔ دعوت: {row.reward_awarded_at ? managementDate(row.reward_awarded_at) : "ثبت نشده است"}</p></>}
        {row.kind === "moderation" && <p className="manage-muted">این سابقه فقط اطلاعات بررسی محتوا دارد.</p>}
        <details><summary>شناسهٔ سابقه</summary><bdi className="manage-dialog-id">{row.id}</bdi></details>
        {permissions.includes("view_private_message_text") && ["order", "attempt"].includes(row.kind) && <ManagementButton className="manage-button secondary" onClick={() => onAction({ name: row.kind === "order" ? "message_texts" : "attempt_texts", label: "مشاهدهٔ متن‌ها", object_id: String(row.kind === "order" ? row.order_id || row.id : row.id), userId })}>مشاهدهٔ متن‌ها</ManagementButton>}
      </article>)}</div>}
      <nav className="manage-pagination" aria-label="صفحه‌بندی فعالیت کاربر">{page > 1 && <Link className="manage-button secondary" href={pageHref(page - 1)}>صفحهٔ قبل</Link>}{page < pages && <Link className="manage-button secondary" href={pageHref(page + 1)}>صفحهٔ بعد</Link>}</nav>
    </Card>}
  </>;
}
