"use client";

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import Link from 'next/link';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import LanOutlined from '@mui/icons-material/LanOutlined';
import RefreshRounded from '@mui/icons-material/RefreshRounded';
import SaveOutlined from '@mui/icons-material/SaveOutlined';
import MonitorOutlined from '@mui/icons-material/MonitorOutlined';
import { api, ApiError, errorMessage } from '@/lib/api';
import { ManagementTextarea } from './management-ui';

type Settings = { ips:string[]; revision:number; current_ip:string|null };

export function MonitoringAccessSettings({onFailure}:{onFailure:(error:unknown)=>void}) {
  const [data,setData]=useState<Settings|null>(null),[text,setText]=useState('');
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false);
  const [error,setError]=useState(''),[fieldError,setFieldError]=useState(''),[saved,setSaved]=useState(false);
  const load=useCallback(async()=>{
    setLoading(true);setError('');setFieldError('');setSaved(false);
    try { const result=await api<Settings>('/manage/monitoring/settings');setData(result);setText(result.ips.join('\n')); }
    catch(e){setData(null);setText('');setError(errorMessage(e));onFailure(e);}
    finally{setLoading(false);}
  },[onFailure]);
  useEffect(()=>{void load();},[load]);
  async function save(event:FormEvent<HTMLFormElement>){
    event.preventDefault();if(!data||busy)return;
    setBusy(true);setError('');setFieldError('');setSaved(false);
    try{
      const result=await api<Settings>('/manage/monitoring/settings',{method:'PUT',body:{
        ips:text.split(/\r?\n/).map(value=>value.trim()).filter(Boolean),revision:data.revision,
      }});
      setData(result);setText(result.ips.join('\n'));setSaved(true);
    }catch(e){setError(errorMessage(e));if(e instanceof ApiError)setFieldError(String(e.fields?.ips||''));onFailure(e);}
    finally{setBusy(false);}
  }
  return <Card component="form" onSubmit={save} sx={{p:{xs:2,sm:3}}}>
    <Stack spacing={2.5}>
      <Stack direction="row" spacing={1} sx={{alignItems:'center'}}><LanOutlined color="primary"/><Typography component="h2" variant="h6">IPهای مجاز سامانه</Typography></Stack>
      <Alert severity="info">فقط مانیتورینگ از IPهای این فهرست بدون نام کاربری و رمز باز می‌شود. همهٔ دستگاه‌هایی که از یک IP مشترک به سایت وصل می‌شوند، این دسترسی را دارند. سایر بخش‌ها همچنان نیاز به ورود و مجوز دارند.</Alert>
      {error&&<Alert severity="error">{error}</Alert>}
      {saved&&<Alert severity="success">فهرست ذخیره شد. IPهای حذف‌شده از درخواست بعدی برای مشاهدهٔ مانیتورینگ باید وارد شوند.</Alert>}
      {loading?<Stack direction="row" spacing={1} role="status"><CircularProgress size={20}/><Typography>در حال دریافت IPهای مجاز…</Typography></Stack>:data&&<>
        <Typography variant="body2" color="text.secondary">IP اتصال فعلی: {data.current_ip?<Box component="span" dir="ltr" sx={{display:'inline-block'}}>{data.current_ip}</Box>:'قابل تشخیص نیست؛ تنظیم شبکهٔ سرور را بررسی کنید.'}</Typography>
        <Box component="fieldset" disabled={busy} sx={{border:0,p:0,m:0,minWidth:0}}><Stack spacing={2}>
          <ManagementTextarea label="IPهای مجاز مانیتورینگ" name="ips" dir="ltr" rows={5} value={text}
            onChange={event=>{setText(event.target.value);setSaved(false);}}
            maxLength={2500} autoComplete="off" spellCheck={false} error={!!fieldError}
            helperText={fieldError||'هر خط یک IP دقیق IPv4 یا IPv6؛ حداکثر ۵۰ مورد. دامنه و بازهٔ IP مجاز نیست. برای لغو همهٔ دسترسی‌های بدون ورود، فهرست را خالی ذخیره کنید.'}/>
          <Stack direction={{xs:'column',sm:'row'}} useFlexGap sx={{gap:1,flexWrap:'wrap'}}>
            <Button type="submit" variant="contained" startIcon={<SaveOutlined/>}>{busy?'در حال ذخیره…':'ذخیرهٔ IPهای مجاز'}</Button>
            <Button type="button" variant="outlined" onClick={()=>void load()} startIcon={<RefreshRounded/>}>دریافت آخرین فهرست</Button>
            <Button component={Link} href="/manage/monitoring" startIcon={<MonitorOutlined/>}>بازکردن مانیتورینگ</Button>
          </Stack>
        </Stack></Box>
      </>}
      {!data&&!loading&&<Button type="button" onClick={()=>void load()} startIcon={<RefreshRounded/>}>تلاش دوباره</Button>}
    </Stack>
  </Card>;
}
