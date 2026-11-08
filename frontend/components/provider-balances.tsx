"use client";
import { useEffect, useRef, useState } from 'react';
import { api, errorMessage } from '@/lib/api';
import { balanceLabel, type ProviderBalance } from '@/lib/provider-balances';
import Grid from '@mui/material/Grid';
import Card from '@mui/material/Card';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Avatar from '@mui/material/Avatar';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import SmsOutlined from '@mui/icons-material/SmsOutlined';
import AutoAwesomeOutlined from '@mui/icons-material/AutoAwesomeOutlined';
import OpenInNewRounded from '@mui/icons-material/OpenInNewRounded';


export function ProviderBalances({onFailure}:{onFailure:(e:unknown)=>void}){
  return <Grid container spacing={2} component="section" aria-label="اعتبار سرویس‌های متصل"><Grid size={{xs:12,sm:6}}><Balance provider="kavenegar" onFailure={onFailure}/></Grid><Grid size={{xs:12,sm:6}}><Balance provider="gapgpt" onFailure={onFailure}/></Grid></Grid>;
}
function Balance({provider,onFailure}:{provider:'kavenegar'|'gapgpt';onFailure:(e:unknown)=>void}){
  const [value,setValue]=useState<ProviderBalance|null>(null),[error,setError]=useState('');
  const failure=useRef(onFailure);failure.current=onFailure;
  useEffect(()=>{
    let disposed=false,running=false,timer:ReturnType<typeof setTimeout>|undefined,controller:AbortController|undefined,failures=0;
    async function load(){
      if(disposed||running||document.hidden||!navigator.onLine)return;
      running=true;controller=new AbortController();let wait=60000;
      try{
        const result=await api<ProviderBalance>(`/manage/provider-balances/${provider}`,{signal:controller.signal});
        if(!disposed){setValue(result);setError('');failures=0;if(result.status==='updating')wait=3000;}
      }catch(e){if(!disposed&&!controller.signal.aborted){setValue(null);setError(errorMessage(e));failure.current(e);failures++;wait=Math.min(60000,10000*2**Math.min(failures,3));}}
      finally{running=false;if(!disposed)timer=setTimeout(()=>void load(),wait);}
    }
    const resume=()=>{if(timer)clearTimeout(timer);if(!document.hidden&&navigator.onLine)void load();};
    const visible=()=>{if(document.hidden){if(timer)clearTimeout(timer);controller?.abort();}else resume();};
    void load();window.addEventListener('focus',resume);window.addEventListener('online',resume);document.addEventListener('visibilitychange',visible);
    return()=>{disposed=true;if(timer)clearTimeout(timer);controller?.abort();window.removeEventListener('focus',resume);window.removeEventListener('online',resume);document.removeEventListener('visibilitychange',visible);};
  },[provider]);
  const label=provider==='kavenegar'?'اعتبار پیامک':'اعتبار GapGPT';
  const stale=value?.status==='stale';
  const time=value?.observed_at?new Intl.DateTimeFormat('fa-IR',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tehran'}).format(new Date(value.observed_at)):null;
  const message=error?'ارتباط با سرویس برقرار نشد':stale?(value.reason==='refresh_in_progress'?'آخرین موجودی؛ در حال استعلام':'آخرین موجودی؛ استعلام تازه ناموفق'):value?.status==='unsupported'?'API موجودی تأیید نشده':value?.status==='available'?`استعلام ${time} · تا ۲ دقیقه تأخیر`:value?.status==='not_configured'?'کلید خصوصی سرویس لازم است':value?.status==='disabled'?'پروفایل اتصال خارجی فعال نیست':value?.status==='unavailable'?(value.reason==='access_denied'?'دسترسی به موجودی مجاز نیست':'دوباره به‌صورت خودکار بررسی می‌شود'):'';
  return <Card component="article" aria-label={label} sx={{p:2.5,height:'100%',bgcolor:stale?'#fffaf0':'background.paper'}}>
    <Stack direction="row" spacing={2} sx={{alignItems:'center'}}>
      <Avatar variant="rounded" sx={{bgcolor:'primary.light',color:'primary.contrastText'}}>{provider==='kavenegar'?<SmsOutlined/>:<AutoAwesomeOutlined/>}</Avatar>
      <Stack spacing={1} sx={{minWidth:0}}><Typography component="h2" variant="subtitle2" color="text.secondary">{label}{provider==='kavenegar'?' کاوه‌نگار':''}</Typography>
        <Stack direction="row" spacing={1} sx={{alignItems:'center',flexWrap:'wrap'}} aria-live="polite" aria-atomic="true">
          {provider==='gapgpt'?<Button variant="outlined" size="small" href="https://gapgpt.app/platform-v2/wallet" target="_blank" rel="noopener noreferrer" aria-label="بازکردن کیف پول GapGPT در زبانهٔ جدید" endIcon={<OpenInNewRounded/>}>بررسی در پنل</Button>:<Typography variant="h6">{error?'فعلاً دریافت نشد':balanceLabel(value)}</Typography>}
          {stale&&<Chip size="small" label="قدیمی" color="warning" variant="outlined"/>}
        </Stack><Typography variant="caption" color="text.secondary" title={stale&&time?`آخرین استعلام موفق: ${time}`:undefined}>{message}</Typography>
      </Stack>
    </Stack>
  </Card>;
}
