"use client";

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
    <p className="manage-muted">{grant?'شناسهٔ حساب':'شناسهٔ درخواست'}: <bdi className="manage-dialog-id">{action.object_id}</bdi></p>
    {error && <p role="alert" className="manage-error">{error}</p>}
    <form className="manage-form" onSubmit={submit}>
      {!reject && <><p className="manage-notice">فقط پس از مشاهدهٔ واریز قطعی در حساب بانکی تأیید کن؛ تصویر رسید به‌تنهایی کافی نیست. مبلغ باید دقیقاً با بسته تطبیق داشته باشد. تأیید این فرم، اعتبار بسته را بلافاصله اضافه می‌کند.</p>
        {grant?<label>بستهٔ فعال<ManagementSelect value={selected??''} disabled={busy || submitted} required onChange={e=>setSelected(Number(e.target.value))}>{!packages.length && <option value="">بستهٔ فعالی موجود نیست</option>}{packages.map(p=><option key={p.id} value={p.id}>{p.name} · {p.message_count.toLocaleString('fa-IR')} پیام · {toman(p.price_toman)}</option>)}</ManagementSelect></label>:<p>مبلغ ثبت‌شده: <strong>{toman(action.manualPayment?.amount_toman??0)}</strong></p>}
        <label>مبلغ واریزِ تأییدشده (تومان)<ManagementDigitInput name="amount_toman" type="number" inputMode="numeric" min={1} max={2147483647} step={1} required defaultValue={action.manualPayment?.amount_toman}/></label>
        <label>مرجع واریز در صورتحساب بانک<ManagementInput name="bank_reference" dir="ltr" inputMode="numeric" minLength={6} maxLength={64} autoComplete="off" required/></label>
        <label>تاریخ واریز (میلادی)<ManagementDigitInput name="paid_date" type="date" dir="ltr" max={today()} defaultValue={today()} required/></label>
        <label className="checkbox-label"><ManagementInput type="checkbox" name="bank_verified" required/>واریز قطعی، مبلغ و مرجع را در حساب بانک بررسی و با این خرید تطبیق دادم.</label>
      </>}
      {reject && <p className="manage-notice">درخواست با پیام «رسید بانکی تأیید نشد» رد می‌شود. اگر وجهی دریافت شده، رد درخواست جای بازپرداخت را نمی‌گیرد.</p>}
      <ManagementButton className={`manage-button ${reject?'danger':'primary'}`} disabled={busy || (grant && !chosen)}>{busy?'در حال ثبت…':reject?'ثبت رد رسید':'تأیید و فعال‌سازی بسته'}</ManagementButton>
    </form>
  </ManagementDialog>;
}
