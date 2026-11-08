"use client";

import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import ArrowDownward from '@mui/icons-material/ArrowDownward';
import ChatOutlined from '@mui/icons-material/ChatOutlined';
import Done from '@mui/icons-material/Done';
import DoneAll from '@mui/icons-material/DoneAll';
import Refresh from '@mui/icons-material/Refresh';
import Send from '@mui/icons-material/Send';
import { supportDay, supportTime } from '@/lib/support';
import type { SupportThreadViewProps } from './support-thread';

/** Presentation only: shared SupportThread owns polling, reads, drafts and retries. */
export function ManagementSupportThread({page,messages,draft,pending,busy,error,pollError,older,loadingOlder,atBottom,viewport,input,onScroll,onDraftChange,onKeyDown,onSubmit,onRetry,onLoadOlder,onLatest}:SupportThreadViewProps) {
  return <Stack sx={{flex:1,minHeight:0,minWidth:0,overflow:'hidden',position:'relative'}} data-update-blocked={draft || pending ? 'true':undefined}>
    <Box ref={viewport} tabIndex={0} role="log" aria-live="polite" aria-relevant="additions" aria-label="پیام‌های گفت‌وگو" onScroll={onScroll} sx={{flex:1,minHeight:0,overflowY:'auto',overscrollBehavior:'contain',p:{xs:1.5,md:2.5},bgcolor:'background.default',scrollbarWidth:'thin'}}>
      {older && <Stack sx={{alignItems:'center',mb:2}}><Button variant="outlined" disabled={loadingOlder} onClick={onLoadOlder} startIcon={loadingOlder?<CircularProgress size={16} color="inherit"/>:<Refresh/>}>{loadingOlder?'در حال دریافت…':'پیام‌های قدیمی‌تر'}</Button></Stack>}
      {!page && !error && !pollError && <Stack direction="row" spacing={1} role="status" sx={{alignItems:'center',justifyContent:'center',p:3}}><CircularProgress size={20}/><Typography variant="body2" color="text.secondary">در حال دریافت گفت‌وگو…</Typography></Stack>}
      {page && !messages.length && <Stack spacing={1.5} sx={{alignItems:'center',justifyContent:'center',minHeight:220,textAlign:'center'}}><ChatOutlined color="primary" sx={{fontSize:40}}/><Typography variant="h6" component="h3">پیامی در این گفت‌وگو نیست</Typography><Typography variant="body2" color="text.secondary">پیام‌های کاربر و پاسخ‌های پشتیبانی اینجا دیده می‌شوند.</Typography></Stack>}
      {messages.map((message,index)=>{
        const mine=message.role==='staff';
        const read=!!page?.thread && message.sequence<=page.thread.customer_read_sequence;
        return <Box key={message.id}>
          {(!index || supportDay(messages[index-1].created_at)!==supportDay(message.created_at)) && <Divider sx={{my:2}}><Typography variant="caption" color="text.secondary">{supportDay(message.created_at)}</Typography></Divider>}
          <Paper component="article" variant="outlined" aria-label={mine?'پیام پشتیبانی':'پیام کاربر'} sx={{width:'fit-content',maxWidth:{xs:'94%',md:'86%'},minWidth:100,my:1,p:1.5,bgcolor:mine?'primary.main':'background.paper',color:mine?'primary.contrastText':'text.primary',marginInlineStart:mine?0:'auto',marginInlineEnd:mine?'auto':0,borderRadius:2}}>
            <Typography component="span" variant="caption" sx={{fontWeight:700}}>{mine?'پشتیبانی':'کاربر'}</Typography>
            <Typography variant="body2" sx={{whiteSpace:'pre-wrap',overflowWrap:'anywhere',lineHeight:2,my:.5}}>{message.redacted?'متن این پیام طبق زمان نگهداری پاک شده است.':message.text}</Typography>
            <Stack direction="row" spacing={1} sx={{alignItems:'center',justifyContent:'flex-end'}}>
              <Typography component="time" dateTime={message.created_at} variant="caption">{supportTime(message.created_at)}</Typography>
              {mine && <Stack direction="row" spacing={.5} sx={{alignItems:'center'}}><Typography variant="caption">{read?'خوانده شد':'ارسال شد'}</Typography>{read?<DoneAll sx={{fontSize:15}}/>:<Done sx={{fontSize:15}}/>}</Stack>}
            </Stack>
          </Paper>
        </Box>;
      })}
      {page?.thread?.status==='closed' && <Alert severity="info" sx={{mt:2}}>این گفت‌وگو پاسخ داده شده؛ با پیام تازه دوباره باز می‌شود.</Alert>}
    </Box>
    {!atBottom && <Button variant="contained" size="small" onClick={onLatest} startIcon={<ArrowDownward/>} sx={{alignSelf:'center',position:'absolute',bottom:180,zIndex:1,maxWidth:'90%'}}>رفتن به آخرین پیام</Button>}
    <Stack spacing={1.5} sx={{p:{xs:1.5,md:2},borderTop:1,borderColor:'divider',bgcolor:'background.paper',flexShrink:0}}>
      {(error || pollError) && <Alert severity="error">{error || pollError}</Alert>}
      {pending && !busy && <Alert severity="warning" role="status" action={<Button color="inherit" onClick={onRetry} startIcon={<Refresh/>}>تلاش دوباره</Button>} sx={{flexWrap:'wrap'}}>نتیجهٔ ارسال هنوز مشخص نیست؛ تکرار با همان شناسه انجام می‌شود تا پیام دوباره ثبت نشود.</Alert>}
      <Stack component="form" onSubmit={onSubmit} aria-label="ارسال پیام به پشتیبانی" direction="row" spacing={1} sx={{alignItems:'flex-end'}}>
        <TextField id="support-draft-staff" inputRef={input} label="پاسخ به کاربر" value={draft} onChange={event=>onDraftChange(event.target.value)} multiline rows={2} fullWidth disabled={busy || pending} placeholder="پاسخت را بنویس…" autoComplete="off" slotProps={{htmlInput:{maxLength:2000,onKeyDown}}} sx={{minWidth:0,'& textarea':{fontSize:{xs:16,md:14},lineHeight:1.8}}}/>
        <IconButton type="submit" color="primary" aria-label={busy?'در حال ارسال پیام':'ارسال پیام پشتیبانی'} disabled={busy || pending || !draft.trim() || !page || !page.thread?.last_customer_sequence} sx={{flexShrink:0,mb:.5}}>{busy?<CircularProgress size={22} color="inherit"/>:<Send sx={{transform:'scaleX(-1)'}}/>}</IconButton>
      </Stack>
      <Stack direction="row" spacing={1} sx={{alignItems:'flex-start',justifyContent:'space-between'}}><Typography variant="caption" color="text.secondary">فقط متن · رمز، کد ورود یا اطلاعات حساس نفرست.</Typography><Typography variant="caption" color="text.secondary" sx={{whiteSpace:'nowrap'}}>{draft.length.toLocaleString('fa-IR')}/۲۰۰۰</Typography></Stack>
    </Stack>
  </Stack>;
}
