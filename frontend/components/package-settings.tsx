"use client";
import Card from "@mui/material/Card";

import { ManagementButton, ManagementInput, ManagementDigitInput } from "./management-ui";

import { managementReason } from "@/lib/management";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, errorMessage, type MessagePackage } from "@/lib/api";
import { managementNumber } from "@/lib/management";
import { toman } from "@/lib/format";

export function PackageSettings({ onFailure }: { onFailure: (error: unknown) => void }) {
  const [packages, setPackages] = useState<MessagePackage[]>([]);
  const [editing, setEditing] = useState<MessagePackage | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setPackages((await api<{ packages: MessagePackage[] }>("/manage/packages")).packages); }
    catch (e) { setError(errorMessage(e)); onFailure(e); }
    finally { setLoading(false); }
  }, [onFailure]);
  useEffect(() => { void load(); }, [load]);
  return <>
    <div className="manage-section-heading"><div><h2>بسته‌های اعتبار پیام</h2><p className="manage-muted">کاربر فقط بسته‌های فعال را می‌بیند. هر ارسال یک اعتبار مصرف می‌کند.</p></div><ManagementButton className="manage-button primary" onClick={() => { setEditing(null); setNotice(""); }}>بستهٔ جدید</ManagementButton></div>
    {notice && <p role="status" className="manage-card">{notice}</p>}
    {error && <p role="alert">{error} <ManagementButton className="manage-button secondary" onClick={() => void load()}>تلاش دوباره</ManagementButton></p>}
    <Card component="section" className="manage-card"><p>تغییر یا غیرفعال‌کردن بسته، خریدهای ثبت‌شده و موجودی قبلی کاربران را تغییر نمی‌دهد. فعال‌کردن بسته به‌تنهایی درگاه پرداخت را فعال نمی‌کند.</p>
      {loading ? <p role="status">در حال دریافت بسته‌ها…</p> : <div className="package-admin-list">{packages.map(item => <article key={item.id}><div><strong>{item.name}</strong><p>{managementNumber(item.message_count)} پیام · {toman(item.price_toman)}</p><span className={`manage-badge ${item.active ? "good" : "neutral"}`}>{item.active ? "فعال" : "غیرفعال"}</span></div><ManagementButton className="manage-button secondary" onClick={() => { setEditing(item); setNotice(""); }}>ویرایش {item.name}</ManagementButton></article>)}</div>}
    </Card>
    <PackageForm key={editing ? `${editing.id}-${editing.revision}` : "new"} value={editing} onFailure={onFailure} onSaved={async () => { await load(); setEditing(null); setNotice("بسته ذخیره شد؛ فقط بسته‌های فعال در خرید نمایش داده می‌شوند."); }} />
  </>;
}

function PackageForm({ value, onSaved, onFailure }: { value: MessagePackage | null; onSaved: () => Promise<void>; onFailure: (e: unknown) => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget, data = new FormData(form); setBusy(true); setError("");
    try {
      await api(value ? `/manage/packages/${value.id}` : "/manage/packages", { method: "POST", body: {
        values: { name: String(data.get("name")), message_count: Number(data.get("message_count")), price_toman: Number(data.get("price_toman")), active: data.get("active") === "on", sort_order: Number(data.get("sort_order")) },
        revision: value?.revision ?? 0, reason: managementReason("packages"),
      } });
      form.reset(); await onSaved();
    } catch (e) { setError(errorMessage(e)); onFailure(e); }
    finally { setBusy(false); }
  }
  return <Card component="section" className="manage-card"><h2>{value ? `ویرایش ${value.name}` : "تعریف بستهٔ جدید"}</h2><form className="manage-form" onSubmit={submit}>
    {error && <p role="alert">{error}</p>}
    <label>نام بسته<ManagementInput name="name" maxLength={80} required defaultValue={value?.name ?? ""} /></label>
    <div className="manage-two-columns"><label>تعداد پیام<ManagementDigitInput name="message_count" type="number" inputMode="numeric" min={1} max={1000000} required defaultValue={value?.message_count ?? 3} /></label><label>قیمت کل بسته (تومان)<ManagementDigitInput name="price_toman" type="number" inputMode="numeric" min={1} max={2147483647} required defaultValue={value?.price_toman ?? 10000} /></label></div>
    <label>ترتیب نمایش<ManagementDigitInput name="sort_order" type="number" min={0} max={2147483647} required defaultValue={value?.sort_order ?? 0} /></label>
    <label className="checkbox-label"><ManagementInput name="active" type="checkbox" defaultChecked={value?.active ?? false} />این بسته فعال باشد و به کاربران نمایش داده شود</label>
    <ManagementButton className="manage-button primary" disabled={busy}>{busy ? "در حال ذخیره…" : "ذخیرهٔ بسته"}</ManagementButton>
  </form></Card>;
}
