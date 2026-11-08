"use client";

import { useEffect, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import HistoryOutlined from '@mui/icons-material/HistoryOutlined';
import NewReleasesOutlined from '@mui/icons-material/NewReleasesOutlined';
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded';
import RefreshRounded from '@mui/icons-material/RefreshRounded';
import LockOutlined from '@mui/icons-material/LockOutlined';
import { api, errorMessage } from '@/lib/api';
import { managementDate } from '@/lib/management';

type ReleaseHistory = {
  locale: string; catalog_version: string; notice: string;
  entries: { version: string; title: string; date: string | null; scope: 'local' | 'history'; changes: string[] }[];
};

export function ManagementChangelog({onFailure}:{onFailure:(error:unknown)=>void}) {
  const [data,setData]=useState<ReleaseHistory|null>(null);
  const [error,setError]=useState('');
  const [retry,setRetry]=useState(0);
  const [visible,setVisible]=useState(10);
  useEffect(()=>{
    const controller=new AbortController();setError('');setData(null);
    void api<ReleaseHistory>('/manage/changelog',{signal:controller.signal}).then(result=>{if(!controller.signal.aborted)setData(result);}).catch(e=>{if(!controller.signal.aborted){setError(errorMessage(e));onFailure(e);}});
    return()=>controller.abort();
  },[retry,onFailure]);
  return <Stack spacing={3}>
    <Stack spacing={1}><Stack direction="row" spacing={1} sx={{alignItems:'center'}}><HistoryOutlined color="primary"/><Typography component="h2" variant="h5">تاریخچهٔ تغییرات فارسی</Typography></Stack><Chip icon={<LockOutlined/>} label="فقط برای مدیران" variant="outlined" size="small" sx={{alignSelf:'flex-start'}}/></Stack>
    {error?<Alert severity="error" action={<Button onClick={()=>setRetry(n=>n+1)} startIcon={<RefreshRounded/>}>تلاش دوباره</Button>}>{error}</Alert>:!data?<Stack direction="row" spacing={1} sx={{alignItems:'center'}} role="status"><CircularProgress size={20}/><Typography>در حال دریافت تاریخچه…</Typography></Stack>:<>
      <Alert severity="info">{data.notice}</Alert>
      {data.entries.slice(0,visible).map((entry,index)=><Card component="article" key={entry.version} sx={{p:{xs:2,sm:3}}}><Stack spacing={2}>
        <Stack direction="row" spacing={1} useFlexGap sx={{alignItems:'center',flexWrap:'wrap'}}><NewReleasesOutlined color={index===0?'primary':'disabled'}/><Chip label={entry.version} color={index===0?'primary':'default'} size="small"/><Chip label={entry.scope==='local'?'نسخهٔ محلی':'سابقهٔ نسخه'} variant="outlined" size="small"/>{entry.date&&<Typography variant="caption" color="text.secondary">ثبت: {managementDate(entry.date)}</Typography>}</Stack>
        <Typography component="h3" variant="h6">{entry.title}</Typography>
        <Stack component="ul" spacing={1} sx={{m:0,paddingInlineStart:2.5}}>{entry.changes.map((change,i)=><Typography component="li" variant="body2" key={i}>{change}</Typography>)}</Stack>
      </Stack></Card>)}
      {visible<data.entries.length&&<Box sx={{textAlign:'center'}}><Button variant="outlined" startIcon={<ExpandMoreRounded/>} onClick={()=>setVisible(n=>n+10)}>نمایش نسخه‌های قدیمی‌تر</Button></Box>}
    </>}
  </Stack>;
}
