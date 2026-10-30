"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/lib/api";
import { DigitInput } from "./digit-input";

type Group = { id: number; name: string; active: boolean; sort_order: number; revision: number };
type Example = { id: number; group_id: number; label: string; description: string; text: string; topic: string; active: boolean; sort_order: number; revision: number };
type Catalog = { groups: Group[]; examples: Example[]; topics: { id: string; label: string }[] };
type Edit = { kind: "groups"; value: Group | null } | { kind: "examples"; value: Example | null };

export function ExampleSettings({ onFailure }: { onFailure: (error: unknown) => void }) {
  const [data, setData] = useState<Catalog | null>(null);
  const [edit, setEdit] = useState<Edit | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setError(""); setLoading(true);
    try { setData(await api<Catalog>("/manage/message-examples")); }
    catch (e) { setError(errorMessage(e)); onFailure(e); }
    finally { setLoading(false); }
  }, [onFailure]);
  useEffect(() => { void load(); }, [load]);
  function openEditor(next: Edit) { setNotice(""); setError(""); setEdit(next); }
  return <>
    <div className="manage-section-heading"><div><h2>پیام‌های نمونه</h2><p className="manage-muted">دسته‌ها و متن‌هایی که به کاربر برای شروع نوشتن کمک می‌کنند.</p></div>
      <button className="manage-button secondary" disabled={loading} onClick={() => void load()}>تازه‌سازی</button></div>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {loading && <p role="status">در حال دریافت…</p>}
    {data && <>
      <section className="manage-card"><div className="manage-section-heading"><h3>دسته‌بندی‌ها</h3><button className="manage-button primary" onClick={() => openEditor({ kind: "groups", value: null })}>دستهٔ جدید</button></div>
        <div className="example-admin-groups">{data.groups.map(group => <button className="manage-button secondary" key={group.id} onClick={() => openEditor({ kind: "groups", value: group })}>
          {group.name} · {data.examples.filter(item => item.group_id === group.id).length.toLocaleString("fa-IR")} نمونه{!group.active && " · غیرفعال"}</button>)}</div>
        {!data.groups.length && <p>برای شروع یک دسته بسازید.</p>}
      </section>
      <section className="manage-card"><div className="manage-section-heading"><div><label htmlFor="catalog-filter">نمایش دسته</label><select id="catalog-filter" value={filter} onChange={e => setFilter(e.target.value)}><option value="">همه</option>{data.groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}</select></div>
        <button className="manage-button primary" disabled={!data.groups.length} onClick={() => openEditor({ kind: "examples", value: null })}>نمونهٔ جدید</button></div>
        <div className="example-admin-list">{data.examples.filter(item => !filter || String(item.group_id) === filter).map(item => <article key={item.id}>
          <div><strong>{item.label}</strong><p>{item.text}</p><small>{data.groups.find(group => group.id === item.group_id)?.name} · {item.active ? "فعال" : "غیرفعال"}</small></div>
          <button className="manage-button secondary" onClick={() => openEditor({ kind: "examples", value: item })}>ویرایش {item.label}</button>
        </article>)}</div>
        {!data.examples.length && <p>هنوز نمونه‌ای ثبت نشده است.</p>}
      </section>
      {edit && <CatalogEditor key={`${edit.kind}-${edit.value?.id ?? "new"}-${edit.value?.revision ?? 0}`} edit={edit} data={data} onCancel={() => setEdit(null)} onFailure={onFailure}
        onSaved={async () => { setEdit(null); await load(); setNotice("تغییر ذخیره شد؛ فهرست نمونه‌های سایت به‌روز است."); }} />}
    </>}
  </>;
}

function CatalogEditor({ edit, data, onCancel, onSaved, onFailure }: { edit: Edit; data: Catalog; onCancel: () => void; onSaved: () => Promise<void>; onFailure: (e: unknown) => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [deleting, setDeleting] = useState(false);
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => { title.current?.focus(); }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return;
    const form = new FormData(event.currentTarget);
    const values = { active: form.get("active") === "on", sort_order: Number(form.get("sort_order")),
      ...(edit.kind === "groups" ? { name: String(form.get("name")) } : {
        group_id: Number(form.get("group_id")), label: String(form.get("label")), description: String(form.get("description")), text: String(form.get("text")), topic: String(form.get("topic")),
      }) };
    setBusy(true); setError("");
    try {
      await api(`/manage/message-examples/${edit.kind}${edit.value ? `/${edit.value.id}` : ""}${deleting ? "/delete" : ""}`, {
        method: "POST", body: { ...(deleting ? {} : { values }), revision: edit.value?.revision ?? 0, reason: form.get("reason") },
      });
      await onSaved();
    } catch (e) { setError(errorMessage(e)); onFailure(e); }
    finally { setBusy(false); }
  }
  return <section className="manage-card"><h2 ref={title} tabIndex={-1}>{deleting ? "حذف" : edit.value ? "ویرایش" : "افزودن"} {edit.kind === "groups" ? "دسته" : "نمونه"}</h2>
    <form className="manage-form" onSubmit={submit}>
      {error && <p role="alert">{error}</p>}
      <fieldset disabled={busy} className="manage-fieldset">
        {deleting ? <p>«{edit.kind === "groups" ? edit.value?.name : edit.value?.label}» حذف شود؟ {edit.kind === "groups" && "دسته باید خالی باشد؛ برای پنهان‌کردن همهٔ نمونه‌ها می‌توانید آن را غیرفعال کنید."}</p> : <>
          {edit.kind === "groups" ? <label>نام دسته<input name="name" required maxLength={60} defaultValue={edit.value?.name} /></label> : <>
            <label>عنوان نمونه<input name="label" required maxLength={60} defaultValue={edit.value?.label} /></label>
            <div><label htmlFor="example-group">دسته</label><select id="example-group" name="group_id" required defaultValue={edit.value?.group_id ?? data.groups[0]?.id}>{data.groups.map(group => <option key={group.id} value={group.id}>{group.name}{!group.active && " (غیرفعال)"}</option>)}</select></div>
            <div><label htmlFor="example-text">متن نمونه</label><textarea id="example-text" name="text" required minLength={3} maxLength={280} rows={3} defaultValue={edit.value?.text} /></div>
            <label>توضیح کوتاه<input name="description" maxLength={160} defaultValue={edit.value?.description} /></label>
            <div><label htmlFor="example-topic">موضوع متن آماده</label><select id="example-topic" name="topic" defaultValue={edit.value?.topic ?? ""}><option value="">فقط بازنویسی متن دلخواه</option>{data.topics.map(topic => <option key={topic.id} value={topic.id}>{topic.label}</option>)}</select></div>
            <p className="manage-muted">موضوع مرتبط را انتخاب کنید تا نمونه در حالت متن آماده هم نمایش داده شود. متن نهایی همچنان پیش از ارسال بررسی و تأیید می‌شود.</p>
          </>}
          <label>ترتیب نمایش<DigitInput type="number" name="sort_order" min={0} max={10000} required defaultValue={edit.value?.sort_order ?? 0} /></label>
          <label className="checkbox-label"><input type="checkbox" name="active" defaultChecked={edit.value?.active ?? true} />نمایش در سایت</label>
        </>}
        <label>دلیل تغییر<input name="reason" required minLength={3} maxLength={200} /></label>
        <div className="example-admin-actions"><button type="submit" className="manage-button primary">{busy ? "در حال ذخیره…" : deleting ? "تأیید حذف" : "ذخیره"}</button>
          <button type="button" className="manage-button secondary" onClick={deleting ? () => setDeleting(false) : onCancel}>انصراف</button>
          {edit.value && !deleting && <button type="button" className="manage-button secondary" onClick={() => { setDeleting(true); setError(""); }}>حذف</button>}
        </div>
      </fieldset>
    </form>
  </section>;
}
