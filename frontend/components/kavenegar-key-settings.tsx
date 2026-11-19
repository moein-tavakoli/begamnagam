'use client';

import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import KeyOutlined from '@mui/icons-material/KeyOutlined';
import RefreshRounded from '@mui/icons-material/RefreshRounded';
import RestoreRounded from '@mui/icons-material/RestoreRounded';
import SaveOutlined from '@mui/icons-material/SaveOutlined';
import { api, ApiError, errorMessage } from '@/lib/api';

const path = '/manage/sms-template/kavenegar-key';
const sourceLabels = {
  panel: 'کلید ثبت‌شده در پنل',
  environment: 'کلید تنظیمات سرور',
  missing: 'کلید تنظیم نشده',
  unreadable: 'خطای خواندن کلید پنل',
};
type KeyStatus = { source: keyof typeof sourceLabels; revision: number };

export function KavenegarKeySettings({ onFailure }: { onFailure: (error: unknown) => void }) {
  const [status, setStatus] = useState<KeyStatus | null>(null);
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState<'load' | 'save' | null>('load');
  const [message, setMessage] = useState('');
  const [failure, setFailure] = useState<unknown>(null);
  const lifetime = useRef<AbortController | null>(null);

  const load = useCallback(async (signal: AbortSignal) => {
    setPending('load');
    setFailure(null);
    try {
      const result = await api<KeyStatus>(path, { signal });
      if (!signal.aborted) setStatus(result);
    } catch (error) {
      if (!signal.aborted) { setFailure(error); onFailure(error); }
    } finally {
      if (!signal.aborted) setPending(null);
    }
  }, [onFailure]);

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function update(key: string) {
    const signal = lifetime.current?.signal;
    if (!signal || signal.aborted || pending || !status) return;
    setPending('save');
    setFailure(null);
    setMessage('');
    try {
      const result = await api<KeyStatus>(path, { method: 'PUT', body: { api_key: key, revision: status.revision }, signal });
      if (signal.aborted) return;
      setStatus(result);
      setDraft('');
      setMessage(key ? 'کلید جدید ذخیره شد.' : 'کلید ثبت‌شده در پنل حذف شد.');
    } catch (error) {
      if (signal.aborted) return;
      if (error instanceof ApiError && error.code === 'settings_changed') {
        setStatus(null);
        setDraft('');
      }
      setFailure(error);
      onFailure(error);
    } finally {
      if (!signal.aborted) setPending(null);
    }
  }

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft) void update(draft);
  }

  return <Card component="section" aria-labelledby="kavenegar-key-title" sx={{ p: { xs: 2, sm: 3 } }}>
    <Stack spacing={1.75}>
      <Stack direction="row" useFlexGap sx={{ alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <KeyOutlined color="primary"/>
        <Typography id="kavenegar-key-title" component="h2" variant="h6">کلید API کاوه‌نگار</Typography>
        {status && <Chip size="small" label={sourceLabels[status.source]} variant="outlined"/>}
      </Stack>
      {failure != null && <Alert severity="error">{errorMessage(failure)}</Alert>}
      {message && <Alert severity="success" role="status">{message}</Alert>}
      {!status && (pending ? <Typography role="status">در حال دریافت وضعیت کلید…</Typography> :
        <Button sx={{ alignSelf: 'flex-start' }} startIcon={<RefreshRounded/>}
          onClick={() => { if (lifetime.current) void load(lifetime.current.signal); }}>دریافت وضعیت کلید</Button>)}
      {status && <Stack component="form" method="post" onSubmit={save} spacing={1.25}>
        <TextField id="kavenegar-api-key" label="کلید API جدید" type="password" autoComplete="new-password"
          fullWidth required disabled={pending !== null} value={draft} onChange={event => {
            setDraft(event.target.value);
            setFailure(null);
            setMessage('');
          }}
          helperText="کلید جدید از درخواست بعدی برای کد ورود، ارسال پیامک، پیگیری تحویل و استعلام اعتبار استفاده می‌شود."
          slotProps={{ htmlInput: { dir: 'ltr', maxLength: 256, spellCheck: false } }}/>
        <Stack direction={{ xs: 'column', sm: 'row' }} useFlexGap sx={{ gap: 1, flexWrap: 'wrap' }}>
          <Button type="submit" variant="contained" startIcon={<SaveOutlined/>} disabled={pending !== null || !draft}>
            {pending === 'save' ? 'در حال ذخیره…' : 'ذخیرهٔ کلید'}
          </Button>
          {(status.source === 'panel' || status.source === 'unreadable') && <Button type="button" variant="outlined" startIcon={<RestoreRounded/>}
            disabled={pending !== null} onClick={() => void update('')}>بازگشت به کلید تنظیمات سرور</Button>}
        </Stack>
      </Stack>}
    </Stack>
  </Card>;
}
