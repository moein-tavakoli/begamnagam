"use client";

import { AppRouterCacheProvider } from '@mui/material-nextjs/v16-appRouter';
import { createTheme, ThemeProvider, type ThemeOptions } from '@mui/material/styles';
import { faIR } from '@mui/material/locale';
import rtlPlugin from '@mui/stylis-plugin-rtl';
import { prefixer } from 'stylis';
import type { ReactNode } from 'react';

const themeOptions: ThemeOptions = {
  direction: 'rtl',
  typography: { fontFamily: '"Vazirmatn FD", "Vazirmatn", Tahoma, sans-serif', fontSize: 14, h4:{fontSize:"1.8rem",fontWeight:800}, h5:{fontSize:"1.4rem",fontWeight:700}, h6:{fontSize:"1.1rem",fontWeight:700}, body1:{lineHeight:1.9}, body2:{lineHeight:1.9}, button: { textTransform: 'none', fontWeight: 600 } },
  shape: { borderRadius: 12 },
  components: {
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { minHeight: 44, paddingInline: 16, gap: 6 } } },
    MuiIconButton: { styleOverrides: { root: { width: 44, height: 44 } } },
    MuiMenuItem: { styleOverrides: { root: { minHeight: 44, fontSize: 14, whiteSpace: 'normal', gap: 10 } } },
    MuiMenu: { styleOverrides: { paper: ({theme}) => ({ border: `1px solid ${theme.palette.divider}`, boxShadow: theme.palette.mode === 'dark' ? '0 12px 40px #02040db3' : '0 12px 40px #201c2924', minWidth: 220, maxWidth: 'calc(100vw - 32px)', marginTop: 4 }) } },
    MuiTextField: { styleOverrides: { root: {
      '&& .MuiInputBase-input': { margin:0, border:0, borderRadius:0, background:'transparent', minHeight:0, height:'auto', padding:'12px 14px', fontFamily:'inherit', fontSize:16, lineHeight:1.7, '@media (min-width:900px)':{fontSize:14} },
      '&& .MuiInputBase-inputMultiline': { padding:0 },
      '&& .MuiInputBase-input[data-number-input]': { textAlign:'end' },
      '& .MuiInputBase-multiline': { padding:'12px 14px' },
    } } },
    MuiChip: { styleOverrides:{root:{fontFamily:'inherit',fontWeight:500}} },
    MuiBadge: { styleOverrides:{badge:{fontFamily:'inherit'}} },
    MuiFormControlLabel: {styleOverrides:{root:{minHeight:44},label:{fontSize:14,lineHeight:1.8}}},
    MuiOutlinedInput: { defaultProps: { size: 'small' }, styleOverrides: { root: ({theme}) => ({ backgroundColor: theme.palette.background.paper, minHeight: 48 }), input: { fontFamily: 'inherit', fontSize: 14 } } },
    MuiCard: { defaultProps: { variant: 'outlined' }, styleOverrides: { root: { borderRadius: 20 } } },
    MuiTableCell: { styleOverrides: { root: { textAlign: 'start', fontFamily: 'inherit' }, head: { fontWeight: 600 } } },
    MuiDialog: { styleOverrides: { paper: { borderRadius: 20 } } },
    MuiDialogTitle: { styleOverrides: { root: { fontSize: 19, fontWeight: 700 } } },
  },
};

const theme = createTheme({
  ...themeOptions,
  palette: { primary: { main: '#6843ad' }, secondary: { main: '#201c29' }, background: { default: '#f2eeff', paper: '#fff' }, text: { primary: '#201c29', secondary: '#6e627d' }, error: { main: '#a52c42' }, divider: '#e1d8f1' },
}, faIR);

const monitoringTheme = createTheme({
  ...themeOptions,
  palette: {
    mode: 'dark',
    primary: { main: '#62e6f5', contrastText: '#061827' },
    secondary: { main: '#ed9af9' },
    info: { main: '#a9b6ff' },
    success: { main: '#68edb2' },
    warning: { main: '#ffc07b' },
    error: { main: '#ff8197' },
    background: { default: '#080b18', paper: '#10162a' },
    text: { primary: '#f4f7ff', secondary: '#b9c5df' },
    divider: '#344260',
  },
}, faIR);

export function ManagementTheme({ children }: { children: ReactNode }) {
  return <AppRouterCacheProvider options={{ key: 'manage-rtl', stylisPlugins: [prefixer, rtlPlugin] }}><ThemeProvider theme={theme}>{children}</ThemeProvider></AppRouterCacheProvider>;
}

export function MonitoringTheme({ children }: { children: ReactNode }) {
  return <ThemeProvider theme={monitoringTheme}>{children}</ThemeProvider>;
}
