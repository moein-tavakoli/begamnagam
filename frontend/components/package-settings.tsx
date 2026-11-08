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
import RefreshIcon from "@mui/icons-material/Refresh";
import Inventory2Icon from "@mui/icons-material/Inventory2";

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
  return <Stack spacing={3}>
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' } }}>
      <Stack spacing={1}><Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}><Inventory2Icon color="primary" /><Typography variant="h6" component="h2">بسته‌های اعتبار پیام</Typography></Stack><Typography variant="body2" color="text.secondary">کاربر فقط بسته‌های فعال را می‌بیند. هر ارسال یک اعتبار مصرف می‌کند.</Typography></Stack>
      <ManagementButton type="button" startIcon={<AddIcon />} onClick={() => { setEditing(null); setNotice(""); }}>بستهٔ جدید</ManagementButton>
    </Stack>
    {notice && <Alert severity="success" role="status">{notice}</Alert>}
    {error && <Alert severity="error" action={<ManagementButton type="button" className="secondary" startIcon={<RefreshIcon />} onClick={() => void load()}>تلاش دوباره</ManagementButton>}>{error}</Alert>}
    <Card component="section" sx={{ p: { xs: 2, md: 3 } }}><Stack spacing={3}>
      <Alert severity="info">تغییر یا غیرفعال‌کردن بسته، خریدهای ثبت‌شده و موجودی قبلی کاربران را تغییر نمی‌دهد. فعال‌کردن بسته به‌تنهایی درگاه پرداخت را فعال نمی‌کند.</Alert>
      {loading ? <Typography role="status">در حال دریافت بسته‌ها…</Typography> : <Grid container spacing={2}>{packages.map(item => <Grid key={item.id} size={{ xs: 12, md: 6 }}>
        <Stack component="article" spacing={2} sx={{ p: 2, height: '100%', border: 1, borderColor: 'divider', borderRadius: 2 }}>
          <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }} spacing={1}><Typography variant="subtitle1" component="h3">{item.name}</Typography><Chip size="small" color={item.active ? 'success' : 'default'} label={item.active ? "فعال" : "غیرفعال"} /></Stack>
          <Typography variant="body2" color="text.secondary">{managementNumber(item.message_count)} پیام · {toman(item.price_toman)}</Typography>
          <Box><ManagementButton type="button" className="secondary" startIcon={<EditIcon />} onClick={() => { setEditing(item); setNotice(""); }}>ویرایش {item.name}</ManagementButton></Box>
        </Stack>
      </Grid>)}</Grid>}
    </Stack></Card>
    <PackageForm key={editing ? `${editing.id}-${editing.revision}` : "new"} value={editing} onFailure={onFailure} onSaved={async () => { await load(); setEditing(null); setNotice("بسته ذخیره شد؛ فقط بسته‌های فعال در خرید نمایش داده می‌شوند."); }} />
  </Stack>;
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
  return <Card component="section" sx={{ p: { xs: 2, md: 3 } }}><Stack spacing={3}>
    <Typography variant="h6" component="h2">{value ? `ویرایش ${value.name}` : "تعریف بستهٔ جدید"}</Typography>
    <Stack component="form" spacing={3} onSubmit={submit}>
      {error && <Alert severity="error">{error}</Alert>}
      <Grid container spacing={2}>
        <Grid size={12}><ManagementInput label="نام بسته" name="name" maxLength={80} required defaultValue={value?.name ?? ""} /></Grid>
        <Grid size={{ xs: 12, md: 6 }}><ManagementDigitInput label="تعداد پیام" name="message_count" type="number" inputMode="numeric" min={1} max={1000000} required defaultValue={value?.message_count ?? 3} /></Grid>
        <Grid size={{ xs: 12, md: 6 }}><ManagementDigitInput label="قیمت کل بسته (تومان)" name="price_toman" type="number" inputMode="numeric" min={1} max={2147483647} required defaultValue={value?.price_toman ?? 10000} /></Grid>
        <Grid size={{ xs: 12, md: 6 }}><ManagementDigitInput label="ترتیب نمایش" name="sort_order" type="number" min={0} max={2147483647} required defaultValue={value?.sort_order ?? 0} /></Grid>
      </Grid>
      <FormControlLabel control={<ManagementInput name="active" type="checkbox" defaultChecked={value?.active ?? false} />} label="این بسته فعال باشد و به کاربران نمایش داده شود" />
      <Box><ManagementButton startIcon={<SaveIcon />} disabled={busy}>{busy ? "در حال ذخیره…" : "ذخیرهٔ بسته"}</ManagementButton></Box>
    </Stack>
  </Stack></Card>;
}
