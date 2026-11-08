"use client";

import dynamic from 'next/dynamic';
import Link from 'next/link';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import Card from '@mui/material/Card';
import Alert from '@mui/material/Alert';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import FormControlLabel from '@mui/material/FormControlLabel';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import RefreshRounded from '@mui/icons-material/RefreshRounded';
import SearchRounded from '@mui/icons-material/SearchRounded';
import SaveOutlined from '@mui/icons-material/SaveOutlined';
import LoginRounded from '@mui/icons-material/LoginRounded';
import ShieldOutlined from '@mui/icons-material/ShieldOutlined';
import MoreHorizRounded from '@mui/icons-material/MoreHorizRounded';
import VisibilityOutlined from '@mui/icons-material/VisibilityOutlined';
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded';
import ArrowForwardRounded from '@mui/icons-material/ArrowForwardRounded';
import ArrowBackRounded from '@mui/icons-material/ArrowBackRounded';
import ReceiptLongOutlined from '@mui/icons-material/ReceiptLongOutlined';
import CheckCircleOutline from '@mui/icons-material/CheckCircleOutlined';
import HistoryOutlined from '@mui/icons-material/HistoryOutlined';
import MailOutlineRounded from '@mui/icons-material/MailOutlineRounded';
import SettingsOutlined from '@mui/icons-material/SettingsOutlined';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { api, ApiError, errorMessage } from '@/lib/api';
import { managementActions, managementDate, managementNumber, managementState, managementNavigation, managementRoute, managementUserHref, managementReason, managementExplanation, managementDisplayValue, managementShowsBalances, managementGridPage, managementLanding,
 type LimitRule, type LimitSettings, type ManagementAction, type ManagementDashboard, type ManagementRecords, type ManagementSession, type ManagementActivity, type ManagementRow } from '@/lib/management';
import type { SupportWorkspaceMemory } from '@/lib/support';
import { ManagementButton, ManagementInput, ManagementSelect, ManagementDigitInput, ManagementDialog } from './management-ui';
import { ManagementMonitoringLayout } from './management-monitoring-layout';
import { ManagementFrame, ManagementBrand } from './management-frame';
import { ManagementIcon } from './management-icons';
import { ProviderBalances } from './provider-balances';
import { AISettings } from './ai-settings';
import { ManualPaymentSettings } from './manual-payment-settings';
import { ManualPaymentDialog } from './manual-payment-dialog';
import { SupportInbox, useSupportBadge } from './support-inbox';
import { PackageSettings } from './package-settings';
import { ExampleSettings } from './example-settings';
import { ManagementChangelog } from './management-changelog';
import { ManagementDataGrid } from './management-data-grid';

const ManagementStaff=dynamic(()=>import('./management-staff').then(module=>module.ManagementStaff),{loading:()=> <Loading/>});
const ManagementMonitoring=dynamic(()=>import('./management-monitoring').then(module=>module.ManagementMonitoring),{loading:()=> <Loading/>});
const MonitoringAccessSettings=dynamic(()=>import('./monitoring-access-settings').then(module=>module.MonitoringAccessSettings),{loading:()=> <Loading/>});

function ContentCard({children}: {children:ReactNode}) { return <Card sx={{p:{xs:2,sm:3},minWidth:0}}><Stack spacing={2.5}>{children}</Stack></Card>; }
function SectionTitle({title,icon,action}: {title:string;icon:string;action?:ReactNode}) { return <Stack direction="row" sx={{alignItems:'center',justifyContent:'space-between',gap:1,flexWrap:'wrap'}}><Stack direction="row" spacing={1} sx={{alignItems:'center'}}><ManagementIcon name={icon} color="primary"/><Typography component="h2" variant="h6">{title}</Typography></Stack>{action}</Stack>; }
function Failure({ message, retry }: { message: string; retry?: () => void }) { return <Alert severity="error" action={retry?<Button onClick={retry} startIcon={<RefreshRounded/>}>تلاش دوباره</Button>:undefined}>{message}</Alert>; }
function Loading() { return <Stack direction="row" spacing={1.5} role="status" sx={{p:3,alignItems:'center',justifyContent:'center'}}><CircularProgress size={22} aria-hidden="true"/><Typography color="text.secondary">در حال دریافت اطلاعات…</Typography></Stack>; }
function Empty({message='رکوردی پیدا نشد'}:{message?:string}) {return <Stack spacing={1.5} sx={{alignItems:'center',textAlign:'center',py:5}}><ReceiptLongOutlined color="disabled" sx={{fontSize:36}}/><Typography variant="subtitle1">{message}</Typography></Stack>;}

export function ManagementConsole({ children }: { children: React.ReactNode }) {
  const pathname=usePathname();
  const supportIdentity=useRef<string|undefined>(undefined);
  const supportMemory=useRef<SupportWorkspaceMemory>({thread:null,composer:{draft:'',pending:null}});
  return managementRoute(pathname).resource==='monitoring'?<MonitoringEntry>{children}</MonitoringEntry>:<StaffConsole supportIdentity={supportIdentity} supportMemory={supportMemory}>{children}</StaffConsole>;
}

function MonitoringEntry({children}:{children:ReactNode}) {
  const [allowed,setAllowed]=useState<boolean|null>(null),[error,setError]=useState('');
  const generation=useRef(0);
  const load=useCallback(async()=>{
    const current=++generation.current;
    setAllowed(null);setError('');
    try{
      const result=await api<{allowed:boolean}>('/manage/monitoring/access');
      if(current===generation.current)setAllowed(result.allowed===true);
    }catch(e){if(current===generation.current)setError(errorMessage(e));}
  },[]);
  useEffect(()=>{
    void load();
    const refresh=()=>{void load();};
    const visible=()=>{if(document.visibilityState==='visible')refresh();};
    window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',visible);
    return()=>{generation.current++;window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',visible);};
  },[load]);
  const failed=useCallback(()=>{void load();},[load]);
  return allowed?<ManagementMonitoringLayout><ManagementMonitoring onFailure={failed}/>{children}</ManagementMonitoringLayout>:
    <Stack sx={{maxWidth:500,mx:'auto',px:2,py:{xs:4,sm:7},gap:3}}><ManagementBrand/><ContentCard>
      <Stack direction="row" spacing={1} sx={{alignItems:'center'}}><ShieldOutlined color="primary"/><Typography component="h1" variant="h5">ورود به مانیتورینگ</Typography></Stack>
      {error?<Failure message={error} retry={()=>void load()}/>:allowed===null?<Loading/>:<>
        <Typography color="text.secondary">با نام کاربری و رمز حساب دارای مجوز مانیتورینگ وارد شوید.</Typography>
        <Login onLogin={current=>{if(!current.permissions?.includes('view_operations'))setError('این حساب مجوز مشاهدهٔ مانیتورینگ را ندارد.');else void load();}}/>
      </>}
      <Button component={Link} href="/manage" startIcon={<ArrowForwardRounded/>}>ورود به مدیریت</Button>
    </ContentCard></Stack>;
}

function StaffConsole({children,supportIdentity,supportMemory}:{children:ReactNode;supportIdentity:{current:string|undefined};supportMemory:{current:SupportWorkspaceMemory}}) {
  const pathname = usePathname();
  const router=useRouter();
  const route = managementRoute(pathname);
  const [session, setSession] = useState<ManagementSession | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [epoch, setEpoch] = useState(0);
  const [action, setAction] = useState<ManagementAction | null>(null);
  const sessionGeneration = useRef(0);
  const loadSession = useCallback(async () => {
    const generation = ++sessionGeneration.current;
    setSession(null); setAction(null); setError("");
    try {
      const current = await api<ManagementSession>("/manage/session");
      if (generation === sessionGeneration.current) {
        if (!current.authenticated || !current.permissions?.includes('support_chat') || supportIdentity.current !== current.session_identity) supportMemory.current={thread:null,composer:{draft:"",pending:null}};
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
    if (e instanceof ApiError && ['management_login_required','forbidden'].includes(e.code)) {
      supportMemory.current={thread:null,composer:{draft:"",pending:null}}; supportIdentity.current=undefined; setAction(null);
      if(e.code==='management_login_required')setSession({authenticated:false});else void loadSession();
    }
  }, [loadSession]);
  async function signOut() {
    setBusy(true); setError("");
    try { await api("/manage/logout", { method: "POST", body: {} }); supportMemory.current={thread:null,composer:{draft:"",pending:null}}; supportIdentity.current=undefined; setSession({ authenticated: false }); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  const supportFailure = failed;
  const permissions = session?.permissions || [];
  const supportCount = useSupportBadge(!!session?.authenticated&&permissions.includes('support_chat'),supportFailure);
  const navigation = managementNavigation(session || { authenticated: false });
  const active = route.resource;
  const allowed = navigation.some(item => item.key === active) || session?.resources?.some(item => item.key === active);
  const title = route.userId ? "پروندهٔ کاربر" : navigation.find(item => item.key === active)?.title || session?.resources?.find(item => item.key === active)?.title || "مدیریت";
  useEffect(() => { setAction(null); }, [pathname]);
  useEffect(()=>{if(session?.authenticated&&active==='dashboard'&&!allowed){const target=managementLanding(session);if(target&&target!=='/manage')router.replace(target);}},[session,active,allowed,router]);
  const workspace=<>
      {managementShowsBalances(active,permissions)&&<ProviderBalances onFailure={failed}/>}
      {error&&<Failure message={error}/>}
      {!allowed&&<Alert severity="warning" action={<Button component={Link} href={managementLanding(session||{authenticated:false})||'/manage'}>بازگشت به بخش مجاز</Button>}>این بخش برای حساب شما در دسترس نیست. از فهرست بخش‌های مجاز انتخاب کنید.</Alert>}
      {allowed&&(route.userId?<UserActivity key={`${route.userId}-${epoch}`} userId={route.userId} permissions={permissions} resources={session?.resources||[]} onAction={setAction} onFailure={failed}/>:active==='staff'?<ManagementStaff view={pathname.endsWith('/roles')?'roles':'employees'} onFailure={failed}/>:active==='changelog'?<ManagementChangelog onFailure={failed}/>:active==='examples'?<ExampleSettings onFailure={failed}/>:active==='support'?<SupportInbox onFailure={supportFailure} memory={supportMemory}/>:active==='dashboard'?<Dashboard key={`dashboard-${epoch}`} canOperate={permissions.includes('operate_safety')} onAction={setAction} onFailure={failed}/>:active==='limits'?<Limits canManageMonitoringAccess={permissions.includes('manage_monitoring_access')} onFailure={failed}/>:active==='ai'?<AISettings onFailure={failed}/>:active==='manual-settings'?<ManualPaymentSettings onFailure={failed}/>:active==='packages'?<PackageSettings onFailure={failed}/>:active&&<Records key={`${active}-${epoch}`} resource={active} permissions={permissions} onAction={setAction} onFailure={failed}/>)}
      {children}
      {action&&(['grant_package','approve_card','reject_card'].includes(action.name)?<ManualPaymentDialog action={action} onClose={()=>setAction(null)} onComplete={()=>{setAction(null);setEpoch(v=>v+1);}} onFailure={failed}/>:<ActionDialog action={action} onClose={()=>setAction(null)} onComplete={()=>{setAction(null);setEpoch(v=>v+1);}} onFailure={failed}/>)}
  </>;
  return <>
    {!session || !session.authenticated ? <Stack sx={{maxWidth:500,mx:'auto',px:2,py:{xs:4,sm:7},gap:3}}><ManagementBrand/><ContentCard>
      <Stack direction="row" spacing={1} sx={{alignItems:'center'}}><ShieldOutlined color="primary"/><Typography component="h1" variant="h5">مدیریت بگم نگم</Typography></Stack>
      <Typography color="text.secondary">با نام کاربری و رمز حساب مدیر وارد شوید.</Typography>
      {error&&<Failure message={error} retry={()=>void loadSession()}/>}
      {!session?<Loading/>:<Login onLogin={current=>{if(supportIdentity.current!==current.session_identity)supportMemory.current={thread:null,composer:{draft:'',pending:null}};supportIdentity.current=current.session_identity;setSession(current);if(!managementNavigation(current).some(item=>item.key===active)&&!current.resources?.some(item=>item.key===active)){const target=managementLanding(current);if(target)router.replace(target);}}}/>}
      <Button component={Link} href="/" variant="text" startIcon={<ArrowForwardRounded/>}>مشاهدهٔ سایت</Button>
    </ContentCard></Stack> : <ManagementFrame session={session} pathname={pathname} title={title} active={active} supportCount={supportCount} busy={busy} onSignOut={()=>void signOut()}>{workspace}</ManagementFrame>}
  </>;
}

function Login({ onLogin }: { onLogin: (session: ManagementSession) => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError("");
    try { onLogin(await api<ManagementSession>("/manage/login", { method: "POST", body: { username: form.get("username"), password: form.get("password") } })); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  return <Stack component="form" onSubmit={submit} spacing={3}>
    {error&&<Failure message={error}/>}
    <ManagementInput label="نام کاربری" name="username" autoComplete="username" dir="ltr" maxLength={150} required/>
    <ManagementInput label="رمز عبور" name="password" type="password" autoComplete="current-password" dir="ltr" maxLength={512} required/>
    <ManagementButton disabled={busy} startIcon={<LoginRounded/>}>{busy?'در حال ورود…':'ورود به مدیریت'}</ManagementButton>
  </Stack>;
}

function Dashboard({ canOperate, onAction, onFailure }: { canOperate: boolean; onAction: (a: ManagementAction) => void; onFailure: (e: unknown) => void }) {
  const [data, setData] = useState<ManagementDashboard | null>(null), [error, setError] = useState("");
  const load = useCallback(async () => { setError(""); try { setData(await api<ManagementDashboard>("/manage/dashboard")); } catch (e) { setError(errorMessage(e)); onFailure(e); } }, [onFailure]);
  useEffect(() => { void load(); }, [load]);
  if (!data) return error ? <Failure message={error} retry={() => void load()} /> : <Loading />;
  const totals: [string, string][] = [["accounts", "حساب کاربری"], ["orders", "درخواست پیام"], ["delivered", "پیامک رسیده"], ["invitations", "دعوت ثبت‌شده"], ["registered_invitations", "عضویت با دعوت"], ["active_alerts", "هشدار فعال"]];
  const metrics: [string, string][] = [["outbox_pending", "در انتظار ارسال"], ["delivery_unknown", "تحویل نیازمند تطبیق"], ["payment_unknown", "پرداخت نیازمند تطبیق"], ["refund_open", "بازپرداخت باز"], ["reports_open", "گزارش باز"], ["oldest_queue_seconds", "عمر قدیمی‌ترین صف (ثانیه)"]];
  return <Stack spacing={3}>
    <SectionTitle title="آنچه در سایت می‌گذرد" icon="dashboard" action={<ManagementButton type="button" variant="outlined" startIcon={<RefreshRounded/>} onClick={()=>void load()}>تازه‌سازی</ManagementButton>}/>
    {error&&<Failure message={error}/>}
    <Grid container spacing={2}>{totals.map(([key,label])=><Grid key={key} size={{xs:6,lg:4}}><Card sx={{p:{xs:2,sm:3},height:'100%'}}><Stack spacing={1.5}><ManagementIcon name={key==='accounts'?'accounts':key==='invitations'||key==='registered_invitations'?'invitations':key==='active_alerts'?'alerts':'orders'} color="primary"/><Typography variant="body2" color="text.secondary">{label}</Typography><Typography variant="h4">{managementNumber(data.totals[key])}</Typography></Stack></Card></Grid>)}</Grid>
    <ContentCard><SectionTitle title="ارسال و صف پردازش" icon="outbox" action={<Chip label={data.operations.sending_halted?'ارسال متوقف است':'ارسال باز است'} color={data.operations.sending_halted?'warning':'success'} size="small"/>}/>
      <Grid container spacing={2}>{metrics.map(([key,label])=><Grid key={key} size={{xs:6,md:4}}><Stack spacing={1} sx={{p:2,bgcolor:'background.default',borderRadius:2}}><Typography variant="caption" color="text.secondary">{label}</Typography><Typography variant="h6">{managementNumber(data.operations[key])}</Typography></Stack></Grid>)}</Grid>
      {canOperate&&<Box><ManagementButton type="button" color={data.operations.sending_halted?'primary':'error'} startIcon={<ManagementIcon name="outbox"/>} onClick={()=>onAction({name:data.operations.sending_halted?'resume':'halt',label:data.operations.sending_halted?'ازسرگیری ارسال':'توقف ارسال جدید',object_id:'global'})}>{data.operations.sending_halted?'ازسرگیری ارسال':'توقف ارسال جدید'}</ManagementButton></Box>}
    </ContentCard>
    <Grid container spacing={2}><Grid size={{xs:12,md:6}}><ContentCard><SectionTitle title="اتصال سرویس‌ها" icon="ai"/>{[['محیط',data.environment.demo?'آزمایشی':'واقعی'],['پیامک',String(managementDisplayValue('provider',data.environment.sms))],['کد ورود',String(managementDisplayValue('provider',data.environment.otp))],['پرداخت پولی',data.environment.paid_enabled?'فعال':'بسته']].map(([label,value])=><Stack key={label} direction="row" sx={{justifyContent:'space-between',gap:2}}><Typography color="text.secondary">{label}</Typography><Typography>{value}</Typography></Stack>)}</ContentCard></Grid>
    <Grid size={{xs:12,md:6}}><ContentCard><SectionTitle title="دفتر هزینهٔ پیامک" icon="budgets"/><Typography color="text.secondary">رزرو ثبت‌شدهٔ امروز</Typography><Typography variant="h5">{managementNumber(data.operations.provider_budget_reserved_rial)} ریال</Typography><Typography>سقف روزانه: {data.operations.provider_budget_unlimited?'بدون سقف':`${managementNumber(data.operations.provider_budget_limit_rial)} ریال`}</Typography><Typography variant="caption" color="text.secondary">رزرو هزینه با صورتحساب قطعی سرویس پیامک یکسان نیست.</Typography></ContentCard></Grid></Grid>
    <Typography variant="caption" color="text.secondary">آخرین دریافت: {managementDate(data.updated_at)}</Typography>
  </Stack>;
}

function Records({ resource, permissions, onAction, onFailure }: { resource: string; permissions: string[]; onAction: (a: ManagementAction) => void; onFailure: (e: unknown) => void }) {
  const [data, setData] = useState<ManagementRecords | null>(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState({ page: 1, page_size:25, query: "", status: "" });
  useEffect(() => {
    const controller = new AbortController(); setBusy(true); setError("");
    void api<ManagementRecords>(`/manage/records/${resource}`, { method: "POST", body: filter, signal: controller.signal }).then(result=>{if(!controller.signal.aborted)setData(result);}).catch(e => { if (controller.signal.aborted) return; setError(errorMessage(e)); onFailure(e); }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [resource, filter, onFailure]);
  function search(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); setFilter(previous=>({...previous,page:1,query:String(form.get('query')||''),status:String(form.get('status')||'')})); }
  const renderActions=useCallback((row:ManagementRow,focused:boolean)=><RowActions resource={resource} row={row} permissions={permissions} onAction={onAction} tabIndex={focused?0:-1}/>,[resource,permissions,onAction]);
  return <ContentCard>
    <Grid component="form" container spacing={2} onSubmit={search} sx={{alignItems:'flex-start'}}>
      <Grid size={{xs:12,md:data?.statuses.length?5:7}}><ManagementInput label="جست‌وجو" name="query" maxLength={100} placeholder={['accounts','invitations','blacklist'].includes(resource)?'همه یا بخشی از شماره موبایل':'وضعیت، موضوع یا کد'} helperText={resource==='accounts'?'شمارهٔ کامل یا بخشی از آن؛ ارقام فارسی و لاتین پذیرفته می‌شوند.':undefined}/></Grid>
      {!!data?.statuses.length&&<Grid size={{xs:12,sm:6,md:3}}><ManagementSelect label="وضعیت" name="status" defaultValue=""><option value="">همهٔ وضعیت‌ها</option>{data.statuses.map(([key])=><option key={key} value={key}>{managementState(key)}</option>)}</ManagementSelect></Grid>}
      <Grid size={{xs:12,sm:6,md:data?.statuses.length?4:5}}><Stack direction="row" spacing={1}><ManagementButton disabled={busy} startIcon={<SearchRounded/>}>جست‌وجو</ManagementButton><ManagementButton type="button" variant="outlined" disabled={busy} startIcon={<RefreshRounded/>} onClick={()=>setFilter(v=>({...v}))}>تازه‌سازی</ManagementButton></Stack></Grid>
    </Grid>
    {resource==='blacklist'&&<Alert severity="info">فقط لغو دریافتِ فعال نمایش داده می‌شود؛ بازکردن لینک به‌تنهایی لغو نیست. فهرست شامل شماره‌های بدون حساب هم هست و امکان فعال‌کردن دریافت از اینجا وجود ندارد.</Alert>}
    {error&&<Failure message={error} retry={()=>setFilter(v=>({...v}))}/>}
    <ManagementDataGrid resource={resource} data={data} rows={busy||error?[]:data?.rows||[]} loading={busy||(!data&&!error)} failed={!!error}
      pagination={{page:filter.page-1,pageSize:filter.page_size}} onPaginationChange={model=>setFilter(current=>managementGridPage(current,model))}
      renderActions={renderActions} hasActions={resource==='accounts'||!!data?.rows.some(row=>managementActions(resource,row,permissions).length>0)}/>
  </ContentCard>;
}

function Limits({ onFailure, canManageMonitoringAccess }: { onFailure: (e: unknown) => void; canManageMonitoringAccess:boolean }) {
  const [data, setData] = useState<LimitSettings | null>(null), [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const onSaved = (updated: LimitSettings) => { setData(updated); setSaved(true); };
  const load = useCallback(async () => { setError(""); try { setData(await api<LimitSettings>("/manage/limits")); } catch (e) { setError(errorMessage(e)); onFailure(e); } }, [onFailure]);
  useEffect(() => { void load(); }, [load]);
  return <Stack spacing={3}>{canManageMonitoringAccess&&<MonitoringAccessSettings onFailure={onFailure}/>} {error&&<Failure message={error} retry={()=>void load()}/>} {saved&&<Alert severity="success">تنظیمات ذخیره شد.</Alert>}{!data?!error&&<Loading/>:<>
    <Alert severity="info">سه ارسال هدیهٔ اولیه رایگان می‌مانند. صفر در بازه‌های شمارش و فاصله‌ها همان محدودیت را خاموش می‌کند. برای ارسال در تمام شبانه‌روز، گزینهٔ «ارسال فقط در ساعت مجاز» را بردارید.</Alert>
    {data.gateway_problem&&<Alert severity="warning">درگاه آمادهٔ فعال‌سازی نیست: {data.gateway_problem}</Alert>}
    <SiteLimits key={`site-${data.revision}`} data={data} onSaved={onSaved} onFailure={onFailure}/><RequestLimits rules={data.requests} onSaved={onSaved} onFailure={onFailure}/>
  </>}</Stack>;
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
  return <Card component="form" onSubmit={save} sx={{p:{xs:2,sm:3}}}><Stack spacing={2.5}><SectionTitle title="تنظیمات مشترک سایت" icon="limits" action={<Chip size="small" label={`نسخهٔ ${managementNumber(data.revision)}`}/>}/>
    {error&&<Failure message={error}/>} {message&&<Alert severity="success">{message}</Alert>}{fields.__all__&&<Failure message={String(fields.__all__)}/>}
    <Box component="fieldset" disabled={busy} sx={{border:0,p:0,m:0,minWidth:0}}><Stack spacing={2}>
      {data.sections.map((section,i)=><Accordion key={section.title} defaultExpanded={i<2} disableGutters variant="outlined" elevation={0}><AccordionSummary expandIcon={<ExpandMoreRounded/>}><Typography variant="subtitle1">{section.title}</Typography></AccordionSummary><AccordionDetails><Grid container spacing={3}>{section.fields.map(field=><Grid key={field.key} size={{xs:12,md:6}}>{field.type==='bool'?<Stack><FormControlLabel label={field.label} control={<ManagementInput name={field.key} type="checkbox" role={['wallet_enabled','gateway_enabled'].includes(field.key)?'switch':undefined} defaultChecked={Boolean(data.values[field.key])} aria-invalid={!!fields[field.key]}/>}/>{(field.help||fields[field.key])&&<Typography variant="caption" color={fields[field.key]?'error':'text.secondary'}>{fields[field.key]?String(fields[field.key]):field.help}</Typography>}</Stack>:<ManagementDigitInput label={field.label} helperText={fields[field.key]?String(fields[field.key]):field.help} error={!!fields[field.key]} name={field.key} min={field.min??0} max={field.max??Number.MAX_SAFE_INTEGER} step={1} defaultValue={Number(data.values[field.key])} required/>}</Grid>)}</Grid></AccordionDetails></Accordion>)}
      <Stack direction={{xs:'column',sm:'row'}} spacing={1}><ManagementButton startIcon={<SaveOutlined/>}>{busy?'در حال ذخیره…':'ذخیرهٔ تنظیمات'}</ManagementButton><ManagementButton type="button" variant="outlined" startIcon={<RefreshRounded/>} onClick={()=>window.location.reload()}>دریافت آخرین تنظیمات</ManagementButton></Stack>
    </Stack></Box>
  </Stack></Card>;
}

function RequestLimits({ rules, onSaved, onFailure }: { rules: LimitRule[]; onSaved: (d: LimitSettings) => void; onFailure: (e: unknown) => void }) {
  const [scope, setScope] = useState(rules[0]?.scope || "");
  return <ContentCard><SectionTitle title="کنترل تعداد درخواست‌ها" icon="limits"/><Alert severity="info">کنترل ورود مدیر، حدس کد، لینک خصوصی و پرداخت باید فعال بماند. تعداد و بازه قابل تنظیم است.</Alert>
    <ManagementSelect label="نوع درخواست" value={scope} onChange={e=>setScope(e.target.value)}>{rules.map(rule=><option key={rule.scope} value={rule.scope}>{rule.label} · {rule.enabled?'فعال':'بدون سقف'}</option>)}</ManagementSelect>
    {rules.find(rule=>rule.scope===scope)&&<RequestRule key={`${scope}:${rules.find(rule=>rule.scope===scope)!.revision}`} rule={rules.find(rule=>rule.scope===scope)!} onSaved={onSaved} onFailure={onFailure}/>}</ContentCard>;
}

function RequestRule({ rule, onSaved, onFailure }: { rule: LimitRule; onSaved: (d: LimitSettings) => void; onFailure: (e: unknown) => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError("");
    try { onSaved(await api<LimitSettings>(`/manage/request-limits/${rule.scope}`, { method: "POST", body: { revision: rule.revision, reason: managementReason("request_limits"), values: { enabled: rule.protected || form.get("enabled") === "on", maximum: Number(form.get("maximum")), window_seconds: Number(form.get("window_seconds")) } } })); }
    catch (e) { setError(errorMessage(e)); onFailure(e); } finally { setBusy(false); }
  }
  return <Stack component="form" onSubmit={save} spacing={2}>{error&&<Failure message={error}/>}<Box component="fieldset" disabled={busy} sx={{border:0,p:0,m:0,minWidth:0}}><Stack spacing={2}>
    <FormControlLabel label="کنترل فعال باشد" control={<ManagementInput name="enabled" type="checkbox" defaultChecked={rule.enabled} disabled={rule.protected}/>}/>
    <Grid container spacing={2}><Grid size={{xs:12,sm:6}}><ManagementDigitInput label="حداکثر تعداد" name="maximum" min={1} step={1} defaultValue={rule.maximum} required/></Grid><Grid size={{xs:12,sm:6}}><ManagementDigitInput label="بازه (ثانیه)" name="window_seconds" min={1} step={1} defaultValue={rule.window_seconds} required/></Grid></Grid>
    <Box><ManagementButton startIcon={<SaveOutlined/>}>{busy?'در حال ذخیره…':'ذخیرهٔ این کنترل'}</ManagementButton></Box>
  </Stack></Box></Stack>;
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
  return <ManagementDialog title={action.label} onClose={onClose} busy={busy}>
    <Typography variant="caption" color="text.secondary" sx={{overflowWrap:'anywhere'}}>رکورد: {action.object_id}</Typography>{error&&<Failure message={error}/>}
    {texts?<Stack spacing={2}><Chip icon={<ShieldOutlined/>} label="فقط مدیریت · مشاهده ثبت شد" sx={{alignSelf:'flex-start'}}/><Typography component="h3" variant="subtitle1">متن اولیهٔ کاربر</Typography><Typography sx={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{texts.original_available?texts.original_text:'متن اولیه برای این سابقه موجود نیست؛ ممکن است قدیمی یا پاک‌سازی‌شده باشد.'}</Typography><Typography component="h3" variant="subtitle1">متن نهایی بررسی‌شده</Typography><Typography sx={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{texts.final_text||(texts.mode==='attempt'?'متن نهایی تأییدشده‌ای برای این سابقه موجود نیست.':'متن طبق سیاست نگهداری حذف شده است.')}</Typography></Stack>:report?<Stack spacing={2}><Chip label={managementState(report.status)} sx={{alignSelf:'flex-start'}}/><Typography component="h3" variant="subtitle1">موضوع گزارش</Typography><Typography>{report.reason}</Typography><Typography component="h3" variant="subtitle1">توضیحات دریافت‌کننده</Typography><Typography sx={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{report.details||'توضیحی ثبت نشده است.'}</Typography><Typography component="h3" variant="subtitle1">متن بررسی‌شدهٔ مرتبط</Typography><Typography sx={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{report.reviewed_text}</Typography><Alert severity="info">مشاهدهٔ این پرونده در سوابق مدیریت ثبت شد.</Alert></Stack>:<Stack component="form" onSubmit={submit} spacing={3}>
      {action.name==='free_sending'&&<Alert severity="warning">{action.value?'این حساب بدون مصرف هدیه یا اعتبار بسته ارسال می‌کند و هزینهٔ واقعی بر عهدهٔ سرویس است.':'ارسال‌های بعدی از هدیه و اعتبار بسته مصرف می‌کنند؛ سفارش‌های قبلی تغییر نمی‌کنند.'} سقف روزانه، کنترل گیرنده و محتوا مستقل‌اند.</Alert>}
      {action.name==='account_limits'&&<Box component="fieldset" disabled={busy} sx={{border:0,p:0,m:0,minWidth:0}}><Stack spacing={3}><Alert severity="info">تنظیم فقط برای همین حساب است. تعداد نامحدود، اعتبار پیام یا کنترل‌های محتوا و گیرنده را حذف نمی‌کند.</Alert><AccountLimitInput name="sender_daily_limit" label="سقف تعداد ارسال در ۲۴ ساعت" value={action.accountLimits?.sender_daily_limit??null}/><AccountLimitInput name="rewrite_daily_limit" label="بازنویسی در روز" value={action.accountLimits?.rewrite_daily_limit??null}/></Stack></Box>}
      {action.name==='confirm_refund'&&<><Alert severity="warning">ابتدا بازپرداخت را خارج از سایت انجام دهید؛ این اقدام فقط ثبت سند است.</Alert><ManagementInput label="مرجع سند بازپرداخت" name="reference" minLength={3} maxLength={100} required/></>}
      <ManagementButton disabled={busy} startIcon={['message_texts','attempt_texts','review'].includes(action.name)?<VisibilityOutlined/>:<CheckCircleOutline/>}>{busy?'در حال ثبت…':['message_texts','attempt_texts'].includes(action.name)?'ثبت مشاهده و نمایش متن‌ها':action.name==='review'?'ثبت مشاهده و بازکردن پرونده':'تأیید و ثبت اقدام'}</ManagementButton>
    </Stack>}
  </ManagementDialog>;
}

function AccountLimitInput({ name, label, value }: { name: string; label: string; value: number | null }) {
  const [mode, setMode] = useState(value === null ? 'site' : value === 0 ? 'unlimited' : 'custom');
  return <Grid container spacing={2}><Grid size={{xs:12,sm:6}}><ManagementSelect label={label} name={`${name}_mode`} value={mode} onChange={e=>setMode(e.target.value)}><option value="site">طبق تنظیم سایت</option><option value="custom">عدد اختصاصی</option><option value="unlimited">تعداد نامحدود</option></ManagementSelect></Grid>{mode==='custom'&&<Grid size={{xs:12,sm:6}}><ManagementDigitInput label={`حداکثر ${label}`} name={name} min={1} max={1000000} step={1} defaultValue={value||1000} required/></Grid>}</Grid>;
}

function RowActions({ resource, row, permissions, onAction, tabIndex=0 }: { resource: string; row: ManagementRow; permissions: string[]; onAction: (a: ManagementAction) => void; tabIndex?:number }) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const id = useId();
  const actions = managementActions(resource, row, permissions);
  if (resource !== "accounts" && !actions.length) return null;
  const close = () => setAnchor(null);
  return <>
    <IconButton id={`${id}-button`} aria-label="عملیات ردیف" tabIndex={tabIndex} aria-haspopup="menu" aria-expanded={!!anchor} aria-controls={anchor ? `${id}-menu` : undefined} onClick={event => setAnchor(event.currentTarget)}>
      <MoreHorizRounded/>
    </IconButton>
    <Menu id={`${id}-menu`} dir="rtl" anchorEl={anchor} open={!!anchor} onClose={close} anchorOrigin={{vertical:'bottom',horizontal:'left'}} transformOrigin={{vertical:'top',horizontal:'left'}} slotProps={{list:{'aria-labelledby':`${id}-button`}}}>
      {resource === "accounts" && [
        <MenuItem key="profile" component={Link} href={managementUserHref(row.record_id)} onClick={close}><ListItemIcon><ManagementIcon name="accounts"/></ListItemIcon>پروندهٔ کاربر</MenuItem>,
        <MenuItem key="messages" component={Link} href={managementUserHref(row.record_id, "messages")} onClick={close}><ListItemIcon><MailOutlineRounded/></ListItemIcon>پیام‌های کاربر</MenuItem>,
        <MenuItem key="invitations" component={Link} href={managementUserHref(row.record_id, "invitations")} onClick={close}><ListItemIcon><ManagementIcon name="invitations"/></ListItemIcon>دعوت‌های کاربر</MenuItem>,
      ]}
      {actions.map(item => <MenuItem key={item.name} onClick={() => { close(); onAction(item); }}><ListItemIcon><SettingsOutlined/></ListItemIcon>{item.label}</MenuItem>)}
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
  return <Stack spacing={3}>
    <Box><Button component={Link} href="/manage/users" startIcon={<ArrowForwardRounded/>}>بازگشت به کاربران</Button></Box>
    <ContentCard><SectionTitle title="پروندهٔ کاربر" icon="accounts" action={<ManagementButton type="button" variant="outlined" disabled={busy} startIcon={<RefreshRounded/>} onClick={()=>setEpoch(v=>v+1)}>تازه‌سازی</ManagementButton>}/><Typography component="h2" variant="h5" dir="ltr" sx={{textAlign:'end'}}>{account?account.phone||'شماره در دسترس نیست':`کاربر ${Number(userId).toLocaleString('fa-IR')}`}</Typography>
      {account&&<Stack direction="row" spacing={1} sx={{alignItems:'center'}}><Typography variant="body2">شناسه: {managementNumber(account.id)}</Typography><Chip size="small" color={account.suspended?'warning':'success'} label={account.suspended?'تعلیق‌شده':'فعال'}/></Stack>}
      <Tabs value={canRead?section:false} aria-label="فعالیت کاربر" variant="scrollable" scrollButtons="auto">{([{key:'messages',resource:'orders',title:'پیام‌ها',icon:<MailOutlineRounded/>},{key:'invitations',resource:'invitations',title:'دعوت‌ها',icon:<ManagementIcon name="invitations"/>}] as const).filter(tab=>resources.some(item=>item.key===tab.resource)).map(tab=><Tab component={Link} key={tab.key} value={tab.key} label={tab.title} icon={tab.icon} iconPosition="start" href={managementUserHref(userId,tab.key)}/>)}</Tabs>
    </ContentCard>
    {error&&<Failure message={error} retry={()=>setEpoch(v=>v+1)}/>} {!canRead&&<Alert severity="warning">مجوز مشاهدهٔ این فعالیت را ندارید.</Alert>}{busy&&<Loading/>}
    {data&&!busy&&!error&&<ContentCard>
      <Stack direction="row" sx={{justifyContent:'space-between',gap:1}}><Typography variant="body2" color="text.secondary">{managementNumber(data.total)} رکورد</Typography><Typography variant="body2" color="text.secondary">صفحهٔ {managementNumber(data.page)} از {managementNumber(pages)}</Typography></Stack>
      {!data.rows.length?<Empty message="فعالیتی در این بخش ثبت نشده است."/>:data.rows.map(row=><Card component="article" key={`${row.kind}-${row.record_id}`} sx={{p:2}}><Stack spacing={2}>
        <Stack direction="row" sx={{alignItems:'center',justifyContent:'space-between',gap:1,flexWrap:'wrap'}}><Stack direction="row" spacing={1} sx={{alignItems:'center'}}><HistoryOutlined color="primary"/><Typography component="h3" variant="subtitle1">{kinds[row.kind]||'فعالیت کاربر'}</Typography></Stack><Chip size="small" color={row.status==='rejected'?'warning':row.status==='failed'?'error':'default'} label={managementState(row.status)}/></Stack>
        <Typography variant="caption" color="text.secondary">{managementDate(row.created_at)}</Typography>
        {row.phone&&<Typography variant="body2">مخاطب: {row.phone}</Typography>}
        {row.reason_code&&<Alert severity={row.status==='rejected'?'warning':row.status==='failed'?'error':'info'}>علت: {managementExplanation(row.reason_code)}</Alert>}
        {row.kind==='invitation'&&<Stack spacing={1}><Typography variant="body2">ثبت‌نام مخاطب: {row.registered_at?managementDate(row.registered_at):'هنوز ثبت‌نام نکرده است'}</Typography><Typography variant="body2">جایزهٔ دعوت: {row.reward_awarded_at?managementDate(row.reward_awarded_at):'ثبت نشده است'}</Typography></Stack>}
        {row.kind==='moderation'&&<Typography variant="body2" color="text.secondary">این سابقهٔ قدیمی فقط نتیجهٔ بررسی را دارد؛ متن اولیه در آن زمان ذخیره نشده است.</Typography>}
        <Accordion disableGutters elevation={0}><AccordionSummary expandIcon={<ExpandMoreRounded/>}><Typography variant="caption">شناسهٔ سابقه</Typography></AccordionSummary><AccordionDetails><Typography variant="caption" sx={{overflowWrap:'anywhere'}}>{row.id}</Typography></AccordionDetails></Accordion>
        {permissions.includes('view_private_message_text')&&['order','attempt'].includes(row.kind)&&<Box><ManagementButton type="button" variant="outlined" startIcon={<VisibilityOutlined/>} onClick={()=>onAction({name:row.kind==='order'?'message_texts':'attempt_texts',label:'مشاهدهٔ متن‌ها',object_id:String(row.kind==='order'?row.order_id||row.id:row.id),userId})}>مشاهدهٔ متن اولیه و نتیجه</ManagementButton></Box>}
      </Stack></Card>)}
      <Stack component="nav" aria-label="صفحه‌بندی فعالیت کاربر" direction="row" spacing={1} sx={{justifyContent:'flex-end'}}>{page>1&&<Button component={Link} variant="outlined" startIcon={<ArrowForwardRounded/>} href={pageHref(page-1)}>قبلی</Button>}{page<pages&&<Button component={Link} variant="outlined" endIcon={<ArrowBackRounded/>} href={pageHref(page+1)}>بعدی</Button>}</Stack>
    </ContentCard>}
  </Stack>;
}
