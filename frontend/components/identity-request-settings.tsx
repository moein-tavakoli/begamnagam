"use client";

import { useCallback, useEffect, useId, useState, type FormEvent } from 'react';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import FormControlLabel from '@mui/material/FormControlLabel';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { api, ApiError, errorMessage } from '@/lib/api';
import { identitySettingsChanged } from '@/lib/identity-consent';
import { ManagementInput } from './management-ui';

type Settings = { enabled: boolean; revision: number };
const settingsPath = '/manage/identity-settings';

export function IdentityRequestSettings({ onFailure }: { onFailure: (error: unknown) => void }) {
  const titleId = useId();
  const helpId = useId();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError('');
    try {
      const current = await api<Settings>(settingsPath, { signal });
      if (signal?.aborted) return;
      setSettings(current);
      setEnabled(current.enabled);
    } catch (error) {
      if (signal?.aborted) return;
      setError(errorMessage(error));
      onFailure(error);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [onFailure]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings || saving || settings.enabled === enabled) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const current = await api<Settings>(settingsPath, {
        method: 'PUT', body: { enabled, revision: settings.revision },
      });
      setSettings(current);
      setEnabled(current.enabled);
      setNotice(current.enabled ? 'قابلیت برای کاربران سایت فعال شد.' : 'قابلیت در سایت خاموش شد.');
      window.dispatchEvent(new Event(identitySettingsChanged));
    } catch (error) {
      if (error instanceof ApiError && error.code === 'settings_changed') setSettings(null);
      setError(errorMessage(error));
      onFailure(error);
    } finally {
      setSaving(false);
    }
  }

  return <Card component="form" aria-labelledby={titleId} onSubmit={save} sx={{ p: { xs: 2, sm: 3 } }}>
    <Stack spacing={2}>
      <Typography id={titleId} component="h2" variant="h6">میخوام بدونم</Typography>
      <Typography id={helpId} variant="body2" color="text.secondary">
        با فعال‌سازی، گزینه در منوی پیامک و پروفایل کاربران نمایش داده می‌شود. دیدن شماره به درخواست گیرنده و تأیید صاحب شماره نیاز دارد.
        خاموش‌کردن، دسترسی را موقتاً می‌بندد و رضایت‌های لغونشده را حفظ می‌کند.
      </Typography>
      {error && <Alert severity="error">{error}</Alert>}
      {notice && <Alert severity="success" role="status">{notice}</Alert>}
      {loading && <Typography role="status">در حال دریافت وضعیت…</Typography>}
      {!loading && !settings && <Button type="button" onClick={() => void load()} sx={{ alignSelf: 'start' }}>دریافت آخرین وضعیت</Button>}
      {settings && <Stack spacing={1} sx={{ alignItems: 'start' }}>
        <FormControlLabel label="فعال‌سازی «میخوام بدونم» در سایت" sx={{ minHeight: 44 }} control={
          <ManagementInput type="checkbox" role="switch" aria-describedby={helpId} checked={enabled} disabled={saving}
            onChange={event => { setEnabled(event.target.checked); setNotice(''); }} />
        } />
        <Button type="submit" variant="contained" disabled={saving || enabled === settings.enabled} sx={{ minHeight: 44 }}>
          {saving ? 'در حال ذخیره…' : 'ذخیرهٔ وضعیت'}
        </Button>
      </Stack>}
    </Stack>
  </Card>;
}
