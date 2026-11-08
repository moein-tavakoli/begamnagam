"use client";
import Card from "@mui/material/Card";
import Stack from "@mui/material/Stack";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";
import FormControlLabel from "@mui/material/FormControlLabel";
import Box from "@mui/material/Box";
import RefreshIcon from "@mui/icons-material/Refresh";
import SaveIcon from "@mui/icons-material/Save";
import CreditCardIcon from "@mui/icons-material/CreditCard";

import { ManagementButton, ManagementInput } from "./management-ui";

import { managementReason } from "@/lib/management";

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api, errorMessage } from '@/lib/api';

type Configuration = { values:{enabled:boolean;card_number:string;card_holder:string;bank_name:string;bale_username:string;telegram_username:string};revision:number;ready:boolean;problem:string };
export function ManualPaymentSettings({onFailure}:{onFailure:(e:unknown)=>void}){
  const [config,setConfig]=useState<Configuration|null>(null),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  const load=useCallback(async()=>{try{setConfig(await api<Configuration>('/manage/manual-payment-settings'));setError('');}catch(e){setError(errorMessage(e));onFailure(e);}},[onFailure]);
  useEffect(()=>{void load();},[load]);
  async function save(event:FormEvent<HTMLFormElement>){
    event.preventDefault();const form=new FormData(event.currentTarget);if(!config)return;setBusy(true);setNotice('');setError('');
    try{setConfig(await api<Configuration>('/manage/manual-payment-settings',{method:'POST',body:{revision:config.revision,reason:managementReason("manual_settings"),values:{enabled:form.get('enabled')==='on',card_number:String(form.get('card_number')||''),card_holder:String(form.get('card_holder')||''),bank_name:String(form.get('bank_name')||''),bale_username:String(form.get('bale_username')||''),telegram_username:String(form.get('telegram_username')||'')}}}));setNotice('تنظیمات ذخیره شد. کارت‌به‌کارت فقط با تأیید رسید توسط ادمین اعتبار می‌دهد.');}
    catch(e){setError(errorMessage(e));onFailure(e);}finally{setBusy(false);}
  }
  return <Card component="section" sx={{ p: { xs: 2, md: 3 } }}><Stack spacing={3}>
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' } }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}><CreditCardIcon color="primary" /><Typography component="h2" variant="h6">کارت مقصد و دریافت رسید</Typography></Stack>
      <ManagementButton type="button" className="secondary" startIcon={<RefreshIcon />} disabled={busy} onClick={()=>void load()}>تازه‌سازی</ManagementButton>
    </Stack>
    <Alert severity="info">شمارهٔ کارت متعلق به دریافت‌کنندهٔ وجه است. برای رسید، شناسهٔ شخص پشتیبان را وارد کن که پیام خصوصی دریافت می‌کند. لینک کانال عمومی مناسب نیست. تصویر رسید در سایت ذخیره نمی‌شود.</Alert>
    {error && <Alert severity="error">{error}</Alert>}{notice && <Alert severity="success" role="status">{notice}</Alert>}
    {!config?<Typography role="status">در حال دریافت تنظیمات…</Typography>:<Stack component="form" spacing={3} onSubmit={save} key={config.revision}>
      {config.problem && <Alert severity="warning">{config.problem}</Alert>}
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 6 }}><ManagementInput label="شمارهٔ کارت مقصد" name="card_number" dir="ltr" inputMode="numeric" autoComplete="off" maxLength={24} defaultValue={config.values.card_number} placeholder="۱۶ رقم"/></Grid>
        <Grid size={{ xs: 12, md: 6 }}><ManagementInput label="نام صاحب کارت" name="card_holder" maxLength={80} defaultValue={config.values.card_holder}/></Grid>
        <Grid size={12}><ManagementInput label="نام بانک" name="bank_name" maxLength={80} defaultValue={config.values.bank_name||''} placeholder="مثلاً بانک ملت"/></Grid>
        <Grid size={{ xs: 12, md: 6 }}><ManagementInput label="شناسهٔ پشتیبان در بله" name="bale_username" dir="ltr" autoComplete="off" maxLength={33} defaultValue={config.values.bale_username} placeholder="username"/></Grid>
        <Grid size={{ xs: 12, md: 6 }}><ManagementInput label="شناسهٔ پشتیبان در تلگرام" name="telegram_username" dir="ltr" autoComplete="off" maxLength={33} defaultValue={config.values.telegram_username} placeholder="username"/></Grid>
      </Grid>
      <Typography variant="body2" color="text.secondary">فقط شناسه، بدون لینک؛ حداقل یکی لازم است. شمارهٔ کارت و مرجع‌های بانکی در دیتابیس رمز‌شده‌اند. تغییر کارت، درخواست‌های قبلی را تغییر نمی‌دهد.</Typography>
      <FormControlLabel control={<ManagementInput name="enabled" type="checkbox" defaultChecked={config.values.enabled}/>} label="خرید کارت‌به‌کارت در صفحهٔ پرداخت فعال باشد" />
      <Box><ManagementButton startIcon={<SaveIcon />} disabled={busy}>{busy?'در حال ذخیره…':'ذخیرهٔ تنظیمات'}</ManagementButton></Box>
    </Stack>}
  </Stack></Card>;
}
