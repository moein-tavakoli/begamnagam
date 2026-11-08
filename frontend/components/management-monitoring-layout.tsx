"use client";

import type { ReactNode } from 'react';
import Box from '@mui/material/Box';

export function ManagementMonitoringLayout({children}:{children:ReactNode}) {
  return <Box dir="rtl" data-management-ui="material" data-update-blocked="true" sx={{minHeight:'100dvh',minWidth:0,bgcolor:'background.default',color:'text.primary',p:{xs:2,sm:3},'@media (min-width:1200px) and (max-height:900px)':{p:1.5}}}>{children}</Box>;
}
