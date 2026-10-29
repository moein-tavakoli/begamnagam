export type ProviderBalance = { provider:'kavenegar'|'gapgpt';status:'available'|'stale'|'updating'|'unavailable'|'unsupported'|'not_configured'|'disabled';amount:string|null;currency:'IRR'|null;observed_at:string|null;checked_at:string;reason:string|null };
const fa=new Intl.NumberFormat('fa-IR');
export function rialAsToman(value:string){
  if(!/^-?\d{1,19}$/.test(value))return null;
  const amount=BigInt(value),absolute=amount<0n?-amount:amount;
  const fraction=absolute%10n;
  return `${amount<0n?'−':''}${fa.format(absolute/10n)}${fraction?'٫'+fa.format(fraction):''} تومان`;
}
export function balanceLabel(value:ProviderBalance|null){
  if(!value)return 'در حال دریافت…';
  if((value.status==='available'||value.status==='stale') && value.currency==='IRR' && value.amount!==null)return rialAsToman(value.amount)??'پاسخ نامعتبر';
  return ({unsupported:'بررسی در پنل',not_configured:'کلید تنظیم نشده',disabled:'اتصال غیرفعال',unavailable:'فعلاً دریافت نشد',updating:'در حال استعلام…'} as Record<string,string>)[value.status]??'فعلاً دریافت نشد';
}
