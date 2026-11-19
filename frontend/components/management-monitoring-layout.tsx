"use client";

import type { ReactNode } from 'react';
import Box from '@mui/material/Box';
import { MonitoringTheme } from './management-theme';

export function ManagementMonitoringLayout({children, active}:{children:ReactNode; active:boolean}) {
  return <MonitoringTheme>
    <Box dir="rtl" data-management-ui="material" data-update-blocked={active || undefined} sx={theme=>({
      minHeight: '100dvh',
      minWidth: 0,
      colorScheme: 'dark',
      bgcolor: 'background.default',
      color: 'text.primary',
      '--focus': theme.palette.primary.main,
      backgroundImage: [
        'linear-gradient(#8aa7ff0b 1px, transparent 1px)',
        'linear-gradient(90deg, #8aa7ff0b 1px, transparent 1px)',
        'radial-gradient(ellipse at 100% 0%, #114054 0%, transparent 47%)',
        'radial-gradient(ellipse at 0% 15%, #321d4c 0%, transparent 44%)',
      ].join(', '),
      backgroundSize: '36px 36px, 36px 36px, auto, auto',
      p: {xs:2, sm:3},
      '@media (min-width:1200px) and (max-height:900px)': {p:1.5},
      '& .MuiButtonBase-root.Mui-focusVisible': {outline: `2px solid ${theme.palette.primary.main}`, outlineOffset: 2},
    })}>{children}</Box>
  </MonitoringTheme>;
}
