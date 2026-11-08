"use client";

import Link from 'next/link';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { useSearchParams } from 'next/navigation';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import LinearProgress from '@mui/material/LinearProgress';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import RefreshRounded from '@mui/icons-material/RefreshRounded';
import TvOutlined from '@mui/icons-material/TvOutlined';
import FullscreenExitRounded from '@mui/icons-material/FullscreenExitRounded';
import PeopleOutlined from '@mui/icons-material/PeopleOutlined';
import SmsOutlined from '@mui/icons-material/SmsOutlined';
import MarkEmailReadOutlined from '@mui/icons-material/MarkEmailReadOutlined';
import HourglassEmptyRounded from '@mui/icons-material/HourglassEmptyRounded';
import ScheduleRounded from '@mui/icons-material/ScheduleRounded';
import RuleOutlined from '@mui/icons-material/RuleOutlined';
import SupportAgentOutlined from '@mui/icons-material/SupportAgentOutlined';
import TimelineRounded from '@mui/icons-material/TimelineRounded';
import DonutLargeRounded from '@mui/icons-material/DonutLargeRounded';
import BarChartRounded from '@mui/icons-material/BarChartRounded';
import NotificationsActiveOutlined from '@mui/icons-material/NotificationsActiveOutlined';
import CheckCircleOutlineRounded from '@mui/icons-material/CheckCircleOutlineRounded';
import { LineChart } from '@mui/x-charts/LineChart';
import { PieChart } from '@mui/x-charts/PieChart';
import { BarChart } from '@mui/x-charts/BarChart';
import { api, ApiError, errorMessage } from '@/lib/api';
import { managementExplanation } from '@/lib/management';
import { monitoringIntervals, monitoringInterval, monitoringNumber as number, monitoringTime, monitoringDuration, monitoringAlertValue, startMonitoringPoll, type MonitoringData } from '@/lib/monitoring';

const settingsKey='management-monitoring-interval';
const axisText={fontFamily:'\"Vazirmatn FD\", \"Vazirmatn\", Tahoma, sans-serif',fontSize:12};
const chartSx={ '& .MuiChartsLegend-root':{fontFamily:'inherit',fontSize:12} };
const alertTitles:Record<string,string>={queue_age:'انتظار طولانی در صف',payment_unknown:'پرداخت با نتیجهٔ نامعلوم',delivery_unknown:'تحویل با نتیجهٔ نامعلوم',refund_open:'بازپرداخت ناتمام',reports_open:'گزارش بررسی‌نشده',budget_80_percent:'مصرف بیش از هشتاد درصد بودجه',recipient_controls_unavailable:'کنترل دریافت‌کننده در دسترس نیست'};
const colors={purple:'#6843ad',green:'#25846d',amber:'#b57609',red:'#ba3c54',blue:'#3378bb',gray:'#7f8695'};

function useMonitoring(interval:number,ready:boolean,onFailure:(error:unknown)=>void) {
  const [data,setData]=useState<MonitoringData|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[paused,setPaused]=useState('');
  const [reload,setReload]=useState<()=>void>(()=>()=>{});
  useEffect(()=>{
    if(!ready)return;
    let mounted=true;
    const active=()=>document.visibilityState==='visible'&&navigator.onLine;
    const poll=startMonitoringPoll<MonitoringData>({intervalMs:interval*1000,active,
      request:async signal=>{if(mounted)setBusy(true);try{return await api<MonitoringData>('/manage/monitoring',{signal});}finally{if(mounted)setBusy(false);}},
      onData:result=>{if(mounted){setData(result);setError('');}},
      onError:e=>{if(!mounted)return true;if(e instanceof ApiError&&['management_login_required','forbidden'].includes(e.code)){setData(null);setError('دسترسی به مانیتورینگ پایان یافت.');onFailure(e);return true;}setError(errorMessage(e));return false;},
      schedule:(fn,ms)=>window.setTimeout(fn,ms),cancel:id=>window.clearTimeout(id as number),
    });
    const changed=()=>{setPaused(!navigator.onLine?'ارتباط اینترنت قطع است':document.visibilityState!=='visible'?'به‌روزرسانی در تب پنهان متوقف است':'');if(active())poll.refresh();else poll.pause();};
    setReload(()=>poll.refresh);changed();
    document.addEventListener('visibilitychange',changed);window.addEventListener('online',changed);window.addEventListener('offline',changed);
    return ()=>{mounted=false;poll.stop();document.removeEventListener('visibilitychange',changed);window.removeEventListener('online',changed);window.removeEventListener('offline',changed);};
  },[interval,ready,onFailure]);
  return {data,error,busy,paused,reload};
}
function Panel({title,subtitle,icon,children}:{title:string;subtitle:string;icon:ReactNode;children:ReactNode}) {
  return <Card sx={{p:2,height:'100%',minWidth:0}}><Stack spacing={.5}><Stack direction="row" spacing={1} sx={{alignItems:'center'}}><Box sx={{color:'primary.main',display:'flex'}}>{icon}</Box><Typography component="h2" variant="subtitle1" sx={{fontWeight:700}}>{title}</Typography></Stack><Typography variant="caption" color="text.secondary">{subtitle}</Typography>{children}</Stack></Card>;
}
function Metric({title,value,detail,icon,warning=false}:{title:string;value:ReactNode;detail:string;icon:ReactNode;warning?:boolean}) {
  return <Card sx={{p:1.75,minWidth:0,borderTop:3,borderTopColor:warning?'warning.main':'divider'}}><Stack direction="row" sx={{alignItems:'center',justifyContent:'space-between',gap:1}}><Typography variant="body2" color="text.secondary">{title}</Typography><Box sx={{color:warning?'warning.main':'primary.main',display:'flex'}}>{icon}</Box></Stack><Typography variant="h4" component="p" sx={{my:.5,fontSize:{xs:26,xl:32},whiteSpace:'nowrap'}}>{value}</Typography><Typography variant="caption" color="text.secondary">{detail}</Typography></Card>;
}
function Donut({items,title}:{items:{label:string;value:number;color:string}[];title:string}) {
  const total=items.reduce((sum,item)=>sum+item.value,0);
  return <Box>
    <Box sx={{height:200,position:'relative',minWidth:0}}>
      {total>0?<PieChart aria-label={title} skipAnimation hideLegend height={200} margin={{top:8,bottom:8,left:8,right:8}} series={[{innerRadius:'68%',outerRadius:'90%',paddingAngle:2,cornerRadius:4,data:items.filter(x=>x.value>0).map((item,id)=>({...item,id})),valueFormatter:item=>`${number(item.value)} مورد`}]} sx={chartSx}/>:<Stack sx={{height:200,alignItems:'center',justifyContent:'center'}}><DonutLargeRounded sx={{fontSize:80,color:'divider'}}/><Typography variant="body2" color="text.secondary">در این بازه داده‌ای ثبت نشده</Typography></Stack>}
      {total>0&&<Stack sx={{position:'absolute',inset:0,alignItems:'center',justifyContent:'center',pointerEvents:'none'}}><Typography component="p" variant="h4">{number(total)}</Typography><Typography variant="caption" color="text.secondary">رکورد</Typography></Stack>}
    </Box>
    <Stack direction="row" useFlexGap sx={{flexWrap:'wrap',gap:.5,justifyContent:'center'}}>{items.map(item=><Chip key={item.label} size="small" variant="outlined" icon={<Box component="span" sx={{width:8,height:8,borderRadius:'50%',bgcolor:item.color}}/>} label={`${item.label}: ${number(item.value)}`}/>)}</Stack>
  </Box>;
}
function Charts({data}:{data:MonitoringData}) {
  const delivery=[
    {label:'رسیده',statuses:['delivered'],color:colors.green},
    {label:'در جریان',statuses:['not_ready','queued','submitting','accepted'],color:colors.blue},
    {label:'نامعلوم',statuses:['unknown'],color:colors.amber},
    {label:'ناموفق / متوقف',statuses:['failed','expired','suppressed'],color:colors.red},
    {label:'آزمایشی',statuses:['delivered_demo'],color:colors.purple},
    {label:'سایر',statuses:[],color:colors.gray},
  ].map(item=>({...item,value:data.delivery.filter(x=>item.statuses.length?item.statuses.includes(x.status):!['delivered','not_ready','queued','submitting','accepted','unknown','failed','expired','suppressed','delivered_demo'].includes(x.status)).reduce((sum,x)=>sum+x.count,0)}));
  const moderation=[{label:'تأییدشده',value:0,color:colors.green},{label:'ردشده',value:0,color:colors.red},{label:'سایر نتایج',value:0,color:colors.gray}];
  data.moderation.forEach(item=>{moderation[['accepted','allow'].includes(item.status)?0:['rejected','reject'].includes(item.status)?1:2].value+=item.count;});
  const queueStatuses=[{key:'pending',label:'در انتظار',color:colors.purple},{key:'submitting',label:'در حال ارسال',color:colors.blue},{key:'unknown',label:'نامعلوم',color:colors.amber}];
  return <Grid container spacing={2}>
      <Grid size={{xs:12,lg:6}}><Panel title="روند درخواست‌ها و کاربران" subtitle="۲۴ بازهٔ ساعتی تا اکنون · ساعت تهران · درخواست = سفارش ثبت‌شده" icon={<TimelineRounded/>}>
        <LineChart aria-label="روند ساعتی سفارش و کاربران تازه" height={235} skipAnimation
          xAxis={[{scaleType:'point',height:36,tickLabelStyle:axisText,data:data.hourly.map(item=>item.at),valueFormatter:monitoringTime,tickLabelInterval:(_,index)=>index%4===0}]}
          yAxis={[{width:36,tickLabelStyle:axisText,min:0,max:Math.max(1,...data.hourly.flatMap(item=>[item.accounts,item.requests])),tickMinStep:1,valueFormatter:(value:number)=>number(value)}]}
          series={[{id:'requests',label:'درخواست پیام',data:data.hourly.map(item=>item.requests),color:colors.purple,showMark:false,area:true,valueFormatter:v=>number(v)},{id:'accounts',label:'کاربر تازه',data:data.hourly.map(item=>item.accounts),color:colors.green,showMark:false,valueFormatter:v=>number(v)}]}
          grid={{horizontal:true}} margin={{top:15,bottom:30,left:40,right:15}} sx={chartSx}/>
      </Panel></Grid>
      <Grid size={{xs:12,sm:6,lg:3}}><Panel title="وضعیت تحویل" subtitle="وضعیت فعلی رکوردهای تحویل ساخته‌شده در بازه" icon={<DonutLargeRounded/>}><Donut title="توزیع وضعیت تحویل" items={delivery}/></Panel></Grid>
      <Grid size={{xs:12,sm:6,lg:3}}><Panel title="بررسی محتوا" subtitle="نتایج ثبت‌شده در بازه · هر بررسی یک رکورد" icon={<RuleOutlined/>}><Donut title="توزیع نتیجهٔ بررسی محتوا" items={moderation}/></Panel></Grid>
      <Grid size={{xs:12,lg:6}}><Panel title="صف فعال پیام‌ها و دعوت‌ها" subtitle="اکنون · موارد تکمیل‌شده یا بایگانی‌شده در این نمودار نیستند" icon={<BarChartRounded/>}>
        <BarChart aria-label="تعداد موارد فعال صف به تفکیک نوع و وضعیت" height={175} skipAnimation
          xAxis={[{scaleType:'band',height:36,tickLabelStyle:axisText,data:['پیام‌ها','دعوت‌ها']}]}
          yAxis={[{width:36,tickLabelStyle:axisText,min:0,max:Math.max(1,...data.queue.map(item=>item.count)),tickMinStep:1,valueFormatter:(value:number)=>number(value)}]}
          series={queueStatuses.map(status=>({id:status.key,label:status.label,color:status.color,data:['messages','invitations'].map(kind=>data.queue.filter(x=>x.kind===kind&&x.status===status.key).reduce((sum,x)=>sum+x.count,0)),valueFormatter:v=>number(v)}))}
          grid={{horizontal:true}} margin={{top:10,bottom:30,left:40,right:15}} sx={chartSx}/>
      </Panel></Grid>
      <Grid size={{xs:12,lg:6}}><Panel title="هشدارها و وضعیت عملیات" subtitle="تا ۵ هشدار ثبت‌شده با اولویت بالاتر" icon={<NotificationsActiveOutlined/>}>
        <Stack spacing={1} sx={{pt:1}}>
          <Stack direction="row" useFlexGap sx={{flexWrap:'wrap',gap:1}}><Chip color={data.operations.sending_halted?'warning':'success'} variant="outlined" label={data.operations.sending_halted?'ارسال متوقف است':'ارسال باز است'}/><Chip variant="outlined" label={`محیط ${data.environment.demo?'آزمایشی':'واقعی'}`}/><Chip variant="outlined" label={`پیامک: ${{kavenegar:'کاوه‌نگار',console:'کنسول',demo:'آزمایشی'}[data.environment.sms]||'سرویس تنظیم‌شده'}`}/><Chip variant="outlined" label={`ارائه‌دهندهٔ پرداخت: ${{zarinpal:'زرین‌پال',demo:'آزمایشی',disabled:'غیرفعال'}[data.environment.payment]||'سرویس تنظیم‌شده'}`}/></Stack>
          <Divider/>
          <Typography variant="body2" color="text.secondary">پرداخت نامعلوم: {number(Number(data.operations.payment_unknown||0))} · تحویل نیازمند بررسی: {number(Number(data.operations.delivery_unknown||0))} · گزارش باز: {number(Number(data.operations.reports_open||0))}</Typography>
          {data.alerts.length?<Stack spacing={.5}>{data.alerts.map((item,index)=><Alert key={`${item.code}-${index}`} severity={['critical','high'].includes(item.severity)?'error':'warning'} title={managementExplanation(item.code)} sx={{py:0,fontSize:12,lineHeight:1.5,'& .MuiAlert-icon':{py:.25,fontSize:18},'& .MuiAlert-message':{py:.25}}}>{alertTitles[item.code]||'هشدار عملیاتی نیازمند بررسی'} · {item.severity==='critical'?'بحرانی':item.severity==='high'?'شدید':'هشدار'} · {monitoringAlertValue(item.code,item.count)}</Alert>)}</Stack>:<Stack direction="row" spacing={1} sx={{alignItems:'center',color:'success.main',py:1}}><CheckCircleOutlineRounded/><Typography variant="body2">هشدار عملیاتی فعالی ثبت نشده است.</Typography></Stack>}
        </Stack>
      </Panel></Grid>
  </Grid>;
}
export function ManagementMonitoring({onFailure}:{onFailure:(error:unknown)=>void}) {
  const tv=useSearchParams().get('tv')==='1';
  const [interval,setInterval]=useState(30),[ready,setReady]=useState(false);
  useEffect(()=>{try{setInterval(monitoringInterval(localStorage.getItem(settingsKey)));}catch{}setReady(true);},[]);
  const changeInterval=useCallback((value:string)=>{const next=monitoringInterval(value);setInterval(next);try{localStorage.setItem(settingsKey,String(next));}catch{}},[]);
  const {data,error,busy,paused,reload}=useMonitoring(interval,ready,onFailure);
  return <Stack spacing={2} aria-label="مانیتورینگ سایت">
    <Card sx={{p:1.5}}><Stack direction={{xs:'column',sm:'row'}} useFlexGap sx={{justifyContent:'space-between',alignItems:{xs:'stretch',sm:'center'},gap:1.5}}>
      <Stack spacing={.25}><Stack direction="row" spacing={1} sx={{alignItems:'center'}}><Box sx={{width:9,height:9,borderRadius:'50%',bgcolor:error||paused?'warning.main':data?'success.main':'grey.400'}}/><Typography variant="subtitle1" sx={{fontWeight:700}}>{paused?'به‌روزرسانی متوقف':error?'داده‌ها به‌روز نیستند':data?'مانیتورینگ عملیاتی سایت':'در حال دریافت آمار'}</Typography></Stack><Typography variant="caption" color="text.secondary">{data?`آخرین دریافت: ${new Date(data.generated_at).toLocaleTimeString('fa-IR',{timeZone:'Asia/Tehran',hour:'2-digit',minute:'2-digit',second:'2-digit'})} · بازه: از ${new Date(data.window.start).toLocaleString('fa-IR',{timeZone:'Asia/Tehran',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})} تا اکنون`:'در انتظار نخستین پاسخ سرور'} · ساعت تهران</Typography></Stack>
      <Stack direction="row" useFlexGap sx={{gap:1,alignItems:'center',flexWrap:'wrap'}}>
        <TextField select label="دورهٔ به‌روزرسانی" value={interval} onChange={event=>changeInterval(event.target.value)} size="small" sx={{minWidth:155}}>{monitoringIntervals.map(seconds=><MenuItem key={seconds} value={seconds}>{seconds<60?`${number(seconds)} ثانیه`:`${number(seconds/60)} دقیقه`}</MenuItem>)}</TextField>
        <Button variant="outlined" onClick={reload} disabled={busy||!!paused||!ready} startIcon={<RefreshRounded/>}>تازه‌سازی</Button>
        <Button component={Link} href={tv?'/manage/monitoring':'/manage/monitoring?tv=1'} variant={tv?'outlined':'contained'} startIcon={tv?<FullscreenExitRounded/>:<TvOutlined/>}>{tv?'خروج از حالت نمایشگر':'حالت نمایشگر'}</Button>
      </Stack>
    </Stack></Card>
    {busy&&<LinearProgress aria-label="دریافت آمار مانیتورینگ" sx={{height:2,mb:'-18px !important',zIndex:1}}/>}
    {(error||paused)&&<Alert severity="warning">{paused||error}{data?' · آخرین دادهٔ موفق نمایش داده می‌شود؛ ممکن است قدیمی باشد.':' · هنوز اطلاعاتی دریافت نشده است.'}</Alert>}
    {data&&<>
      <Box sx={{display:'grid',gridTemplateColumns:{xs:'repeat(2,minmax(0,1fr))',sm:'repeat(3,minmax(0,1fr))',lg:'repeat(7,minmax(0,1fr))'},gap:1.5}}>
        <Metric title="کاربر تازه" value={number(data.totals.accounts_new)} detail="در بازهٔ نمودار" icon={<PeopleOutlined/>}/>
        <Metric title="درخواست پیام" value={number(data.totals.requests)} detail="سفارش ثبت‌شده در بازه" icon={<SmsOutlined/>}/>
        <Metric title="رسیده به گیرنده" value={number(data.totals.delivered)} detail="از رکوردهای تحویل این بازه" icon={<MarkEmailReadOutlined/>}/>
        <Metric title="در انتظار ارسال" value={number(Number(data.operations.outbox_pending||0))} detail="پیام‌ها و دعوت‌ها · اکنون" icon={<HourglassEmptyRounded/>}/>
        <Metric title="عمر قدیمی‌ترین صف" value={monitoringDuration(Number(data.operations.oldest_queue_seconds||0))} detail="از موارد فعال · اکنون" icon={<ScheduleRounded/>} warning={Number(data.operations.oldest_queue_seconds)>120}/>
        <Metric title="نتیجهٔ نامعلوم" value={number(Number(data.operations.payment_unknown||0)+Number(data.operations.delivery_unknown||0))} detail="پرداخت و تحویل · اکنون" icon={<RuleOutlined/>} warning={Number(data.operations.payment_unknown)+Number(data.operations.delivery_unknown)>0}/>
        <Metric title="پشتیبانی بی‌پاسخ" value={number(data.totals.support_unanswered)} detail="گفت‌وگوهای منتظر پاسخ" icon={<SupportAgentOutlined/>} warning={data.totals.support_unanswered>0}/>
      </Box>
      <Charts data={data}/>
    </>}
  </Stack>;
}
