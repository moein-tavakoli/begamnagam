"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import AddRounded from '@mui/icons-material/AddRounded';
import DataObjectOutlined from '@mui/icons-material/DataObjectOutlined';
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded';
import PreviewOutlined from '@mui/icons-material/PreviewOutlined';
import RefreshRounded from '@mui/icons-material/RefreshRounded';
import RestoreRounded from '@mui/icons-material/RestoreRounded';
import SaveOutlined from '@mui/icons-material/SaveOutlined';
import SmsOutlined from '@mui/icons-material/SmsOutlined';
import { api, ApiError, errorMessage } from '@/lib/api';
import { latinInputDigits } from '@/lib/input-digits';
import { managementNumber as number } from '@/lib/management';

type Variable = { name: string; value: string };
type Draft = { template: string; variables: Variable[] };
export type SmsTemplateDraftMemory = { draft: Draft; revision: number } | null;
type Preview = { full_sms: string; sms_units: number; sms_segments: number; body_units: number };
type Settings = Draft & {
  revision: number;
  preview: Preview;
  default_template: string;
  max_template_length: number;
  max_variables: number;
  max_value_length: number;
};

const path = '/manage/sms-template';
const variableName = '[a-z][a-z0-9_]{0,23}';
const validName = new RegExp(`^${variableName}$`);
const requiredSlots = [
  { token: '{{message}}', label: 'متن تأییدشدهٔ پیام', hint: 'یک بار در یک خط جدا' },
  { token: '{{opt_out}}', label: 'نام سرویس و لینک لغو دریافت', hint: 'یک بار در آخرین خط' },
];

function draftFrom({ template, variables }: Draft): Draft {
  return { template, variables };
}

export function SmsTemplateSettings({ onFailure, memory }: {
  onFailure: (error: unknown) => void;
  memory: { current: SmsTemplateDraftMemory };
}) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [draft, setDraft] = useState<Draft>({ template: '', variables: [] });
  const [sample, setSample] = useState<{ key: string; preview: Preview } | null>(null);
  const [pending, setPending] = useState<'load' | 'preview' | 'save' | null>('load');
  const [failure, setFailure] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const templateInput = useRef<HTMLTextAreaElement>(null);
  const previewTitle = useRef<HTMLHeadingElement>(null);
  const lifetime = useRef<AbortController | null>(null);

  const accept = useCallback((result: Settings, restoreDraft = false) => {
    const active = draftFrom(result);
    const local = restoreDraft ? memory.current : null;
    setSettings(result);
    if (local && JSON.stringify(local.draft) !== JSON.stringify(active)) {
      setDraft(local.draft);
    } else {
      memory.current = null;
      setDraft(active);
    }
    setSample(null);
  }, [memory]);
  const load = useCallback(async (signal?: AbortSignal, restoreDraft = false) => {
    setPending('load');
    setFailure(null);
    setSaved(false);
    try {
      const result = await api<Settings>(path, { signal });
      if (!signal?.aborted) accept(result, restoreDraft);
    } catch (error) {
      if (!signal?.aborted) { setFailure(error); onFailure(error); }
    } finally {
      if (!signal?.aborted) setPending(null);
    }
  }, [accept, onFailure]);
  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    void load(controller.signal, true);
    return () => controller.abort();
  }, [load]);

  function edit(next: Draft) {
    if (settings) {
      memory.current = JSON.stringify(next) === JSON.stringify(draftFrom(settings))
        ? null : { draft: next, revision: memory.current?.revision ?? settings.revision };
    }
    setDraft(next);
    setFailure(null);
    setSaved(false);
  }

  function updateVariable(index: number, key: keyof Variable, value: string) {
    edit({ ...draft, variables: draft.variables.map((item, at) => at === index ? { ...item, [key]: value } : item) });
  }

  function insertVariable(name: string) {
    const input = templateInput.current;
    const start = input?.selectionStart ?? draft.template.length;
    const end = input?.selectionEnd ?? start;
    const token = `{{${name}}}`;
    const template = draft.template.slice(0, start) + token + draft.template.slice(end);
    if (!settings || template.length > settings.max_template_length) return;
    edit({ ...draft, template });
    requestAnimationFrame(() => {
      input?.focus();
      input?.setSelectionRange(start + token.length, start + token.length);
    });
  }

  const draftKey = JSON.stringify(draft);
  const dirty = settings !== null && draftKey !== JSON.stringify(draftFrom(settings));
  const revision = memory.current?.revision ?? settings?.revision;
  const conflict = dirty && revision !== settings?.revision;

  async function showPreview() {
    if (pending || !settings) return;
    const signal = lifetime.current?.signal;
    setPending('preview');
    setFailure(null);
    try {
      const preview = await api<Preview>(`${path}/preview`, { method: 'POST', body: draft, signal });
      setSample({ key: draftKey, preview });
      previewTitle.current?.focus();
    } catch (error) {
      if (!signal?.aborted) { setFailure(error); onFailure(error); }
    } finally { if (!signal?.aborted) setPending(null); }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !settings || !dirty || conflict) return;
    const signal = lifetime.current?.signal;
    setPending('save');
    setFailure(null);
    try {
      const result = await api<Settings>(path, { method: 'PUT', body: { ...draft, revision }, signal });
      if (signal?.aborted) return;
      accept(result);
      setSaved(true);
    } catch (error) {
      if (signal?.aborted) return;
      if (error instanceof ApiError && error.code === 'settings_changed') await load(signal, true);
      else { setFailure(error); onFailure(error); }
    } finally { if (!signal?.aborted) setPending(null); }
  }

  const fieldErrors = failure instanceof ApiError ? failure.fields : undefined;
  const sampleIsCurrent = sample?.key === draftKey;
  const preview = sampleIsCurrent ? sample.preview : settings?.preview;
  const disabled = pending !== null;

  return <Stack spacing={2.5}>
    <Alert severity="info" variant="outlined">
      قالب ذخیره‌شده روی پیش‌نمایش‌های تازهٔ پیام به گیرنده اعمال می‌شود. پیش‌نمایش‌های قبلی با همان متنِ تأییدشده ارسال می‌شوند.
    </Alert>
    {failure != null && <Alert severity="error">{errorMessage(failure)}</Alert>}
    {conflict && <Alert severity="warning">قالب فعال تغییر کرده است. متن پیش‌نویس شما در ویرایشگر باقی مانده است.</Alert>}
    {saved && <Alert severity="success">قالب ذخیره شد و برای پیام‌های تازه فعال است.</Alert>}
    {!settings && (disabled ? <Stack direction="row" spacing={1.5} role="status" sx={{ alignItems: 'center', py: 2 }}>
      <CircularProgress size={20} aria-hidden="true"/><Typography>در حال دریافت قالب پیامک…</Typography>
    </Stack> : <Box><Button onClick={() => void load(lifetime.current?.signal, true)} startIcon={<RefreshRounded/>}>تلاش دوباره</Button></Box>)}
    {settings && <Grid container spacing={2.5} sx={{ alignItems: 'flex-start' }}>
      <Grid size={{ xs: 12, lg: 7 }}>
        <Card component="form" onSubmit={save} sx={{ p: { xs: 2, sm: 3 }, minWidth: 0 }}>
          <Stack spacing={2.5}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
              <SmsOutlined color="primary"/><Typography component="h2" variant="h6">ویرایش قالب پیامک</Typography>
            </Stack>
            <TextField id="sms-template-text" inputRef={templateInput} label="متن قالب" multiline minRows={5} fullWidth required
              value={draft.template} disabled={disabled} onChange={event => edit({ ...draft, template: event.target.value })}
              error={!!fieldErrors?.template}
              helperText={fieldErrors?.template || 'متن ثابت و متغیرها را به ترتیبی که در پیامک دیده می‌شوند وارد کنید.'}
              slotProps={{ htmlInput: { maxLength: settings.max_template_length, spellCheck: false, dir: 'rtl' } }}/>
            <Stack spacing={.75}>
              {requiredSlots.map(slot => <Stack key={slot.token} direction="row" useFlexGap sx={{ gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                <Chip size="small" color="primary" variant="outlined" label={<Box component="code" dir="ltr">{slot.token}</Box>}/>
                <Typography variant="body2">{slot.label}</Typography>
                <Typography variant="caption" color="text.secondary">{slot.hint}</Typography>
              </Stack>)}
            </Stack>
            <Divider/>
            <Stack direction="row" useFlexGap sx={{ alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <DataObjectOutlined color="primary"/><Typography component="h3" variant="subtitle1" sx={{ fontWeight: 700 }}>متغیرهای سفارشی</Typography>
              </Stack>
              <Button type="button" variant="outlined" startIcon={<AddRounded/>} disabled={disabled || draft.variables.length >= settings.max_variables}
                onClick={() => edit({ ...draft, variables: [...draft.variables, { name: '', value: '' }] })}>افزودن متغیر</Button>
            </Stack>
            <Typography variant="body2" color="text.secondary">برای متن‌های ثابت مثل تیتر، یک نام انگلیسی و مقدار وارد کنید. «درج» متغیر را به محل نشانگر در قالب اضافه می‌کند.</Typography>
            {fieldErrors?.variables && <Alert severity="error">{fieldErrors.variables}</Alert>}
            {draft.variables.map((variable, index) => <Box key={index} sx={{ p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
              <Grid container spacing={1.25} sx={{ alignItems: 'center' }}>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <TextField id={`sms-variable-name-${index}`} label="نام متغیر" fullWidth required disabled={disabled} placeholder="intro" value={variable.name}
                    onChange={event => updateVariable(index, 'name', latinInputDigits(event.target.value))}
                    slotProps={{ htmlInput: { dir: 'ltr', autoComplete: 'off', maxLength: 24, pattern: variableName, spellCheck: false } }}/>
                </Grid>
                <Grid size={{ xs: 12, sm: 8 }}>
                  <TextField id={`sms-variable-value-${index}`} label="مقدار ثابت" fullWidth required disabled={disabled} value={variable.value}
                    onChange={event => updateVariable(index, 'value', event.target.value)} slotProps={{ htmlInput: { maxLength: settings.max_value_length } }}/>
                </Grid>
              </Grid>
              <Stack direction="row" spacing={.5} sx={{ mt: .5, alignItems: 'center', justifyContent: 'flex-end' }}>
                <Button type="button" disabled={disabled || !validName.test(variable.name)} onClick={() => insertVariable(variable.name)}>درج در قالب</Button>
                <IconButton type="button" aria-label={`حذف متغیر ${number(index + 1)}`} disabled={disabled}
                  onClick={() => edit({ ...draft, variables: draft.variables.filter((_, at) => at !== index) })}><DeleteOutlineRounded/></IconButton>
              </Stack>
            </Box>)}
            <Divider/>
            <Stack direction={{ xs: 'column', sm: 'row' }} useFlexGap sx={{ gap: 1, flexWrap: 'wrap' }}>
              <Button type="submit" variant="contained" startIcon={<SaveOutlined/>} disabled={disabled || !dirty || conflict}>{pending === 'save' ? 'در حال ذخیره…' : 'ذخیرهٔ قالب'}</Button>
              <Button type="button" variant="outlined" startIcon={<PreviewOutlined/>} disabled={disabled} onClick={() => void showPreview()}>{pending === 'preview' ? 'در حال آماده‌سازی…' : 'پیش‌نمایش تغییرات'}</Button>
              <Button type="button" startIcon={<RestoreRounded/>} disabled={disabled} onClick={() => edit({ template: settings.default_template, variables: [] })}>استفاده از قالب پیش‌فرض</Button>
              {conflict && <Button type="button" startIcon={<RefreshRounded/>} onClick={() => void load(lifetime.current?.signal)} disabled={disabled}>کنارگذاشتن ویرایش‌ها و دریافت قالب فعال</Button>}
            </Stack>
          </Stack>
        </Card>
      </Grid>
      {preview && <Grid size={{ xs: 12, lg: 5 }}>
        <Card component="section" aria-labelledby="sms-sample-title" sx={{ p: { xs: 2, sm: 3 }, minWidth: 0 }}>
          <Stack spacing={2} aria-live="polite">
            <Stack direction="row" useFlexGap sx={{ alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <PreviewOutlined color="primary"/><Typography id="sms-sample-title" ref={previewTitle} tabIndex={-1} component="h2" variant="h6">نمونهٔ پیامک</Typography>
              <Chip size="small" label={dirty && sampleIsCurrent ? 'پیش‌نویس' : 'قالب فعال'} variant="outlined"/>
            </Stack>
            {dirty && !sampleIsCurrent && <Typography variant="body2" color="text.secondary">برای دیدن ویرایش‌ها، «پیش‌نمایش تغییرات» را بزنید.</Typography>}
            <Box dir="auto" sx={{ p: 2, bgcolor: 'background.default', border: 1, borderColor: 'divider', borderRadius: 1,
              whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', lineHeight: 2 }}>{preview.full_sms}</Box>
            <Stack direction="row" useFlexGap sx={{ gap: .75, flexWrap: 'wrap' }}>
              <Chip size="small" color="primary" label={`${number(preview.sms_segments)} بخش پیامک`}/>
              <Chip size="small" variant="outlined" label={`${number(preview.sms_units)} واحد در نمونه`}/>
            </Stack>
            <Typography variant="caption" color="text.secondary">تا {number(preview.body_units)} واحد برای متن پیام جا دارد. این نمونه با لینک آزمایشی نمایش داده می‌شود.</Typography>
          </Stack>
        </Card>
      </Grid>}
    </Grid>}
  </Stack>;
}
