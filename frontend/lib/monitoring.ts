export const monitoringIntervals = [30, 60, 120, 300] as const;
export function monitoringInterval(value:unknown):number {
  const number=typeof value==='string'||typeof value==='number'?Number(value):0;
  return monitoringIntervals.some(item=>item===number)?number:30;
}
export type MonitoringMetricSeverity = 'normal' | 'warning' | 'error';
export function monitoringMetricSeverity(metric:'support_unanswered'|'oldest_queue_seconds',value:number):MonitoringMetricSeverity {
  const [warning,error]=metric==='support_unanswered'?[1,10]:[120,600];
  return value>=error?'error':value>=warning?'warning':'normal';
}
export type MonitoringData = {
  generated_at:string;
  window:{start:string;end:string;timezone:string};
  totals:{accounts_today:number;accounts_total:number;accounts_new:number;requests:number;delivered:number;support_unanswered:number};
  hourly:{at:string;accounts:number;requests:number}[];
  delivery:{status:string;count:number}[];
  moderation:{status:string;count:number}[];
  queue:{kind:string;status:string;count:number}[];
  operations:Record<string,number|boolean|null>;
  alerts:{code:string;severity:string;count:number}[];
  environment:{demo:boolean;sms:string;otp:string;payment:string;paid_enabled:boolean};
};
// A single in-flight request; visibility/offline pause aborts it and discards late data.
export function startMonitoringPoll<T>({request,active,intervalMs,onData,onError,schedule,cancel}:{
  request:(signal:AbortSignal)=>Promise<T>;active:()=>boolean;intervalMs:number;
  onData:(data:T)=>void;onError:(error:unknown)=>boolean;
  schedule:(callback:()=>void,ms:number)=>unknown;cancel:(timer:unknown)=>void;
}) {
  let stopped=false,running=false,timer:unknown,controller:AbortController|undefined;
  const clear=()=>{if(timer!==undefined){cancel(timer);timer=undefined;}};
  const stop=()=>{stopped=true;clear();controller?.abort();};
  async function run() {
    if(stopped||running||!active())return;
    clear();running=true;const current=new AbortController();controller=current;
    try {const result=await request(current.signal);if(!stopped&&!current.signal.aborted)onData(result);}
    catch(error){if(!stopped&&!current.signal.aborted&&onError(error))stop();}
    finally {running=false;controller=undefined;if(!stopped&&active())timer=schedule(()=>void run(),current.signal.aborted?0:intervalMs);}
  }
  const refresh=()=>{void run();};
  refresh();
  return {refresh,pause:()=>{clear();controller?.abort();},stop};
}
export const monitoringNumber=(value:number|null)=>value===null?'—':value.toLocaleString('fa-IR');
export function monitoringTime(value:string):string {
  return new Date(value).toLocaleTimeString('fa-IR',{timeZone:'Asia/Tehran',hour:'2-digit',minute:'2-digit'});
}
export function monitoringDuration(seconds:number):string {
  if(seconds<60)return `${monitoringNumber(seconds)} ثانیه`;
  if(seconds<3600)return `${monitoringNumber(Math.floor(seconds/60))} دقیقه`;
  return `${monitoringNumber(Math.floor(seconds/3600))} ساعت`;
}
export function monitoringAlertValue(code:string,count:number):string {
  return code==='queue_age'?`${monitoringDuration(count)} انتظار`:code==='budget_80_percent'?'بررسی بودجه':`${monitoringNumber(count)} مورد`;
}
