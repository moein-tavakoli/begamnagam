"use client";

import { AppRouterCacheProvider } from '@mui/material-nextjs/v16-appRouter';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { faIR } from '@mui/material/locale';
import rtlPlugin from '@mui/stylis-plugin-rtl';
import { prefixer } from 'stylis';
import type { ReactNode } from 'react';

const theme = createTheme({
  direction: 'rtl',
  typography: { fontFamily: '"Vazirmatn FD", "Vazirmatn", Tahoma, sans-serif', fontSize: 14, button: { textTransform: 'none', fontWeight: 600 } },
  palette: { primary: { main: '#6843ad' }, secondary: { main: '#201c29' }, background: { default: '#f2eeff', paper: '#fff' }, text: { primary: '#201c29', secondary: '#6e627d' }, error: { main: '#a52c42' }, divider: '#e1d8f1' },
  shape: { borderRadius: 12 },
  components: {
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { minHeight: 44, paddingInline: 16, gap: 6 } } },
    MuiIconButton: { styleOverrides: { root: { width: 44, height: 44 } } },
    MuiMenuItem: { styleOverrides: { root: { minHeight: 44, fontSize: 14, whiteSpace: 'normal', gap: 10 } } },
    MuiMenu: { styleOverrides: { paper: { border: '1px solid #e1d8f1', boxShadow: '0 12px 40px #201c2924', minWidth: 220, maxWidth: 'calc(100vw - 32px)', marginTop: 4 } } },
    MuiOutlinedInput: { defaultProps: { size: 'small' }, styleOverrides: { root: { backgroundColor: '#fff', minHeight: 48 }, input: { fontFamily: 'inherit', fontSize: 14 } } },
    MuiCard: { defaultProps: { variant: 'outlined' }, styleOverrides: { root: { borderRadius: 20 } } },
    MuiTableCell: { styleOverrides: { root: { textAlign: 'right', fontFamily: 'inherit' }, head: { fontWeight: 600 } } },
    MuiDialog: { styleOverrides: { paper: { borderRadius: 20 } } },
    MuiDialogTitle: { styleOverrides: { root: { fontSize: 19, fontWeight: 700 } } },
  },
}, faIR);

export function ManagementTheme({ children }: { children: ReactNode }) {
  return <AppRouterCacheProvider options={{ key: 'manage-rtl', stylisPlugins: [prefixer, rtlPlugin] }}><ThemeProvider theme={theme}>{children}</ThemeProvider></AppRouterCacheProvider>;
}
