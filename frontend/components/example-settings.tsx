"use client";
import Card from "@mui/material/Card";
import Stack from "@mui/material/Stack";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";
import Chip from "@mui/material/Chip";
import FormControlLabel from "@mui/material/FormControlLabel";
import Box from "@mui/material/Box";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import SaveIcon from "@mui/icons-material/Save";
import DeleteIcon from "@mui/icons-material/Delete";
import CloseIcon from "@mui/icons-material/Close";
import RefreshIcon from "@mui/icons-material/Refresh";
import FolderIcon from "@mui/icons-material/Folder";
import MessageIcon from "@mui/icons-material/Message";

import { ManagementButton, ManagementInput, ManagementSelect, ManagementTextarea, ManagementDigitInput } from "./management-ui";

import { managementReason } from "@/lib/management";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/lib/api";


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
  return <Stack spacing={3}>
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' } }}>
      <Stack spacing={1}><Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}><MessageIcon color="primary" /><Typography component="h2" variant="h6">پیام‌های نمونه</Typography></Stack><Typography variant="body2" color="text.secondary">دسته‌ها و متن‌هایی که به کاربر برای شروع نوشتن کمک می‌کنند.</Typography></Stack>
      <ManagementButton type="button" className="secondary" startIcon={<RefreshIcon />} disabled={loading} onClick={() => void load()}>تازه‌سازی</ManagementButton>
    </Stack>
    {error && <Alert severity="error">{error}</Alert>}{notice && <Alert severity="success" role="status">{notice}</Alert>}
    {loading && <Typography role="status">در حال دریافت…</Typography>}
    {data && <>
      <Card component="section" sx={{ p: { xs: 2, md: 3 } }}><Stack spacing={3}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' } }}>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}><FolderIcon color="primary" /><Typography component="h3" variant="subtitle1">دسته‌بندی‌ها</Typography></Stack>
          <ManagementButton type="button" startIcon={<AddIcon />} onClick={() => openEditor({ kind: "groups", value: null })}>دستهٔ جدید</ManagementButton>
        </Stack>
        <Stack direction="row" useFlexGap sx={{ flexWrap: 'wrap' }} spacing={1}>{data.groups.map(group => <ManagementButton type="button" className="secondary" startIcon={<EditIcon />} key={group.id} onClick={() => openEditor({ kind: "groups", value: group })}>
          {group.name} · {data.examples.filter(item => item.group_id === group.id).length.toLocaleString("fa-IR")} نمونه{!group.active && " · غیرفعال"}</ManagementButton>)}</Stack>
        {!data.groups.length && <Typography color="text.secondary">برای شروع یک دسته بسازید.</Typography>}
      </Stack></Card>
      <Card component="section" sx={{ p: { xs: 2, md: 3 } }}><Stack spacing={3}>
        <Grid container spacing={2} sx={{ alignItems: 'center' }}>
          <Grid size={{ xs: 12, sm: 8 }}><ManagementSelect label="نمایش دسته" id="catalog-filter" value={filter} onChange={e => setFilter(e.target.value)}><option value="">همه</option>{data.groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}</ManagementSelect></Grid>
          <Grid size={{ xs: 12, sm: 4 }}><ManagementButton type="button" startIcon={<AddIcon />} disabled={!data.groups.length} onClick={() => openEditor({ kind: "examples", value: null })}>نمونهٔ جدید</ManagementButton></Grid>
        </Grid>
        <Stack spacing={2}>{data.examples.filter(item => !filter || String(item.group_id) === filter).map(item => <Stack component="article" key={item.id} spacing={2} sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 2 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' } }}><Typography component="h3" variant="subtitle1">{item.label}</Typography><Chip size="small" color={item.active ? 'success' : 'default'} label={item.active ? "فعال" : "غیرفعال"} /></Stack>
          <Typography sx={{ overflowWrap: 'anywhere', whiteSpace: 'pre-wrap' }}>{item.text}</Typography>
          <Typography variant="caption" color="text.secondary">{data.groups.find(group => group.id === item.group_id)?.name}</Typography>
          <Box><ManagementButton type="button" className="secondary" startIcon={<EditIcon />} onClick={() => openEditor({ kind: "examples", value: item })}>ویرایش {item.label}</ManagementButton></Box>
        </Stack>)}</Stack>
        {!data.examples.length && <Typography color="text.secondary">هنوز نمونه‌ای ثبت نشده است.</Typography>}
      </Stack></Card>
      {edit && <CatalogEditor key={`${edit.kind}-${edit.value?.id ?? "new"}-${edit.value?.revision ?? 0}`} edit={edit} data={data} onCancel={() => setEdit(null)} onFailure={onFailure}
        onSaved={async () => { setEdit(null); await load(); setNotice("تغییر ذخیره شد؛ فهرست نمونه‌های سایت به‌روز است."); }} />}
    </>}
  </Stack>;
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
        method: "POST", body: { ...(deleting ? {} : { values }), revision: edit.value?.revision ?? 0, reason: managementReason(deleting ? "example_delete" : "example_save") },
      });
      await onSaved();
    } catch (e) { setError(errorMessage(e)); onFailure(e); }
    finally { setBusy(false); }
  }
  return <Card component="section" sx={{ p: { xs: 2, md: 3 } }}><Stack spacing={3}>
    <Typography component="h2" variant="h6" ref={title} tabIndex={-1}>{deleting ? "حذف" : edit.value ? "ویرایش" : "افزودن"} {edit.kind === "groups" ? "دسته" : "نمونه"}</Typography>
    <Stack component="form" spacing={3} onSubmit={submit}>
      {error && <Alert severity="error">{error}</Alert>}
      <Stack component="fieldset" disabled={busy} spacing={3} sx={{ border: 0, p: 0, m: 0, minWidth: 0 }}>
        {deleting ? <Alert severity="warning">«{edit.kind === "groups" ? edit.value?.name : edit.value?.label}» حذف شود؟ {edit.kind === "groups" && "دسته باید خالی باشد؛ برای پنهان‌کردن همهٔ نمونه‌ها می‌توانید آن را غیرفعال کنید."}</Alert> : <>
          {edit.kind === "groups" ? <ManagementInput label="نام دسته" name="name" required maxLength={60} defaultValue={edit.value?.name} /> : <>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, md: 6 }}><ManagementInput label="عنوان نمونه" name="label" required maxLength={60} defaultValue={edit.value?.label} /></Grid>
              <Grid size={{ xs: 12, md: 6 }}><ManagementSelect label="دسته" id="example-group" name="group_id" required defaultValue={edit.value?.group_id ?? data.groups[0]?.id}>{data.groups.map(group => <option key={group.id} value={group.id}>{group.name}{!group.active && " (غیرفعال)"}</option>)}</ManagementSelect></Grid>
              <Grid size={12}><ManagementTextarea label="متن نمونه" id="example-text" name="text" required minLength={3} maxLength={280} rows={3} defaultValue={edit.value?.text} /></Grid>
              <Grid size={12}><ManagementInput label="توضیح کوتاه" name="description" maxLength={160} defaultValue={edit.value?.description} /></Grid>
              <Grid size={12}><ManagementSelect label="موضوع متن آماده" id="example-topic" name="topic" defaultValue={edit.value?.topic ?? ""} helperText="موضوع مرتبط را انتخاب کنید تا نمونه در حالت متن آماده هم نمایش داده شود. متن نهایی همچنان پیش از ارسال بررسی و تأیید می‌شود."><option value="">فقط بازنویسی متن دلخواه</option>{data.topics.map(topic => <option key={topic.id} value={topic.id}>{topic.label}</option>)}</ManagementSelect></Grid>
            </Grid>
          </>}
          <ManagementDigitInput label="ترتیب نمایش" type="number" name="sort_order" min={0} max={10000} required defaultValue={edit.value?.sort_order ?? 0} />
          <FormControlLabel control={<ManagementInput type="checkbox" name="active" defaultChecked={edit.value?.active ?? true} />} label="نمایش در سایت" />
        </>}
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
          <ManagementButton type="submit" className={deleting ? 'danger' : ''} startIcon={deleting ? <DeleteIcon /> : <SaveIcon />}>{busy ? "در حال ذخیره…" : deleting ? "تأیید حذف" : "ذخیره"}</ManagementButton>
          <ManagementButton type="button" className="secondary" startIcon={<CloseIcon />} onClick={deleting ? () => setDeleting(false) : onCancel}>انصراف</ManagementButton>
          {edit.value && !deleting && <ManagementButton type="button" className="secondary danger" startIcon={<DeleteIcon />} onClick={() => { setDeleting(true); setError(""); }}>حذف</ManagementButton>}
        </Stack>
      </Stack>
    </Stack>
  </Stack></Card>;
}
