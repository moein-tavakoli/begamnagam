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
import Popover from '@mui/material/Popover';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import AddRounded from '@mui/icons-material/AddRounded';
import CloseRounded from '@mui/icons-material/CloseRounded';
import DataObjectOutlined from '@mui/icons-material/DataObjectOutlined';
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded';
import EmojiEmotionsOutlined from '@mui/icons-material/EmojiEmotionsOutlined';
import PreviewOutlined from '@mui/icons-material/PreviewOutlined';
import RefreshRounded from '@mui/icons-material/RefreshRounded';
import RestoreRounded from '@mui/icons-material/RestoreRounded';
import SaveOutlined from '@mui/icons-material/SaveOutlined';
import SmsOutlined from '@mui/icons-material/SmsOutlined';
import { api, ApiError, errorMessage } from '@/lib/api';
import { latinInputDigits } from '@/lib/input-digits';
import { managementNumber as number } from '@/lib/management';
import { KavenegarKeySettings } from './kavenegar-key-settings';

type Variable = { name: string; value: string };
type Draft = { template: string; variables: Variable[]; sender: string };
export type SmsTemplateDraftMemory = { draft: Draft; revision: number } | null;
type Preview = {
  full_sms: string;
  sms_units: number;
  sms_segments: number;
  body_units: number;
  has_message: boolean;
  has_opt_out: boolean;
  length_warning: boolean;
};
type Settings = Draft & {
  revision: number;
  preview: Preview;
  default_template: string;
  default_sender: string;
  max_variables: number;
};

const path = '/manage/sms-template';
const variableName = '[a-z][a-z0-9_]{0,23}';
const validName = new RegExp(`^${variableName}$`);
const systemSlots = [
  { name: 'message', label: 'متن پیام' },
  { name: 'reply', label: 'لینک پاسخ یا لغو دریافت' },
  { name: 'opt_out', label: 'لینک لغو دریافت' },
  { name: 'site_url', label: 'آدرس سایت' },
];
const templateEmojis = [
  { value: '😊', label: 'لبخند' },
  { value: '❤️', label: 'قلب قرمز' },
  { value: '🌹', label: 'گل رز' },
  { value: '🙏', label: 'دست‌های به هم چسبیده' },
  { value: '✨', label: 'درخشش' },
  { value: '👍', label: 'شست رو به بالا' },
  { value: '👏', label: 'دست زدن' },
  { value: '🤝', label: 'دست دادن' },
  { value: '🌷', label: 'گل لاله' },
  { value: '🎉', label: 'جشن' },
  { value: '💜', label: 'قلب بنفش' },
];
const emojiPickerId = 'sms-template-emoji-picker';

function draftFrom({ template, variables, sender = '' }: Draft): Draft {
  return { template, variables, sender };
}

export function SmsTemplateSettings({ onFailure, memory, canManageKavenegarKey }: {
  onFailure: (error: unknown) => void;
  memory: { current: SmsTemplateDraftMemory };
  canManageKavenegarKey: boolean;
}) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [draft, setDraft] = useState<Draft>({ template: '', variables: [], sender: '' });
  const [sample, setSample] = useState<{ key: string; preview: Preview } | null>(null);
  const [pending, setPending] = useState<'load' | 'preview' | 'save' | null>('load');
  const [failure, setFailure] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const [emojiAnchor, setEmojiAnchor] = useState<HTMLButtonElement | null>(null);
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

  function insertTemplateText(text: string) {
    const input = templateInput.current;
    const start = input?.selectionStart ?? draft.template.length;
    const end = input?.selectionEnd ?? start;
    const template = draft.template.slice(0, start) + text + draft.template.slice(end);
    const caret = start + text.length;
    edit({ ...draft, template });
    requestAnimationFrame(() => {
      input?.focus();
      input?.setSelectionRange(caret, caret);
    });
  }

  function insertVariable(name: string) {
    insertTemplateText(`{{${name}}}`);
  }

  const { sender, ...layout } = draft;
  const layoutKey = JSON.stringify(layout);
  const layoutDirty = settings !== null && layoutKey !== JSON.stringify({ template: settings.template, variables: settings.variables });
  const dirty = settings !== null && (layoutDirty || sender !== (settings.sender ?? ''));
  const revision = memory.current?.revision ?? settings?.revision;
  const conflict = dirty && revision !== settings?.revision;

  async function showPreview() {
    if (pending || !settings) return;
    const signal = lifetime.current?.signal;
    setPending('preview');
    setFailure(null);
    try {
      const preview = await api<Preview>(`${path}/preview`, { method: 'POST', body: layout, signal });
      setSample({ key: layoutKey, preview });
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
  const sampleIsCurrent = sample?.key === layoutKey;
  const preview = sampleIsCurrent ? sample.preview : settings?.preview;
  const disabled = pending !== null;

  return <Stack spacing={2.5}>
    {canManageKavenegarKey && <KavenegarKeySettings onFailure={onFailure}/>}
    <Alert severity="info" variant="outlined">
      قالب ذخیره‌شده روی پیش‌نمایش‌های تازهٔ پیام به گیرنده اعمال می‌شود. پیش‌نمایش‌های قبلی با همان متنِ تأییدشده ارسال می‌شوند.
    </Alert>
    {failure != null && <Alert severity="error">{errorMessage(failure)}</Alert>}
    {conflict && <Alert severity="warning">تنظیمات فعال تغییر کرده‌اند. ویرایش‌های شما حفظ شده‌اند.</Alert>}
    {saved && <Alert severity="success">تنظیمات پیامک ذخیره شد.</Alert>}
    {!settings && (disabled ? <Stack direction="row" spacing={1.5} role="status" sx={{ alignItems: 'center', py: 2 }}>
      <CircularProgress size={20} aria-hidden="true"/><Typography>در حال دریافت تنظیمات پیامک…</Typography>
    </Stack> : <Box><Button onClick={() => void load(lifetime.current?.signal, true)} startIcon={<RefreshRounded/>}>تلاش دوباره</Button></Box>)}
    {settings && <Grid container spacing={2.5} sx={{ alignItems: 'flex-start' }}>
      <Grid size={{ xs: 12, lg: 7 }}>
        <Card component="form" onSubmit={save} sx={{ p: { xs: 2, sm: 3 }, minWidth: 0 }}>
          <Stack spacing={2.5}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
              <SmsOutlined color="primary"/><Typography component="h2" variant="h6">تنظیمات پیامک</Typography>
            </Stack>
            <TextField id="sms-sender" label="شمارهٔ فرستنده" fullWidth disabled={disabled}
              value={sender} placeholder={settings.default_sender}
              onChange={event => edit({ ...draft, sender: latinInputDigits(event.target.value).replace(/\s/g, '') })}
              error={!!fieldErrors?.sender}
              helperText={fieldErrors?.sender || 'شمارهٔ خط مجاز کاوه‌نگار را وارد کنید. کادر خالی از خط پیش‌فرض سرور استفاده می‌کند.'}
              slotProps={{ inputLabel: { shrink: true }, htmlInput: { dir: 'ltr', inputMode: 'numeric', autoComplete: 'off' } }}/>
            <TextField id="sms-template-text" inputRef={templateInput} label="متن قالب" multiline minRows={5} fullWidth required
              value={draft.template} disabled={disabled} onChange={event => edit({ ...draft, template: latinInputDigits(event.target.value) })}
              error={!!fieldErrors?.template}
              helperText={fieldErrors?.template || 'متن و متغیرها را در هر جای قالب بنویسید. روی متغیر بزنید تا در محل نشانگر درج شود.'}
              slotProps={{ htmlInput: { spellCheck: false, dir: 'rtl' } }}/>
            <Stack spacing={1}>
              <Stack direction="row" useFlexGap sx={{ alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                <Button type="button" size="small" variant="outlined" startIcon={<EmojiEmotionsOutlined/>} disabled={disabled}
                  aria-haspopup="dialog" aria-expanded={!!emojiAnchor} aria-controls={emojiAnchor ? emojiPickerId : undefined}
                  onClick={event => setEmojiAnchor(event.currentTarget)}>درج ایموجی</Button>
                {systemSlots.map(slot => <Chip key={slot.name} color="primary" variant="outlined" disabled={disabled}
                  aria-label={'درج ' + slot.label} onClick={() => insertVariable(slot.name)}
                  label={<Stack direction="row" spacing={.75} sx={{ alignItems: 'center' }}>
                    <span>{slot.label}</span><Box component="code" dir="ltr">{'{{' + slot.name + '}}'}</Box>
                  </Stack>}/>)}
              </Stack>
              <Popover open={!!emojiAnchor} anchorEl={emojiAnchor} onClose={() => setEmojiAnchor(null)} dir="rtl"
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }} transitionDuration={0}
                slotProps={{ paper: {
                  id: emojiPickerId, role: 'dialog', 'aria-modal': true, 'aria-label': 'انتخاب ایموجی', tabIndex: -1,
                  sx: {
                    boxSizing: 'border-box', width: 216, p: 1, display: 'grid', gap: 1, gridTemplateColumns: 'repeat(auto-fit, 44px)',
                    '& .Mui-focusVisible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: -2 },
                  },
                } }}>
                {templateEmojis.map(({ value, label }) => <IconButton key={value} type="button" aria-label={label}
                  onClick={() => { setEmojiAnchor(null); insertTemplateText(value); }}>
                  <span aria-hidden="true">{value}</span>
                </IconButton>)}
                <IconButton type="button" aria-label="بستن انتخاب ایموجی" onClick={() => setEmojiAnchor(null)}><CloseRounded/></IconButton>
              </Popover>
              <Typography variant="caption" color="text.secondary">در نوبت مجاز، اولین جای لینک در قالب به لینک مشترک پاسخ و لغو دریافت اختصاص دارد. برای پیام بدون نوبت پاسخ، لینک لغو دریافت درج می‌شود.</Typography>
            </Stack>
            <Divider/>
            <Stack direction="row" useFlexGap sx={{ alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <DataObjectOutlined color="primary"/><Typography component="h3" variant="subtitle1" sx={{ fontWeight: 700 }}>متغیرهای سفارشی</Typography>
              </Stack>
              <Button type="button" variant="outlined" startIcon={<AddRounded/>} disabled={disabled || draft.variables.length >= settings.max_variables}
                onClick={() => edit({ ...draft, variables: [...draft.variables, { name: '', value: '' }] })}>افزودن متغیر</Button>
            </Stack>
            <Typography variant="body2" color="text.secondary">برای متن ثابت دلخواه، مثل امضا یا توضیح، یک نام انگلیسی و مقدار وارد کنید.</Typography>
            {fieldErrors?.variables && <Alert severity="error">{fieldErrors.variables}</Alert>}
            {draft.variables.map((variable, index) => <Box key={index} sx={{ p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
              <Grid container spacing={1.25} sx={{ alignItems: 'center' }}>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <TextField id={`sms-variable-name-${index}`} label="نام متغیر" fullWidth required disabled={disabled} placeholder="intro" value={variable.name}
                    onChange={event => updateVariable(index, 'name', latinInputDigits(event.target.value))}
                    slotProps={{ htmlInput: { dir: 'ltr', autoComplete: 'off', maxLength: 24, pattern: variableName, spellCheck: false } }}/>
                </Grid>
                <Grid size={{ xs: 12, sm: 8 }}>
                  <TextField id={`sms-variable-value-${index}`} label="مقدار ثابت" fullWidth multiline minRows={2} disabled={disabled} value={variable.value}
                    onChange={event => updateVariable(index, 'value', latinInputDigits(event.target.value))}/>
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
              <Button type="submit" variant="contained" startIcon={<SaveOutlined/>} disabled={disabled || !dirty || conflict}>{pending === 'save' ? 'در حال ذخیره…' : 'ذخیرهٔ تنظیمات'}</Button>
              <Button type="button" variant="outlined" startIcon={<PreviewOutlined/>} disabled={disabled} onClick={() => void showPreview()}>{pending === 'preview' ? 'در حال آماده‌سازی…' : 'پیش‌نمایش تغییرات'}</Button>
              <Button type="button" startIcon={<RestoreRounded/>} disabled={disabled} onClick={() => edit({ ...draft, template: settings.default_template, variables: [] })}>استفاده از قالب پیش‌فرض</Button>
              {conflict && <Button type="button" startIcon={<RefreshRounded/>} onClick={() => void load(lifetime.current?.signal)} disabled={disabled}>کنارگذاشتن ویرایش‌ها و دریافت تنظیمات فعال</Button>}
            </Stack>
          </Stack>
        </Card>
      </Grid>
      {preview && <Grid size={{ xs: 12, lg: 5 }}>
        <Card component="section" aria-labelledby="sms-sample-title" sx={{ p: { xs: 2, sm: 3 }, minWidth: 0 }}>
          <Stack spacing={2} aria-live="polite">
            <Stack direction="row" useFlexGap sx={{ alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <PreviewOutlined color="primary"/><Typography id="sms-sample-title" ref={previewTitle} tabIndex={-1} component="h2" variant="h6">نمونهٔ پیامک</Typography>
              <Chip size="small" label={layoutDirty && sampleIsCurrent ? 'پیش‌نویس' : 'قالب فعال'} variant="outlined"/>
            </Stack>
            {layoutDirty && !sampleIsCurrent && <Typography variant="body2" color="text.secondary">برای دیدن ویرایش‌ها، «پیش‌نمایش تغییرات» را بزنید.</Typography>}
            <Box dir="auto" sx={{ p: 2, bgcolor: 'background.default', border: 1, borderColor: 'divider', borderRadius: 1,
              whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', lineHeight: 2 }}>{preview.full_sms}</Box>
            <Stack direction="row" useFlexGap sx={{ gap: .75, flexWrap: 'wrap' }}>
              <Chip size="small" color="primary" label={`${number(preview.sms_segments)} بخش پیامک`}/>
              <Chip size="small" variant="outlined" label={`${number(preview.sms_units)} واحد در نمونه`}/>
            </Stack>
            {preview.has_message === false && <Alert severity="warning" variant="outlined">این قالب جای متن تأییدشدهٔ کاربر را ندارد.</Alert>}
            {preview.has_opt_out === false && <Alert severity="info" variant="outlined">اگر پیام امکان پاسخ نداشته باشد، لینک لغو دریافت خودکار به پایان پیامک اضافه می‌شود.</Alert>}
            {preview.length_warning && <Alert severity="warning" variant="outlined">این قالب ممکن است به بیش از ۳ بخش پیامک نیاز داشته باشد. می‌توانید آن را با همین طول ذخیره کنید.</Alert>}
            <Typography variant="caption" color="text.secondary">
              {preview.has_message !== false && <>برای ماندن در ۳ بخش، حدود {number(preview.body_units)} واحد برای متن پیام جا هست. </>}
              لینک این نمونه آزمایشی است.
            </Typography>
          </Stack>
        </Card>
      </Grid>}
    </Grid>}
  </Stack>;
}
