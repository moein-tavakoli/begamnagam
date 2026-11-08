"use client";
import Card from "@mui/material/Card";
import Stack from "@mui/material/Stack";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormHelperText from "@mui/material/FormHelperText";
import Box from "@mui/material/Box";
import RefreshIcon from "@mui/icons-material/Refresh";
import SaveIcon from "@mui/icons-material/Save";
import SettingsIcon from "@mui/icons-material/Settings";
import ScienceIcon from "@mui/icons-material/Science";

import { ManagementButton, ManagementInput, ManagementSelect, ManagementTextarea, ManagementDigitInput } from "./management-ui";

import { managementReason } from "@/lib/management";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import { managementNumber } from "@/lib/management";
import type { MessageTone, MessageToneOption } from '@/lib/message-tones';

type ToneFlag = 'tone_polite_enabled' | 'tone_firm_enabled' | 'tone_blunt_enabled' | 'tone_angry_enabled';
type Values = { provider: string; ollama_model: string; gapgpt_model: string; timeout_seconds: number; parallel_requests: number; daily_limit: number; user_daily_limit: number } & Record<ToneFlag, boolean>;
type Settings = { values: Values; revision: number; gapgpt_credentials_configured: boolean; tone_options: (MessageToneOption & {field: ToneFlag})[] };
type Result = { allowed: boolean; message: string; elapsed_seconds: number };

export function AISettings({ onFailure }: { onFailure: (error: unknown) => void }) {
  const [data, setData] = useState<Settings | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const load = useCallback(async () => {
    setError(""); setSaved(false);
    try { setData(await api<Settings>("/manage/ai")); }
    catch (failure) { setError(errorMessage(failure)); onFailure(failure); }
  }, [onFailure]);
  useEffect(() => { void load(); }, [load]);
  return <Stack spacing={3}>
    {error && <Alert severity="error">{error}</Alert>}
    {!data ? <Typography role="status">در حال دریافت تنظیمات هوش مصنوعی…</Typography> : <>
      <Alert severity="info">بازنویسی و بازبینی در همان درخواست انجام می‌شوند. متن نهایی پیش از ارسال به تأیید فرستنده می‌رسد. اگر سرویس مشغول یا نامطمئن باشد، خطا نمایش داده می‌شود و سرویس دیگری خودکار جایگزین نمی‌شود.</Alert>
      {saved && <Alert severity="success" role="status">تنظیمات برای درخواست‌های تازه ذخیره شد.</Alert>}
      <Configuration key={data.revision} data={data} onSaved={updated => { setData(updated); setSaved(true); }} onFailure={onFailure} />
      <LocalTest key={`test-${data.revision}`} model={data.values.ollama_model} tones={data.tone_options.filter(option => data.values[option.field])} onFailure={onFailure} />
    </>}
    <Box><ManagementButton type="button" className="secondary" startIcon={<RefreshIcon />} onClick={() => void load()}>دریافت آخرین تنظیمات</ManagementButton></Box>
  </Stack>;
}

function Configuration({ data, onSaved, onFailure }: { data: Settings; onSaved: (data: Settings) => void; onFailure: (error: unknown) => void }) {
  const [provider, setProvider] = useState(data.values.provider);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string | string[]>>({});
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const values = { ...data.values, provider };
    for (const key of ["ollama_model", "gapgpt_model"] as const) values[key] = String(form.get(key) || "").trim();
    for (const key of ["timeout_seconds", "parallel_requests", "daily_limit", "user_daily_limit"] as const) values[key] = Number(form.get(key));
    for (const option of data.tone_options) values[option.field] = form.get(option.field) === 'on';
    setBusy(true); setError(""); setFields({});
    try {
      const updated = await api<Settings>("/manage/ai", { method: "POST", body: { values, revision: data.revision, reason: managementReason("ai") } });
      onSaved(updated);
    } catch (failure) {
      setError(errorMessage(failure)); if (failure instanceof ApiError) setFields(failure.fields || {}); onFailure(failure);
    } finally { setBusy(false); }
  }
  const numbers = [
    ["timeout_seconds", "مهلت کل بازنویسی و بازبینی محلی (ثانیه)", 2, 20],
    ["parallel_requests", "حداکثر درخواست محلی هم‌زمان؛ بدون صف", 1, 2],
    ["daily_limit", "سقف روزانهٔ بازنویسی محلی", 1, 100000],
    ["user_daily_limit", "سقف روزانهٔ محلی برای هر حساب", 1, 10000],
  ] as const;
  return <Card component="form" onSubmit={save} sx={{ p: { xs: 2, md: 3 } }}>
    <Stack spacing={3}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}><SettingsIcon color="primary" /><Typography variant="h6" component="h2">سرویس فعال هوش مصنوعی</Typography></Stack>
      {error && <Alert severity="error">{error}</Alert>}
      <Stack component="fieldset" disabled={busy} spacing={3} sx={{ border: 0, p: 0, m: 0, minWidth: 0 }}>
        <ManagementSelect label="سرویس" value={provider} onChange={event => setProvider(event.target.value)} error={!!fields.provider} helperText={fields.provider ? String(fields.provider) : provider === "ollama" ? "متن روی همین زیرساخت پردازش می‌شود." : provider === "gapgpt" ? "فعال‌سازی به کلید سرور، مدل و سهمیهٔ مثبت GapGPT نیاز دارد." : "بازنویسی دلخواه غیرفعال می‌شود."}>
          <option value="template">خاموش — متن‌های آماده</option><option value="ollama">Ollama — مدل محلی</option><option value="gapgpt">GapGPT — سرویس بیرونی</option>
        </ManagementSelect>
        <Stack component="section" spacing={2} aria-labelledby="manage-tone-title">
          <Typography variant="subtitle1" component="h3" id="manage-tone-title">لحن‌های قابل انتخاب کاربران</Typography>
          <Typography color="text.secondary" variant="body2">فقط گزینه‌های تیک‌خورده، زیر کادر متن کاربر نمایش داده می‌شوند. بدون تیک، انتخاب لحن پنهان و حالت مودبانه برقرار می‌شود. تغییر برای پیش‌نمایش‌های تازه است.</Typography>
          <Grid container spacing={2}>{data.tone_options.map(option => <Grid size={{ xs: 12, md: 4 }} key={option.id}>
            <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2, height: '100%' }}>
              <FormControlLabel label={option.label} control={<ManagementInput type="checkbox" name={option.field} defaultChecked={data.values[option.field]} aria-describedby={`help-${option.field}`} aria-invalid={!!fields[option.field]} />} />
              <FormHelperText id={`help-${option.field}`} error={!!fields[option.field]}>{fields[option.field] ? String(fields[option.field]) : option.description}</FormHelperText>
            </Box>
          </Grid>)}</Grid>
          <Typography color="text.secondary" variant="body2">در هر سه لحن، توهین، تهدید، نشانی و اطلاعات خصوصی رد می‌شوند. لحن سوم شدت بیان را بیشتر می‌کند.</Typography>
        </Stack>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 6 }}><ManagementInput label="مدل نصب‌شدهٔ Ollama" name="ollama_model" dir="ltr" defaultValue={data.values.ollama_model} maxLength={100} required error={!!fields.ollama_model} helperText={fields.ollama_model ? String(fields.ollama_model) : undefined} /></Grid>
          <Grid size={{ xs: 12, md: 6 }}><ManagementInput label="مدل GapGPT" name="gapgpt_model" dir="ltr" defaultValue={data.values.gapgpt_model} maxLength={100} error={!!fields.gapgpt_model} helperText={fields.gapgpt_model ? String(fields.gapgpt_model) : data.gapgpt_credentials_configured ? "کلید روی سرور تنظیم شده است." : "کلید روی سرور تنظیم نشده است."} /></Grid>
          {numbers.map(([key, label, min, max]) => <Grid size={{ xs: 12, md: 6 }} key={key}><ManagementDigitInput label={label} name={key} type="number" min={min} max={max} step={1} defaultValue={data.values[key]} required error={!!fields[key]} helperText={fields[key] ? String(fields[key]) : undefined} /></Grid>)}
        </Grid>
        <Box><ManagementButton startIcon={<SaveIcon />}>{busy ? "در حال ذخیره…" : "ذخیرهٔ تنظیمات هوش مصنوعی"}</ManagementButton></Box>
      </Stack>
    </Stack>
  </Card>;
}

function LocalTest({ model, tones, onFailure }: { model: string; tones: MessageToneOption[]; onFailure: (error: unknown) => void }) {
  const [text, setText] = useState("بیشعور، لطفاً جلوی در پارک نکن، رفت‌وآمد سخت میشه.");
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [tone, setTone] = useState<MessageTone>(tones[0]?.id ?? 'polite');
  async function evaluate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setResult(null);
    try { setResult(await api<Result>("/manage/ai/test", { method: "POST", body: { text, message_tone: tone } })); }
    catch (failure) { setError(errorMessage(failure)); onFailure(failure); }
    finally { setBusy(false); }
  }
  return <Card component="form" onSubmit={evaluate} sx={{ p: { xs: 2, md: 3 } }}>
    <Stack spacing={3}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}><ScienceIcon color="primary" /><Typography variant="h6" component="h2">آزمایش واقعی مدل محلی</Typography></Stack>
      <Typography variant="body2" color="text.secondary">مدل ذخیره‌شده: <bdi>{model}</bdi>. این آزمایش فقط Ollama را صدا می‌زند؛ پیامکی ارسال و متن آزمایش ذخیره نمی‌شود.</Typography>
      <ManagementTextarea label="متن نمونه؛ اطلاعات خصوصی ننویسید" value={text} onChange={event => setText(event.target.value)} maxLength={280} rows={3} required />
      <ManagementSelect label="لحن آزمایش" value={tone} disabled={busy} onChange={event => setTone(event.target.value as MessageTone)}>{(tones.length ? tones : [{id:'polite',label:'مودبانه',description:''}]).map(option => <option key={option.id} value={option.id}>{option.label}</option>)}</ManagementSelect>
      <Box><ManagementButton className="secondary" startIcon={<ScienceIcon />} disabled={busy}>{busy ? "در حال بازنویسی و بازبینی…" : "آزمایش بازنویسی محلی"}</ManagementButton></Box>
      {error && <Alert severity="error">{error}</Alert>}
      <Stack spacing={1} aria-live="polite" aria-atomic="true">{result && <><Alert severity={result.allowed ? "success" : "warning"}>{result.allowed ? result.message : "این متن به شکل امن و با حفظ منظور قابل آماده‌سازی نبود."}</Alert><Typography variant="caption" color="text.secondary">زمان پاسخ: {managementNumber(result.elapsed_seconds)} ثانیه</Typography></>}</Stack>
    </Stack>
  </Card>;
}
