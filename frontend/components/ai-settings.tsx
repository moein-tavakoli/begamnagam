"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import { managementNumber } from "@/lib/management";
import type { MessageTone, MessageToneOption } from '@/lib/message-tones';

type ToneFlag = 'tone_polite_enabled' | 'tone_firm_enabled' | 'tone_angry_enabled';
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
  return <>
    {error && <p className="manage-error" role="alert">{error}</p>}
    {!data ? <p role="status">در حال دریافت تنظیمات هوش مصنوعی…</p> : <>
      <div className="manage-notice">بازنویسی و بازبینی در همان درخواست انجام می‌شوند. متن نهایی پیش از ارسال به تأیید فرستنده می‌رسد. اگر سرویس مشغول یا نامطمئن باشد، خطا نمایش داده می‌شود و سرویس دیگری خودکار جایگزین نمی‌شود.</div>
      {saved && <p className="manage-success" role="status">تنظیمات برای درخواست‌های تازه ذخیره شد.</p>}
      <Configuration key={data.revision} data={data} onSaved={updated => { setData(updated); setSaved(true); }} onFailure={onFailure} />
      <LocalTest key={`test-${data.revision}`} model={data.values.ollama_model} tones={data.tone_options.filter(option => data.values[option.field])} onFailure={onFailure} />
    </>}
    <button type="button" className="manage-button secondary" onClick={() => void load()}>دریافت آخرین تنظیمات</button>
  </>;
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
      const updated = await api<Settings>("/manage/ai", { method: "POST", body: { values, revision: data.revision, reason: form.get("reason") } });
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
  return <form className="manage-card manage-form" onSubmit={save}>
    <h2>سرویس فعال هوش مصنوعی</h2>
    {error && <p className="manage-error" role="alert">{error}</p>}
    <fieldset disabled={busy} className="manage-fieldset">
      <label>سرویس<select value={provider} onChange={event => setProvider(event.target.value)} aria-describedby="ai-provider-help">
        <option value="template">خاموش — متن‌های آماده</option><option value="ollama">Ollama — مدل محلی</option><option value="gapgpt">GapGPT — سرویس بیرونی</option>
      </select><small id="ai-provider-help">{fields.provider ? String(fields.provider) : provider === "ollama" ? "متن روی همین زیرساخت پردازش می‌شود." : provider === "gapgpt" ? "فعال‌سازی به کلید سرور، مدل و سهمیهٔ مثبت GapGPT نیاز دارد." : "بازنویسی دلخواه غیرفعال می‌شود."}</small></label>
      <section className="manage-tone-settings" aria-labelledby="manage-tone-title"><h3 id="manage-tone-title">لحن‌های قابل انتخاب کاربران</h3>
        <p className="manage-muted">فقط گزینه‌های تیک‌خورده، زیر کادر متن کاربر نمایش داده می‌شوند. بدون تیک، انتخاب لحن پنهان و حالت مودبانه برقرار می‌شود. تغییر برای پیش‌نمایش‌های تازه است.</p>
        <div className="manage-tone-grid">{data.tone_options.map(option => <label className="manage-checkbox" key={option.id}>
          <span>{option.label}</span><input type="checkbox" name={option.field} defaultChecked={data.values[option.field]} aria-describedby={`help-${option.field}`} aria-invalid={!!fields[option.field]} />
          <small id={`help-${option.field}`} className={fields[option.field] ? 'manage-field-error' : ''}>{fields[option.field] ? String(fields[option.field]) : option.description}</small>
        </label>)}</div><p className="manage-muted">در هر سه لحن، توهین، تهدید، نشانی و اطلاعات خصوصی رد می‌شوند. لحن سوم شدت بیان را بیشتر می‌کند.</p>
      </section>
      <div className="manage-settings-grid">
        <label>مدل نصب‌شدهٔ Ollama<input name="ollama_model" dir="ltr" defaultValue={data.values.ollama_model} maxLength={100} required aria-invalid={!!fields.ollama_model} />{fields.ollama_model && <small className="manage-field-error">{String(fields.ollama_model)}</small>}</label>
        <label>مدل GapGPT<input name="gapgpt_model" dir="ltr" defaultValue={data.values.gapgpt_model} maxLength={100} aria-invalid={!!fields.gapgpt_model} /><small>{fields.gapgpt_model ? String(fields.gapgpt_model) : data.gapgpt_credentials_configured ? "کلید روی سرور تنظیم شده است." : "کلید روی سرور تنظیم نشده است."}</small></label>
        {numbers.map(([key, label, min, max]) => <label key={key}>{label}<input name={key} type="number" min={min} max={max} step={1} defaultValue={data.values[key]} required aria-invalid={!!fields[key]} />{fields[key] && <small className="manage-field-error">{String(fields[key])}</small>}</label>)}
      </div>
      <label>دلیل تغییر<input name="reason" required minLength={3} maxLength={200} placeholder="دلیل کوتاه؛ اطلاعات خصوصی ننویسید" /></label>
      <button className="manage-button primary">{busy ? "در حال ذخیره…" : "ذخیرهٔ تنظیمات هوش مصنوعی"}</button>
    </fieldset>
  </form>;
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
  return <form className="manage-card manage-form" onSubmit={evaluate}>
    <h2>آزمایش واقعی مدل محلی</h2><p className="manage-muted">مدل ذخیره‌شده: <bdi>{model}</bdi>. این آزمایش فقط Ollama را صدا می‌زند؛ پیامکی ارسال و متن آزمایش ذخیره نمی‌شود.</p>
    <label>متن نمونه؛ اطلاعات خصوصی ننویسید<textarea value={text} onChange={event => setText(event.target.value)} maxLength={280} rows={3} required /></label>
    <label>لحن آزمایش<select value={tone} disabled={busy} onChange={event => setTone(event.target.value as MessageTone)}>{(tones.length ? tones : [{id:'polite',label:'مودبانه',description:''}]).map(option => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
    <button className="manage-button secondary" disabled={busy}>{busy ? "در حال بازنویسی و بازبینی…" : "آزمایش بازنویسی محلی"}</button>
    {error && <p className="manage-error" role="alert">{error}</p>}
    <div aria-live="polite" aria-atomic="true">{result && <><p className={result.allowed ? "manage-success" : "manage-notice"}>{result.allowed ? result.message : "این متن به شکل امن و با حفظ منظور قابل آماده‌سازی نبود."}</p><small>زمان پاسخ: {managementNumber(result.elapsed_seconds)} ثانیه</small></>}</div>
  </form>;
}
