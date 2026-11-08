"use client";

import Alert from '@mui/material/Alert';
import Avatar from '@mui/material/Avatar';
import Badge from '@mui/material/Badge';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import IconButton from '@mui/material/IconButton';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import ArrowForward from '@mui/icons-material/ArrowForward';
import ChatOutlined from '@mui/icons-material/ChatOutlined';
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined';
import PersonOutlined from '@mui/icons-material/PersonOutlined';
import Search from '@mui/icons-material/Search';
import { ManagementSupportThread } from './management-support-thread';
import { useCallback, useEffect, useState, type FormEvent, type RefObject } from 'react';
import { api, errorMessage } from '@/lib/api';
import { supportAccessLost, type SupportThreadData, type SupportWorkspaceMemory, type SupportDraftState } from '@/lib/support';
import { managementDate } from '@/lib/management';
import { SupportThread } from './support-thread';
import { notifySupportUpdate, useSupportPolling, useSupportRevision } from './support-polling';

type Inbox = {conversations:SupportThreadData[];total:number;page:number;page_size:number;waiting_count:number;attention_count:number};
export function useSupportBadge(enabled:boolean,onFailure:(e:unknown)=>void){
  const [count,setCount]=useState(0),revision=useSupportRevision();
  useSupportPolling(async signal=>{try{const result=await api<{attention_count:number}>('/manage/support/summary',{signal});if(!signal.aborted)setCount(result.attention_count);}catch(e){if(!signal.aborted){if(supportAccessLost(e))setCount(0);onFailure(e);}throw e;}},enabled,20000,revision);
  return enabled?count:0;
}
export function SupportInbox({onFailure,memory}:{onFailure:(e:unknown)=>void;memory:RefObject<SupportWorkspaceMemory>}){
  const [data,setData]=useState<Inbox|null>(null),[selected,setSelected]=useState<SupportThreadData|null>(memory.current.thread);
  const [filter,setFilter]=useState('waiting'),[query,setQuery]=useState(''),[page,setPage]=useState(1),[error,setError]=useState('');
  const [selectionRequest,setSelectionRequest]=useState<{thread:SupportThreadData|null}|null>(null);
  const [dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),revision=useSupportRevision();
  const failure=useCallback((e:unknown)=>{onFailure(e);if(supportAccessLost(e)){memory.current={thread:null,composer:{draft:"",pending:null}};setSelected(null);setData(null);setSelectionRequest(null);}},[onFailure,memory]);
  useSupportPolling(async signal=>{
    try{const result=await api<Inbox>('/manage/support/inbox',{method:'POST',body:{filter,query,page},signal});if(!signal.aborted){setData(result);setError('');}}
    catch(e){if(!signal.aborted){setError(errorMessage(e));failure(e);}throw e;}
  },true,10000,revision);
  // Filter/page transitions explicitly request a fresh list without racing a poll.
  useEffect(()=>{notifySupportUpdate();},[filter,query,page]);
  function commitSelection(thread:SupportThreadData|null){memory.current={thread,composer:{draft:"",pending:null}};setSelected(thread);setDirty(false);setError('');setSelectionRequest(null);}
  function select(thread:SupportThreadData|null){if(selected?.id===thread?.id)return;if(dirty){setSelectionRequest({thread});return;}commitSelection(thread);}
  async function close(){if(!selected)return;setBusy(true);setError('');try{const result=await api<{thread:SupportThreadData}>(`/manage/support/${selected.id}/close`,{method:'POST',body:{last_sequence:selected.last_sequence}});if(memory.current.thread?.id===result.thread.id)memory.current.thread={...memory.current.thread,...result.thread};setSelected(current=>current?.id===result.thread.id?{...current,...result.thread}:current);notifySupportUpdate();}catch(e){setError(errorMessage(e));failure(e);}finally{setBusy(false);}}
  const updateThread=useCallback((thread:SupportThreadData|null)=>{if(thread){if(memory.current.thread?.id===thread.id)memory.current.thread={...memory.current.thread,...thread};setSelected(current=>current?.id===thread.id?{...current,...thread}:current);}},[memory]);
  const rememberDraft=useCallback((composer:SupportDraftState)=>{memory.current.composer=composer;},[memory]);
  return <Stack component="section" aria-label="صندوق پشتیبانی" spacing={2.5} sx={{minWidth:0}}>
    <Stack direction={{xs:'column',md:'row'}} spacing={2} sx={{alignItems:{xs:'flex-start',md:'center'},justifyContent:'space-between'}}>
      <Stack spacing={.75}><Typography component="h2" variant="h5">یک جای مشترک برای پاسخ‌دادن</Typography><Typography variant="body2" color="text.secondary" sx={{maxWidth:650,lineHeight:2}}>کارمندان دارای دسترسی پشتیبانی می‌توانند پاسخ بدهند؛ نشان قرمز تا پاسخ به پیام کاربر باقی می‌ماند.</Typography></Stack>
      <Chip color="error" variant="outlined" label={`${(data?.waiting_count??0).toLocaleString('fa-IR')} منتظر پاسخ`} sx={{flexShrink:0}}/>
    </Stack>
    {error && <Alert severity="error">{error}</Alert>}
    <Paper variant="outlined" sx={{display:'grid',gridTemplateColumns:{xs:'minmax(0,1fr)',md:'300px minmax(0,1fr)'},height:{xs:'calc(100dvh - 230px)',md:'min(740px, calc(100dvh - 230px))'},minHeight:{xs:500,md:540},overflow:'hidden',borderRadius:3,minWidth:0}}>
      <Box component="aside" aria-label="فهرست گفت‌وگوها" sx={{display:{xs:selected?'none':'block',md:'block'},minWidth:0,borderInlineEnd:{md:'1px solid'},borderColor:'divider',overflowY:'auto',overscrollBehavior:'contain'}}>
        <Stack spacing={1.5} sx={{p:2,borderBottom:1,borderColor:'divider'}}>
          <Stack component="form" direction="row" spacing={1} sx={{alignItems:'center'}} onSubmit={(event:FormEvent<HTMLFormElement>)=>{event.preventDefault();setQuery(String(new FormData(event.currentTarget).get('query')??'').trim());setPage(1);}}>
            <TextField name="query" id="support-search" type="search" label="شماره یا شناسهٔ حساب" fullWidth size="small" slotProps={{htmlInput:{maxLength:100}}} sx={{minWidth:0}}/>
            <IconButton type="submit" color="primary" aria-label="جست‌وجوی گفت‌وگو"><Search/></IconButton>
          </Stack>
          <Stack direction="row" spacing={.5} aria-label="فیلتر گفت‌وگوها">{[['waiting','نیازمند پاسخ'],['all','همه'],['closed','بسته‌شده']].map(([key,label])=><Button type="button" size="small" key={key} variant={filter===key?'contained':'outlined'} aria-pressed={filter===key} onClick={()=>{setFilter(key);setPage(1);}} sx={{flex:1,minWidth:0,px:.5,fontSize:12}}>{label}</Button>)}</Stack>
        </Stack>
        {!data && !error && <Stack direction="row" spacing={1} role="status" sx={{alignItems:'center',justifyContent:'center',p:3}}><CircularProgress size={20}/><Typography variant="body2" color="text.secondary">در حال دریافت پیام‌ها…</Typography></Stack>}
        {data && !data.conversations.length && <Stack spacing={1.5} sx={{alignItems:'center',p:4,textAlign:'center'}}><CheckCircleOutlined color="primary" sx={{fontSize:32}}/><Typography variant="body2" color="text.secondary">{filter==='waiting'?'همهٔ پیام‌های این فهرست پاسخ گرفته‌اند.':'گفت‌وگویی در این فهرست نیست.'}</Typography></Stack>}
        <List disablePadding>{data?.conversations.map(thread=><ListItem key={thread.id} disablePadding divider><ListItemButton selected={selected?.id===thread.id} onClick={()=>select(thread)} aria-current={selected?.id===thread.id?'true':undefined} sx={{gap:1.5,p:2,alignItems:'flex-start'}}>
          <Badge color="error" badgeContent={thread.unread_count?thread.unread_count.toLocaleString('fa-IR'):0} aria-label={thread.unread_count?`${thread.unread_count.toLocaleString('fa-IR')} پیام جدید`:undefined}><Avatar sx={{bgcolor:'primary.main',width:38,height:38}}><PersonOutlined/></Avatar></Badge>
          <Stack spacing={.75} sx={{minWidth:0,flex:1}}><Typography component="span" variant="subtitle2" sx={{overflowWrap:'anywhere'}}><Box component="bdi">{thread.phone||'شماره در دسترس نیست'}</Box></Typography><Typography variant="caption" color="text.secondary">حساب {thread.account_id?.toLocaleString('fa-IR')} · {managementDate(thread.updated_at)}</Typography><Chip size="small" color={thread.needs_reply?'error':'default'} variant="outlined" label={thread.needs_reply?'منتظر پاسخ':thread.status==='closed'?'بسته‌شده':'پاسخ داده شده'} sx={{alignSelf:'flex-start'}}/></Stack>
        </ListItemButton></ListItem>)}</List>
        {!!data && data.total>25 && <Stack direction="row" spacing={1} sx={{alignItems:'center',justifyContent:'center',p:1.5}}><Button type="button" variant="outlined" disabled={page<=1} onClick={()=>setPage(p=>p-1)}>قبلی</Button><Typography variant="body2">{page.toLocaleString('fa-IR')}</Typography><Button type="button" variant="outlined" disabled={page*25>=data.total} onClick={()=>setPage(p=>p+1)}>بعدی</Button></Stack>}
      </Box>
      <Stack sx={{display:{xs:selected?'flex':'none',md:'flex'},minWidth:0,minHeight:0}}>
        {selected?<><Stack component="header" direction="row" spacing={1} sx={{alignItems:'center',p:{xs:1.5,md:2},borderBottom:1,borderColor:'divider',flexWrap:'wrap',rowGap:1}}>
          <IconButton onClick={()=>select(null)} aria-label="بازگشت به فهرست گفت‌وگوها" sx={{display:{xs:'inline-flex',md:'none'}}}><ArrowForward/></IconButton>
          <Stack spacing={.5} sx={{flex:1,minWidth:0}}><Typography variant="subtitle2">گفت‌وگو با <Box component="bdi" sx={{overflowWrap:'anywhere'}}>{selected.phone||'شماره در دسترس نیست'}</Box></Typography><Typography variant="caption" color="text.secondary">حساب {selected.account_id?.toLocaleString('fa-IR')} · {selected.needs_reply?'منتظر پاسخ':selected.status==='closed'?'بسته‌شده':'پاسخ داده شده'}</Typography></Stack>
          <Button type="button" variant="outlined" disabled={busy || selected.needs_reply || selected.status==='closed' || dirty} onClick={()=>void close()} sx={{fontSize:12}}>{busy?'در حال ثبت…':'بستن گفت‌وگو'}</Button>
        </Stack>
          <SupportThread key={selected.id} base={`/manage/support/${selected.id}`} staff active initialDraft={memory.current.composer} onDraftState={rememberDraft} onThread={updateThread} onDirty={setDirty} onFailure={failure} renderView={props=><ManagementSupportThread {...props}/>}/>
        </>:<Stack spacing={2} sx={{alignItems:'center',justifyContent:'center',flex:1,p:4,textAlign:'center',bgcolor:'background.default'}}><ChatOutlined color="primary" sx={{fontSize:48}}/><Typography component="h3" variant="h6">یک گفت‌وگو را باز کن</Typography><Typography variant="body2" color="text.secondary" sx={{maxWidth:320,lineHeight:2}}>متن‌ها فقط در همین بخش دیده می‌شوند. ارسال فایل فعلاً غیرفعال است.</Typography></Stack>}
      </Stack>
    </Paper>
    <Dialog open={!!selectionRequest} onClose={()=>setSelectionRequest(null)} aria-labelledby="support-discard-title" fullWidth maxWidth="xs">
      <DialogTitle id="support-discard-title">خروج از گفت‌وگو؟</DialogTitle>
      <DialogContent><DialogContentText>پیام ارسال‌نشده داری. با خروج از این گفت‌وگو پیش‌نویس پاک می‌شود.</DialogContentText></DialogContent>
      <DialogActions><Button onClick={()=>setSelectionRequest(null)}>ادامهٔ نوشتن</Button><Button color="error" variant="contained" onClick={()=>{if(selectionRequest)commitSelection(selectionRequest.thread);}}>خروج و پاک‌کردن پیش‌نویس</Button></DialogActions>
    </Dialog>
  </Stack>;
}
