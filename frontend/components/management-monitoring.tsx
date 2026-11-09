"use client";

import Link from 'next/link';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { keyframes } from '@emotion/react';
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
import useMediaQuery from '@mui/material/useMediaQuery';
import RefreshRounded from '@mui/icons-material/RefreshRounded';
import ArrowForwardRounded from '@mui/icons-material/ArrowForwardRounded';
import { alpha, type Theme } from '@mui/material/styles';
import GroupsOutlined from '@mui/icons-material/GroupsOutlined';
import BlockOutlined from '@mui/icons-material/BlockOutlined';
import PeopleOutlined from '@mui/icons-material/PeopleOutlined';
import SmsOutlined from '@mui/icons-material/SmsOutlined';
import MarkEmailReadOutlined from '@mui/icons-material/MarkEmailReadOutlined';
import MonitorHeartOutlined from '@mui/icons-material/MonitorHeartOutlined';
import HourglassEmptyRounded from '@mui/icons-material/HourglassEmptyRounded';
import ScheduleRounded from '@mui/icons-material/ScheduleRounded';
import RuleOutlined from '@mui/icons-material/RuleOutlined';
import SupportAgentOutlined from '@mui/icons-material/SupportAgentOutlined';
import TimelineRounded from '@mui/icons-material/TimelineRounded';
import DonutLargeRounded from '@mui/icons-material/DonutLargeRounded';
import BarChartRounded from '@mui/icons-material/BarChartRounded';
import NotificationsActiveOutlined from '@mui/icons-material/NotificationsActiveOutlined';
import CheckCircleOutlineRounded from '@mui/icons-material/CheckCircleOutlineRounded';
import { LineChart, lineClasses } from '@mui/x-charts/LineChart';
import { PieChart } from '@mui/x-charts/PieChart';
import { BarChart } from '@mui/x-charts/BarChart';
import { axisClasses } from '@mui/x-charts/ChartsAxis';
import { chartsGridClasses } from '@mui/x-charts/ChartsGrid';
import { api, ApiError, errorMessage } from '@/lib/api';
import { managementExplanation } from '@/lib/management';
import { monitoringIntervals, monitoringInterval, monitoringNumber as number, monitoringTime, monitoringDuration, monitoringAlertValue, monitoringMetricSeverity, startMonitoringPoll, type MonitoringData, type MonitoringMetricSeverity } from '@/lib/monitoring';

const settingsKey='management-monitoring-interval';
const compactDesktopQuery='(min-width:1200px) and (max-height:900px)';
const compactDesktop=`@media ${compactDesktopQuery}`;
const axisText={fontFamily:'\"Vazirmatn FD\", \"Vazirmatn\", Tahoma, sans-serif',fontSize:12};
const chartSx=(theme:Theme)=>({
  '& .MuiChartsLegend-root': {fontFamily:'inherit',fontSize:12,color:theme.palette.text.secondary},
  [`& .${axisClasses.tickLabel}`]: {fill:theme.palette.text.secondary},
  [`& .${axisClasses.line}, & .${axisClasses.tick}`]: {stroke:theme.palette.divider},
  [`& .${chartsGridClasses.line}`]: {stroke:alpha(theme.palette.info.main,.21),strokeDasharray:'3 4'},
});
const alertTitles:Record<string,string>={queue_age:'انتظار طولانی در صف',payment_unknown:'پرداخت با نتیجهٔ نامعلوم',delivery_unknown:'تحویل با نتیجهٔ نامعلوم',refund_open:'بازپرداخت ناتمام',reports_open:'گزارش بررسی‌نشده',budget_80_percent:'مصرف بیش از هشتاد درصد بودجه',recipient_controls_unavailable:'کنترل دریافت‌کننده در دسترس نیست'};
const colors={purple:'#ce97ff',cyan:'#62e6f5',green:'#68edb2',amber:'#ffc07b',red:'#ff8197',blue:'#8da7ff',gray:'#9aa8c5'};
const panelSurface={
  borderRadius: '16px 16px 16px 6px',
  backgroundImage: 'linear-gradient(150deg, #171d36, #10162b 50%, #0e1427)',
  boxShadow: '0 8px 24px #03061352',
};
const signalPulse=keyframes`
  0% { transform: scale(1); opacity: .5; }
  78%, 100% { transform: scale(2.6); opacity: 0; }
`;

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
  return <Card sx={{...panelSurface,p:2,height:'100%',minWidth:0,[compactDesktop]:{p:1.5}}}>
    <Stack spacing={.5}>
      <Stack direction="row" spacing={1} sx={{alignItems:'center'}}>
        <Box sx={theme=>({color:'primary.main',display:'flex',p:.5,borderRadius:1,bgcolor:alpha(theme.palette.primary.main,.09)})}>{icon}</Box>
        <Typography component="h2" variant="subtitle1" sx={{fontWeight:700}}>{title}</Typography>
      </Stack>
      <Typography variant="caption" color="text.secondary">{subtitle}</Typography>
      {children}
    </Stack>
  </Card>;
}
function Metric({title,value,detail,icon,severity,accent}:{title:string;value:ReactNode;detail:string;icon:ReactNode;severity?:MonitoringMetricSeverity;accent?:'primary'|'secondary'}) {
  const tone=severity&&severity!=='normal'?severity:accent;
  const severityLabels={normal:'عادی',warning:'نیازمند توجه',error:'نیازمند رسیدگی فوری'};
  return <Card sx={theme=>{
    const tint=theme.palette[tone ?? 'info'].main;
    return {
      ...panelSurface,
      '--metric-tint': tint,
      '--metric-icon-bg': alpha(tint,.12),
      position: 'relative',
      p: 1.75,
      minWidth: 0,
      height: '100%',
      borderColor: tone ? alpha(tint,.42) : 'divider',
      backgroundImage: `linear-gradient(145deg, ${alpha(tint,tone ? .15 : .035)}, transparent 76%), ${panelSurface.backgroundImage}`,
      '&::before': {
        content: '""',
        position: 'absolute',
        inset: '0 0 auto',
        height: 2,
        background: `linear-gradient(90deg, transparent, ${alpha(tint,tone ? .92 : .55)}, transparent)`,
      },
      '&::after': {
        content: '""',position:'absolute',insetInlineEnd:7,bottom:7,width:8,height:8,
        borderBlockEnd:`1px solid ${alpha(tint,.55)}`,borderInlineEnd:`1px solid ${alpha(tint,.55)}`,
      },
      [compactDesktop]: {p:1.25},
    };
  }}>
    <Stack spacing={.75} sx={{height:'100%',[compactDesktop]:{'& > :not(style) ~ :not(style)':{mt:.4}}}}>
      <Stack direction="row" sx={{alignItems:'center',justifyContent:'space-between',gap:.75}}>
        <Typography variant="body2" color="text.secondary" sx={{fontWeight:600,[compactDesktop]:{fontSize:12,lineHeight:1.55}}}>{title}</Typography>
        <Box sx={{color:'var(--metric-tint)',display:'flex',p:.5,borderRadius:1,bgcolor:'var(--metric-icon-bg)',[compactDesktop]:{p:.35,'& .MuiSvgIcon-root':{fontSize:19}}}}>{icon}</Box>
      </Stack>
      <Typography variant="h4" component="p" sx={{
        fontSize:accent?{xs:34,xl:40}:{xs:26,xl:32},
        fontWeight:accent?800:700,
        lineHeight:1.3,
        fontVariantNumeric:'tabular-nums',
        overflowWrap:'anywhere',
        color:tone?'var(--metric-tint)':'text.primary',
        textShadow:accent?'0 0 18px var(--metric-icon-bg)':undefined,
        [compactDesktop]:{fontSize:accent?34:27,lineHeight:1.2},
      }}>{value}</Typography>
      <Typography variant="caption" color="text.secondary" sx={{flex:1}}>{detail}</Typography>
      {severity&&<Typography variant="caption" sx={{fontWeight:700,color:severity==='normal'?'text.secondary':'var(--metric-tint)'}}>{severityLabels[severity]}</Typography>}
    </Stack>
  </Card>;
}
function Donut({items,title,height=200}:{items:{label:string;value:number;color:string}[];title:string;height?:number}) {
  const total=items.reduce((sum,item)=>sum+item.value,0);
  return <Box>
    <Box sx={{height,position:'relative',minWidth:0}}>
      {total>0?<PieChart aria-label={title} skipAnimation hideLegend height={height} margin={{top:8,bottom:8,left:8,right:8}} series={[{innerRadius:'68%',outerRadius:'90%',paddingAngle:2,cornerRadius:4,data:items.filter(x=>x.value>0).map((item,id)=>({...item,id})),valueFormatter:item=>`${number(item.value)} مورد`}]} sx={chartSx}/>:<Stack spacing={1} sx={{height,alignItems:'center',justifyContent:'center'}}>
        <Box sx={{display:'grid',placeItems:'center',width:height<200?52:80,aspectRatio:1,borderRadius:'50%',border:'1px dashed',borderColor:'divider',color:'info.main',backgroundImage:'radial-gradient(circle, #202c55, transparent 72%)'}}><DonutLargeRounded sx={{fontSize:height<200?30:46}}/></Box>
        <Typography variant="body2" color="text.secondary" sx={{[compactDesktop]:{fontSize:12}}}>در این بازه داده‌ای ثبت نشده</Typography>
      </Stack>}
      {total>0&&<Stack sx={{position:'absolute',inset:0,alignItems:'center',justifyContent:'center',pointerEvents:'none'}}><Typography component="p" variant="h4">{number(total)}</Typography><Typography variant="caption" color="text.secondary">رکورد</Typography></Stack>}
    </Box>
    <Stack direction="row" useFlexGap sx={{flexWrap:'wrap',gap:.5,justifyContent:'center'}}>{items.map(item=><Chip key={item.label} size="small" variant="outlined" icon={<Box component="span" sx={{width:8,height:8,borderRadius:'50%',bgcolor:item.color}}/>} label={`${item.label}: ${number(item.value)}`}/>)}</Stack>
  </Box>;
}
function Charts({data}:{data:MonitoringData}) {
  const compact=useMediaQuery(compactDesktopQuery,{noSsr:true});
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
  return <Grid container spacing={compact?1.5:2}>
      <Grid size={{xs:12,lg:6}}><Panel title="روند درخواست‌ها و کاربران" subtitle="۲۴ بازهٔ ساعتی تا اکنون · ساعت تهران · درخواست = سفارش ثبت‌شده" icon={<TimelineRounded/>}>
        <LineChart aria-label="روند ساعتی سفارش و کاربران تازه" height={compact?180:235} skipAnimation
          xAxis={[{scaleType:'point',height:36,tickLabelStyle:axisText,data:data.hourly.map(item=>item.at),valueFormatter:monitoringTime,tickLabelInterval:(_,index)=>index%4===0}]}
          yAxis={[{width:36,tickLabelStyle:axisText,min:0,max:Math.max(1,...data.hourly.flatMap(item=>[item.accounts,item.requests])),tickMinStep:1,valueFormatter:(value:number)=>number(value)}]}
          series={[{id:'requests',label:'درخواست پیام',data:data.hourly.map(item=>item.requests),color:colors.purple,showMark:false,area:true,valueFormatter:v=>number(v)},{id:'accounts',label:'کاربر تازه',data:data.hourly.map(item=>item.accounts),color:colors.cyan,showMark:false,valueFormatter:v=>number(v)}]}
          grid={{horizontal:true}} margin={{top:15,bottom:30,left:40,right:15}} sx={theme=>({
            ...chartSx(theme),
            [`& .${lineClasses.line}`]: {strokeWidth:2.5},
            [`& .${lineClasses.area}[data-series="requests"]`]: {fill:'url(#monitoring-requests-fill)',fillOpacity:1},
          })}>
          <defs><linearGradient id="monitoring-requests-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={colors.purple} stopOpacity={.38}/>
            <stop offset="100%" stopColor={colors.purple} stopOpacity={.025}/>
          </linearGradient></defs>
        </LineChart>
      </Panel></Grid>
      <Grid size={{xs:12,sm:6,lg:3}}><Panel title="وضعیت تحویل" subtitle="وضعیت فعلی رکوردهای تحویل ساخته‌شده در بازه" icon={<DonutLargeRounded/>}><Donut title="توزیع وضعیت تحویل" items={delivery} height={compact?126:200}/></Panel></Grid>
      <Grid size={{xs:12,sm:6,lg:3}}><Panel title="بررسی محتوا" subtitle="نتایج ثبت‌شده در بازه · هر بررسی یک رکورد" icon={<RuleOutlined/>}><Donut title="توزیع نتیجهٔ بررسی محتوا" items={moderation} height={compact?126:200}/></Panel></Grid>
      <Grid size={{xs:12,lg:6}}><Panel title="صف فعال پیام‌ها و دعوت‌ها" subtitle="اکنون · موارد تکمیل‌شده یا بایگانی‌شده در این نمودار نیستند" icon={<BarChartRounded/>}>
        <BarChart aria-label="تعداد موارد فعال صف به تفکیک نوع و وضعیت" height={compact?120:175} skipAnimation
          xAxis={[{scaleType:'band',height:36,tickLabelStyle:axisText,data:['پیام‌ها','دعوت‌ها']}]}
          yAxis={[{width:36,tickLabelStyle:axisText,min:0,max:Math.max(1,...data.queue.map(item=>item.count)),tickMinStep:1,valueFormatter:(value:number)=>number(value)}]}
          series={queueStatuses.map(status=>({id:status.key,label:status.label,color:status.color,data:['messages','invitations'].map(kind=>data.queue.filter(x=>x.kind===kind&&x.status===status.key).reduce((sum,x)=>sum+x.count,0)),valueFormatter:v=>number(v)}))}
          grid={{horizontal:true}} margin={{top:10,bottom:30,left:40,right:15}} sx={chartSx}/>
      </Panel></Grid>
      <Grid size={{xs:12,lg:6}}><Panel title="هشدارها و وضعیت عملیات" subtitle="تا ۵ هشدار ثبت‌شده با اولویت بالاتر" icon={<NotificationsActiveOutlined/>}>
        <Stack spacing={1} sx={{pt:1,[compactDesktop]:{pt:.5,maxHeight:160,overflowY:'auto','& .MuiChip-root':{height:24,fontSize:12},'& .MuiTypography-body2':{fontSize:12,lineHeight:1.5}}}}>
          <Stack direction="row" useFlexGap sx={{flexWrap:'wrap',gap:1}}><Chip color={data.operations.sending_halted?'warning':'success'} variant="outlined" label={data.operations.sending_halted?'ارسال متوقف است':'ارسال باز است'}/><Chip variant="outlined" label={`محیط ${data.environment.demo?'آزمایشی':'واقعی'}`}/><Chip variant="outlined" label={`پیامک: ${{kavenegar:'کاوه‌نگار',console:'کنسول',demo:'آزمایشی'}[data.environment.sms]||'سرویس تنظیم‌شده'}`}/><Chip variant="outlined" label={`ارائه‌دهندهٔ پرداخت: ${{zarinpal:'زرین‌پال',demo:'آزمایشی',disabled:'غیرفعال'}[data.environment.payment]||'سرویس تنظیم‌شده'}`}/></Stack>
          <Divider/>
          <Typography variant="body2" color="text.secondary">پرداخت نامعلوم: {number(Number(data.operations.payment_unknown||0))} · تحویل نیازمند بررسی: {number(Number(data.operations.delivery_unknown||0))} · گزارش باز: {number(Number(data.operations.reports_open||0))}</Typography>
          {data.alerts.length?<Stack spacing={.5}>{data.alerts.map((item,index)=><Alert key={`${item.code}-${index}`} severity={['critical','high'].includes(item.severity)?'error':'warning'} title={managementExplanation(item.code)} sx={{py:0,fontSize:12,lineHeight:1.5,'& .MuiAlert-icon':{py:.25,fontSize:18},'& .MuiAlert-message':{py:.25}}}>{alertTitles[item.code]||'هشدار عملیاتی نیازمند بررسی'} · {item.severity==='critical'?'بحرانی':item.severity==='high'?'شدید':'هشدار'} · {monitoringAlertValue(item.code,item.count)}</Alert>)}</Stack>:<Stack direction="row" spacing={1} sx={{alignItems:'center',color:'success.main',py:1}}><CheckCircleOutlineRounded/><Typography variant="body2">هشدار عملیاتی فعالی ثبت نشده است.</Typography></Stack>}
        </Stack>
      </Panel></Grid>
  </Grid>;
}
export function ManagementMonitoring({onFailure}:{onFailure:(error:unknown)=>void}) {
  const [interval,setInterval]=useState(30),[ready,setReady]=useState(false);
  useEffect(()=>{try{setInterval(monitoringInterval(localStorage.getItem(settingsKey)));}catch{}setReady(true);},[]);
  const changeInterval=useCallback((value:string)=>{const next=monitoringInterval(value);setInterval(next);try{localStorage.setItem(settingsKey,String(next));}catch{}},[]);
  const {data,error,busy,paused,reload}=useMonitoring(interval,ready,onFailure);
  const signalTone=error||paused?'warning':data?'success':'info';
  const signalText=error||paused?(data?'دادهٔ قدیمی':'وقفه در دریافت'):data?'داده به‌روز':'در انتظار داده';
  return <Stack spacing={1.5} aria-label="مانیتورینگ سایت">
    <Card sx={{
      ...panelSurface,
      p:{xs:1.5,sm:2},
      position:'relative',
      backgroundImage:'linear-gradient(110deg, #341d4c, #1e2245 40%, #103342)',
      '&::before': {
        content:'""',position:'absolute',inset:'0 0 auto',height:2,
        background:'linear-gradient(90deg, #ed9af9, #a9b6ff 42%, #62e6f5)',
        boxShadow:'0 0 16px #9e9eff80',
      },
    }}>
      <Stack direction={{xs:'column',md:'row'}} useFlexGap sx={{justifyContent:'space-between',alignItems:{xs:'stretch',md:'center'},gap:1.5}}>
        <Stack direction="row" useFlexGap sx={{alignItems:'center',gap:1.5,minWidth:0}}>
          <Box sx={theme=>({
            width:{xs:44,sm:52},height:{xs:44,sm:52},flexShrink:0,display:'grid',placeItems:'center',
            borderRadius:'12px 12px 12px 4px',border:'1px solid',borderColor:alpha(theme.palette.primary.main,.43),
            color:'primary.main',backgroundImage:`linear-gradient(155deg, ${alpha(theme.palette.primary.main,.19)}, #0c192e)`,
            boxShadow:`0 0 20px ${alpha(theme.palette.primary.main,.17)}`,
          })}><MonitorHeartOutlined sx={{fontSize:{xs:25,sm:29}}}/></Box>
          <Stack spacing={.5} sx={{minWidth:0}}>
            <Stack direction="row" useFlexGap sx={{alignItems:'center',gap:1,flexWrap:'wrap'}}>
              <Typography component="h1" variant="h5" sx={{fontSize:{xs:22,sm:26},fontWeight:800,lineHeight:1.15}}>بگم نگم</Typography>
              <Stack direction="row" sx={theme=>({
                '--signal': theme.palette[signalTone].main,
                alignItems:'center',gap:.75,px:1,py:.25,borderRadius:8,
                color:'var(--signal)',border:'1px solid',borderColor:alpha(theme.palette[signalTone].main,.36),
                bgcolor:alpha(theme.palette[signalTone].main,.09),
              })}>
                <Box aria-hidden="true" sx={{
                  width:7,height:7,borderRadius:'50%',bgcolor:'currentColor',position:'relative',boxShadow:'0 0 8px currentColor',
                  '&::after': signalTone==='success'?{content:'""',position:'absolute',inset:0,borderRadius:'inherit',border:'1px solid',animation:`${signalPulse} 3s ease-out infinite`}:undefined,
                  '@media (prefers-reduced-motion: reduce)':{'&::after':{display:'none'}},
                }}/>
                <Typography component="span" variant="caption" sx={{fontWeight:700,lineHeight:1.6}}>{signalText}</Typography>
              </Stack>
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{fontVariantNumeric:'tabular-nums'}}>
              {data?`آخرین دریافت: ${new Date(data.generated_at).toLocaleTimeString('fa-IR',{timeZone:'Asia/Tehran',hour:'2-digit',minute:'2-digit',second:'2-digit'})} · بازه: از ${new Date(data.window.start).toLocaleString('fa-IR',{timeZone:'Asia/Tehran',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})} تا اکنون`:'در انتظار نخستین پاسخ سرور'} · ساعت تهران
            </Typography>
          </Stack>
        </Stack>
        <Box sx={{display:{xs:'grid',sm:'flex'},gridTemplateColumns:'repeat(2,minmax(0,1fr))',gap:1,alignItems:'center',flexWrap:'wrap'}}>
          <TextField select label="دورهٔ به‌روزرسانی" value={interval} onChange={event=>changeInterval(event.target.value)} size="small" sx={{minWidth:{xs:0,sm:155}}}>
            {monitoringIntervals.map(seconds=><MenuItem key={seconds} value={seconds}>{seconds<60?`${number(seconds)} ثانیه`:`${number(seconds/60)} دقیقه`}</MenuItem>)}
          </TextField>
          <Button variant="contained" onClick={reload} disabled={busy||!!paused||!ready} startIcon={<RefreshRounded/>}
            sx={{minHeight:48,backgroundImage:'linear-gradient(110deg, #62e6f5, #9fb8ff)',boxShadow:'0 0 18px #62e6f52a','&:hover':{boxShadow:'0 0 22px #62e6f553'},'&.Mui-disabled':{backgroundImage:'none',boxShadow:'none'}}}>
            تازه‌سازی
          </Button>
          <Button component={Link} href="/manage" variant="outlined" startIcon={<ArrowForwardRounded/>}
            sx={{gridColumn:'1 / -1',minHeight:48,borderColor:'divider',color:'text.primary','&:hover':{borderColor:'primary.main'}}}>
            بازگشت به مدیریت
          </Button>
        </Box>
      </Stack>
      {busy&&<LinearProgress aria-label="دریافت آمار مانیتورینگ" sx={{position:'absolute',inset:'auto 0 0',height:2}}/>}
    </Card>
    {(error||paused)&&<Alert severity="warning">{paused||error}{data?' · آخرین دادهٔ موفق نمایش داده می‌شود؛ ممکن است قدیمی باشد.':' · هنوز اطلاعاتی دریافت نشده است.'}</Alert>}
    {data&&<>
      <Box sx={{display:'grid',gridTemplateColumns:{xs:'repeat(2,minmax(0,1fr))',sm:'repeat(3,minmax(0,1fr))',lg:'repeat(9,minmax(0,1fr))'},gap:1.5}}>
        <Metric title="کاربران امروز" value={number(data.totals.accounts_today??null)} detail="از ساعت صفر به وقت تهران" icon={<PeopleOutlined/>} accent="primary"/>
        <Metric title="کل کاربران" value={number(data.totals.accounts_total??null)} detail="تمام حساب‌های محصول" icon={<GroupsOutlined/>} accent="secondary"/>
        <Metric title="بلک لیست" value={number(data.totals.blacklist_total??null)} detail="شماره‌های مسدود فعال" icon={<BlockOutlined/>}/>
        <Metric title="درخواست پیام" value={number(data.totals.requests)} detail="سفارش ثبت‌شده در بازه" icon={<SmsOutlined/>}/>
        <Metric title="رسیده به گیرنده" value={number(data.totals.delivered)} detail="از رکوردهای تحویل این بازه" icon={<MarkEmailReadOutlined/>}/>
        <Metric title="در انتظار ارسال" value={number(Number(data.operations.outbox_pending||0))} detail="پیام‌ها و دعوت‌ها · اکنون" icon={<HourglassEmptyRounded/>}/>
        <Metric title="عمر قدیمی‌ترین صف" value={monitoringDuration(Number(data.operations.oldest_queue_seconds||0))} detail="از موارد فعال · اکنون" icon={<ScheduleRounded/>} severity={monitoringMetricSeverity('oldest_queue_seconds',Number(data.operations.oldest_queue_seconds||0))}/>
        <Metric title="نتیجهٔ نامعلوم" value={number(Number(data.operations.payment_unknown||0)+Number(data.operations.delivery_unknown||0))} detail="پرداخت و تحویل · اکنون" icon={<RuleOutlined/>} severity={Number(data.operations.payment_unknown||0)+Number(data.operations.delivery_unknown||0)>0?'warning':undefined}/>
        <Metric title="پشتیبانی بی‌پاسخ" value={number(data.totals.support_unanswered)} detail="گفت‌وگوهای منتظر پاسخ" icon={<SupportAgentOutlined/>} severity={monitoringMetricSeverity('support_unanswered',data.totals.support_unanswered)}/>
      </Box>
      <Charts data={data}/>
    </>}
  </Stack>;
}
