"use client";
import Stack from "@mui/material/Stack";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";
import FormControlLabel from "@mui/material/FormControlLabel";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";

import { ManagementButton, ManagementInput, ManagementSelect, ManagementDigitInput, ManagementDialog } from "./management-ui";

import { managementReason } from "@/lib/management";



import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, createIdempotencyKey, errorMessage, type Bootstrap, type MessagePackage } from '@/lib/api';
import { toman } from '@/lib/format';
import type { ManagementAction } from '@/lib/management';

function today(){const date=new Date();return new Intl.DateTimeFormat('en-CA',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:'Asia/Tehran'}).format(date);}
export function ManualPaymentDialog({action,onClose,onComplete,onFailure}:{action:ManagementAction;onClose:()=>void;onComplete:()=>void;onFailure:(e:unknown)=>void}){
  const key=useRef(createIdempotencyKey());
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[submitted,setSubmitted]=useState(false);
  const [packages,setPackages]=useState<MessagePackage[]>([]),[selected,setSelected]=useState<number|null>(null);
  const grant=action.name==='grant_package',reject=action.name==='reject_card';
  const chosen=packages.find(p=>p.id===selected);
  useEffect(()=>{if(!grant)return;const controller=new AbortController();void api<Bootstrap>('/bootstrap',{signal:controller.signal}).then(data=>{setPackages(data.message_packages??[]);setSelected(data.message_packages?.[0]?.id??null);}).catch(e=>{if(!controller.signal.aborted){setError(errorMessage(e));onFailure(e);}});return()=>controller.abort();},[grant,onFailure]);
  async function submit(event:FormEvent<HTMLFormElement>){
    event.preventDefault();const form=new FormData(event.currentTarget);setBusy(true);setError('');setSubmitted(true);
    try{
      const proof={reason:managementReason(action.name),bank_reference:form.get('bank_reference'),paid_date:form.get('paid_date'),amount_toman:Number(form.get('amount_toman')),bank_verified:form.get('bank_verified')==='on'};
      if(grant){if(!chosen)throw new Error('بسته را انتخاب کن.');await api('/manage/manual-payments/grant',{method:'POST',idempotencyKey:key.current,body:{...proof,account_id:Number(action.object_id),package_id:chosen.id,package_revision:chosen.revision}});}
      else await api(`/manage/manual-payments/${action.object_id}/${reject?'reject':'approve'}`,{method:'POST',body:reject?{reason:managementReason(action.name)}:proof});
      onComplete();
    }catch(e){setError(errorMessage(e));onFailure(e);}finally{setBusy(false);}
  }
  return <ManagementDialog title={action.label} onClose={onClose} busy={busy}>
    <Stack spacing={3}>
      <Typography variant="body2" color="text.secondary">{grant?'شناسهٔ حساب':'شناسهٔ درخواست'}: <Typography component="bdi" variant="inherit" sx={{ overflowWrap: 'anywhere' }}>{action.object_id}</Typography></Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <Stack component="form" spacing={3} onSubmit={submit}>
        {!reject && <>
          <Alert severity="warning">فقط پس از مشاهدهٔ واریز قطعی در حساب بانکی تأیید کن؛ تصویر رسید به‌تنهایی کافی نیست. مبلغ باید دقیقاً با بسته تطبیق داشته باشد. تأیید این فرم، اعتبار بسته را بلافاصله اضافه می‌کند.</Alert>
          {grant?<ManagementSelect label="بستهٔ فعال" value={selected??''} disabled={busy || submitted} required onChange={e=>setSelected(Number(e.target.value))}>{!packages.length && <option value="">بستهٔ فعالی موجود نیست</option>}{packages.map(p=><option key={p.id} value={p.id}>{p.name} · {p.message_count.toLocaleString('fa-IR')} پیام · {toman(p.price_toman)}</option>)}</ManagementSelect>:<Typography>مبلغ ثبت‌شده: <Typography component="strong" sx={{ fontWeight: 700 }}>{toman(action.manualPayment?.amount_toman??0)}</Typography></Typography>}
          <Grid container spacing={2}>
            <Grid size={12}><ManagementDigitInput label="مبلغ واریزِ تأییدشده (تومان)" name="amount_toman" type="number" inputMode="numeric" min={1} max={2147483647} step={1} required defaultValue={action.manualPayment?.amount_toman}/></Grid>
            <Grid size={12}><ManagementInput label="مرجع واریز در صورتحساب بانک" name="bank_reference" dir="ltr" inputMode="numeric" minLength={6} maxLength={64} autoComplete="off" required/></Grid>
            <Grid size={12}><ManagementDigitInput label="تاریخ واریز (میلادی)" name="paid_date" type="date" dir="ltr" max={today()} defaultValue={today()} required/></Grid>
          </Grid>
          <FormControlLabel control={<ManagementInput type="checkbox" name="bank_verified" required/>} label="واریز قطعی، مبلغ و مرجع را در حساب بانک بررسی و با این خرید تطبیق دادم." />
        </>}
        {reject && <Alert severity="warning">درخواست با پیام «رسید بانکی تأیید نشد» رد می‌شود. اگر وجهی دریافت شده، رد درخواست جای بازپرداخت را نمی‌گیرد.</Alert>}
        <ManagementButton className={reject?'danger':''} startIcon={reject?<CancelIcon />:<CheckCircleIcon />} disabled={busy || (grant && !chosen)}>{busy?'در حال ثبت…':reject?'ثبت رد رسید':'تأیید و فعال‌سازی بسته'}</ManagementButton>
      </Stack>
    </Stack>
  </ManagementDialog>;
}
