"use client";

import Link from 'next/link';
import { useState } from 'react';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Breadcrumbs from '@mui/material/Breadcrumbs';
import MuiLink from '@mui/material/Link';
import IconButton from '@mui/material/IconButton';
import Badge from '@mui/material/Badge';
import Tooltip from '@mui/material/Tooltip';
import ForumRounded from '@mui/icons-material/ForumRounded';
import MenuRounded from '@mui/icons-material/MenuRounded';
import CloseRounded from '@mui/icons-material/CloseRounded';
import LogoutRounded from '@mui/icons-material/LogoutRounded';
import HomeOutlined from '@mui/icons-material/HomeOutlined';
import ChevronLeftRounded from '@mui/icons-material/ChevronLeftRounded';
import { ManagementIcon } from './management-icons';
import { version } from '../package.json';
import { managementBreadcrumbs, managementHref, managementNavigation, type ManagementSession } from '@/lib/management';
import type { ReactNode } from 'react';

const drawerWidth=256;
export function ManagementBrand() {
  return <MuiLink component={Link} href="/" underline="none" color="text.primary" sx={{display:'inline-flex',alignItems:'center',gap:1.5}}><ForumRounded color="primary" sx={{fontSize:34}}/><Typography component="span" variant="h5" sx={{fontWeight:800}}>بگم نگم.</Typography></MuiLink>;
}
export function ManagementFrame({session,pathname,title,active,supportCount,busy,onSignOut,children}: {session:ManagementSession;pathname:string;title:string;active:string;supportCount:number;busy:boolean;onSignOut:()=>void;children:ReactNode}) {
  const [mobileOpen,setMobileOpen]=useState(false);
  const nav = <Stack sx={{height:'100%',p:2,gap:2}}>
    <Stack direction="row" sx={{alignItems:'center',justifyContent:'space-between',px:1,pt:1}}><ManagementBrand/><IconButton aria-label="بستن منوی مدیریت" onClick={()=>setMobileOpen(false)} sx={{display:{xs:'inline-flex',md:'none'}}}><CloseRounded/></IconButton></Stack>
    <Typography variant="overline" color="text.secondary" sx={{px:1}}>مدیریت محصول</Typography>
    <List component="nav" aria-label="بخش‌های مدیریت" sx={{flex:1,overflowY:'auto',p:0}}>{managementNavigation(session).map(item=><ListItemButton key={item.key} component={Link} href={managementHref(item.key)} selected={active===item.key} aria-current={active===item.key?'page':undefined} onClick={()=>setMobileOpen(false)} sx={{borderRadius:2,mb:.5,py:1}}>
      <ListItemIcon sx={{minWidth:40}}><Badge color="error" badgeContent={item.key==='support'?supportCount:0} max={99} showZero={false}><ManagementIcon name={item.key}/></Badge></ListItemIcon><ListItemText primary={item.title} slotProps={{primary:{sx:{fontSize:14,fontWeight:active===item.key?700:500}}}}/>
    </ListItemButton>)}</List>
  </Stack>;
  return <Box dir="rtl" data-management-ui="material" data-update-blocked="true" sx={{display:'flex',minHeight:'100dvh',bgcolor:'background.default',color:'text.primary'}}>
    <Box component="aside" sx={{width:{md:drawerWidth},flexShrink:{md:0}}}>
      <Drawer variant="temporary" anchor="left" open={mobileOpen} onClose={()=>setMobileOpen(false)} dir="rtl" slotProps={{paper:{sx:{width:drawerWidth,maxWidth:'88vw'}}}} sx={{display:{xs:'block',md:'none'}}}>{nav}</Drawer>
      <Drawer variant="permanent" anchor="left" open slotProps={{paper:{sx:{width:drawerWidth,boxSizing:'border-box'}}}} sx={{display:{xs:'none',md:'block'}}}>{nav}</Drawer>
    </Box>
    <Box sx={{flex:1,minWidth:0}}>
      <AppBar position="sticky" color="inherit" elevation={0} sx={{borderBottom:1,borderColor:'divider',bgcolor:'background.paper'}}>
        <Toolbar sx={{gap:1,px:{xs:1.5,sm:3},minHeight:{xs:68,sm:80}}}>
          <IconButton aria-label="بازکردن منوی مدیریت" aria-expanded={mobileOpen} onClick={()=>setMobileOpen(true)} sx={{display:{md:'none'}}}><MenuRounded/></IconButton>
          <Stack spacing={.25} sx={{minWidth:0,flex:1}}><Typography component="h1" variant="h6" noWrap>{title}</Typography><Breadcrumbs aria-label="مسیر صفحه" separator={<ChevronLeftRounded sx={{fontSize:16}}/>} sx={{fontSize:12}}>{managementBreadcrumbs(session,pathname).map((item,index)=>item.href?<MuiLink key={index} component={Link} href={item.href} underline="hover" color="inherit">{item.title}</MuiLink>:<Typography key={index} variant="caption" color="text.primary">{item.title}</Typography>)}</Breadcrumbs></Stack>
          <Tooltip title="بازگشت به سایت"><IconButton component={Link} href="/" aria-label="بازگشت به سایت"><HomeOutlined/></IconButton></Tooltip>
          <Tooltip title="خروج از مدیریت"><IconButton disabled={busy} aria-label="خروج از مدیریت" onClick={onSignOut}><LogoutRounded/></IconButton></Tooltip>
        </Toolbar>
      </AppBar>
      <Stack spacing={{xs:2,md:3}} sx={{p:{xs:2,sm:3,lg:4},maxWidth:1600,mx:'auto',minWidth:0}}>{children}<Stack component="footer" aria-label="پاورقی مدیریت" spacing={.5} sx={{textAlign:'center',pt:1}}><Typography variant="caption" color="text.secondary">زمان‌ها به وقت تهران · اقدام‌های مدیریتی در سابقه ثبت می‌شوند.</Typography><Typography variant="caption" color="text.secondary" aria-label="نسخهٔ نرم‌افزار">نسخهٔ نرم‌افزار {version}</Typography></Stack></Stack>
    </Box>
  </Box>;
}
