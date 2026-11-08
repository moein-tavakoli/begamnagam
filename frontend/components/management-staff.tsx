"use client";

import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react';
import Link from 'next/link';
import { DataGrid, type GridColDef, type GridPaginationModel } from '@mui/x-data-grid';
import { faIR } from '@mui/x-data-grid/locales';
import Alert from '@mui/material/Alert';
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import IconButton from '@mui/material/IconButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import AddRounded from '@mui/icons-material/AddRounded';
import BadgeOutlined from '@mui/icons-material/BadgeOutlined';
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded';
import EditOutlined from '@mui/icons-material/EditOutlined';
import GroupsOutlined from '@mui/icons-material/GroupsOutlined';
import MoreVertRounded from '@mui/icons-material/MoreVertRounded';
import RefreshRounded from '@mui/icons-material/RefreshRounded';
import SaveOutlined from '@mui/icons-material/SaveOutlined';
import { api, ApiError, errorMessage } from '@/lib/api';
import { latinInputDigits } from '@/lib/input-digits';
import { managementGridRange, managementPageSizes } from '@/lib/management';
import { staffEmployeeErrors, staffEmployeePayload, staffListPath, staffRoleErrors, staffRolePayload,
  type StaffEmployee, type StaffEmployeeErrors, type StaffEmployeeForm, type StaffPage, type StaffRole,
  type StaffRoleOption, type StaffSection, type StaffSectionKey } from '@/lib/staff';
import { ManagementDialog } from './management-ui';

type OnFailure = (error: unknown) => void;
const gridLocale = {
  ...faIR.components.MuiDataGrid.defaultProps.localeText,
  noRowsLabel: 'رکوردی پیدا نشد', noResultsOverlayLabel: 'نتیجه‌ای پیدا نشد',
  paginationRowsPerPage: 'تعداد سطر در صفحه:', paginationDisplayedRows: managementGridRange,
  paginationItemAriaLabel: (type: 'first' | 'last' | 'previous' | 'next') => ({ first: 'صفحهٔ اول', last: 'صفحهٔ آخر', previous: 'صفحهٔ قبل', next: 'صفحهٔ بعد' }[type]),
};

function useStaffList<T>(resource: 'employees' | 'roles', onFailure: OnFailure) {
  const [data, setData] = useState<StaffPage<T> | null>(null);
  const [pagination, setPagination] = useState<GridPaginationModel>({ page: 0, pageSize: 25 });
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => { setSearch(query); setPagination(current => ({ ...current, page: 0 })); }, 250);
    return () => clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    // Clear rows while changing pages or retrying so revoked/stale records cannot be edited.
    setData(current => current ? { ...current, rows: [] } : null);
    void api<StaffPage<T>>(staffListPath(resource, pagination.page, pagination.pageSize, search), { signal: controller.signal }).then(result => {
      if (controller.signal.aborted) return;
      if (result.total > 0 && pagination.page * pagination.pageSize >= result.total) {
        setPagination(current => ({ ...current, page: Math.max(0, Math.ceil(result.total / current.pageSize) - 1) }));
      } else setData(result);
    }).catch(cause => {
      if (controller.signal.aborted) return;
      setData(null); setError(errorMessage(cause)); onFailure(cause);
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [resource, pagination.page, pagination.pageSize, search, retry, onFailure]);
  return { data, query, setQuery, pagination, setPagination, loading, error, reload: () => setRetry(value => value + 1) };
}

function StaffGrid<T extends { id: number }>({ title, columns, list }: {
  title: string; columns: GridColDef<T>[]; list: ReturnType<typeof useStaffList<T>>;
}) {
  return <Box sx={{ width: '100%', minWidth: 0, height: Math.min(640, Math.max(360, (list.data?.rows.length || 0) * 68 + 154)) }}>
    <DataGrid<T> aria-label={title} rows={list.data?.rows || []} columns={columns} loading={list.loading}
      rowCount={list.data?.total ?? 0} paginationMode="server" paginationModel={list.pagination}
      onPaginationModelChange={model => list.setPagination(current => ({ page: model.pageSize === current.pageSize ? model.page : 0, pageSize: model.pageSize }))}
      pageSizeOptions={managementPageSizes.map(value => ({ value, label: value.toLocaleString('fa-IR') }))}
      disableColumnSorting disableColumnFilter disableColumnMenu disableColumnSelector disableRowSelectionOnClick rowSelection={false} hideFooterSelectedRowCount
      rowHeight={68} columnHeaderHeight={54} localeText={list.error ? { ...gridLocale, noRowsLabel: 'اطلاعات جدول دریافت نشد؛ دوباره تلاش کنید.' } : gridLocale}
      slotProps={{ basePagination: { material: { showFirstButton: true, showLastButton: true } } }}
      sx={{ bgcolor: 'background.paper', borderColor: 'divider', borderRadius: 2, fontFamily: 'inherit',
        '& .MuiDataGrid-cell': { display: 'flex', alignItems: 'center', minWidth: 0 },
        '& .MuiDataGrid-columnHeaderTitle': { fontWeight: 600 },
        '& .MuiDataGrid-footerContainer': { minHeight: { xs: 96, sm: 56 }, flexWrap: 'wrap' },
        '& .MuiTablePagination-root': { width: '100%', overflow: 'visible' },
        '& .MuiTablePagination-toolbar': { px: 1, flexWrap: 'wrap', justifyContent: 'center', gap: .5 },
        '& .MuiTablePagination-spacer': { display: 'none' },
        '& .MuiTablePagination-root .MuiTablePagination-selectLabel': { display: 'block', m: 0, fontSize: 12 },
        '& .MuiTablePagination-root .MuiTablePagination-input': { display: 'inline-flex', marginInline: 1 },
        '& .MuiTablePagination-displayedRows': { m: 0, fontSize: 12 },
        '& .MuiTablePagination-actions': { marginInlineStart: 0 },
      }} />
  </Box>;
}

function RowMenu({ label, focused, onEdit, onDelete }: { label: string; focused: boolean; onEdit: () => void; onDelete?: () => void }) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const id = useId();
  return <><IconButton size="small" aria-label={`عملیات ${label}`} aria-haspopup="menu" aria-controls={anchor ? id : undefined} aria-expanded={!!anchor}
    tabIndex={focused ? 0 : -1} onClick={event => setAnchor(event.currentTarget)}><MoreVertRounded /></IconButton>
    <Menu id={id} dir="rtl" anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)}>
      <MenuItem onClick={() => { setAnchor(null); onEdit(); }}><ListItemIcon><EditOutlined fontSize="small" /></ListItemIcon>ویرایش</MenuItem>
      {onDelete && <MenuItem onClick={() => { setAnchor(null); onDelete(); }} sx={{ color: 'error.main' }}><ListItemIcon><DeleteOutlineRounded color="error" fontSize="small" /></ListItemIcon>حذف نقش</MenuItem>}
    </Menu>
  </>;
}

function ListToolbar({ query, onQuery, onReload, onAdd, roleView }: { query: string; onQuery: (value: string) => void; onReload: () => void; onAdd: () => void; roleView?: boolean }) {
  return <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ alignItems: { sm: 'center' } }}>
    <TextField size="small" label={roleView ? 'جست‌وجوی نقش' : 'جست‌وجوی نام یا نام کاربری'} value={query} onChange={event => onQuery(event.target.value)} slotProps={{ htmlInput: { maxLength: 100 } }} sx={{ flex: 1 }} />
    <Stack direction="row" spacing={1}>
      <Button variant="outlined" onClick={onReload} startIcon={<RefreshRounded />}>تازه‌سازی</Button>
      <Button variant="contained" onClick={onAdd} startIcon={<AddRounded />}>{roleView ? 'نقش جدید' : 'کارمند جدید'}</Button>
    </Stack>
  </Stack>;
}

function FormActions({ busy, onClose, children }: { busy: boolean; onClose: () => void; children?: ReactNode }) {
  return <Stack direction="row" spacing={1} useFlexGap sx={{ justifyContent: 'flex-end', flexWrap: 'wrap', pt: 1 }}>
    <Button type="button" onClick={onClose} disabled={busy}>انصراف</Button>
    <Button type="submit" variant="contained" disabled={busy} startIcon={busy ? <CircularProgress color="inherit" size={18} /> : <SaveOutlined />}>{children || 'ذخیره'}</Button>
  </Stack>;
}

function FailureAlert({ cause, onReload }: { cause: unknown; onReload: () => void }) {
  if (!cause) return null;
  const conflict = cause instanceof ApiError && cause.code === 'revision_conflict';
  return <Alert severity="error" action={conflict ? <Button onClick={onReload} startIcon={<RefreshRounded />}>دریافت تازه</Button> : undefined}>
    {conflict ? 'این اطلاعات هم‌زمان تغییر کرده است. اطلاعات تازه را دریافت و دوباره ویرایش کنید.' : errorMessage(cause)}
  </Alert>;
}

function RoleSelector({ value, onChange, error, disabled, onFailure }: { value: StaffRoleOption | null; onChange: (role: StaffRoleOption | null) => void; error?: string; disabled: boolean; onFailure: OnFailure }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState<StaffRoleOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setLoading(true); setSearchError(''); setOptions([]);
    const timer = setTimeout(() => {
      void api<StaffPage<StaffRole>>(staffListPath('roles', 0, 25, query), { signal: controller.signal }).then(result => {
        if (!controller.signal.aborted) setOptions(result.rows);
      }).catch(cause => {
        if (!controller.signal.aborted) { setSearchError(errorMessage(cause)); onFailure(cause); }
      }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [open, query, retry, onFailure]);
  return <Stack spacing={.5}><Autocomplete<StaffRoleOption> value={value} onChange={(_, role) => onChange(role)} open={open} onOpen={() => setOpen(true)} onClose={() => setOpen(false)}
    options={options} disabled={disabled} loading={loading} loadingText="در حال جست‌وجوی نقش‌ها…" noOptionsText={searchError || 'نقشی پیدا نشد؛ نام دیگری جست‌وجو کنید.'}
    filterOptions={items => items} isOptionEqualToValue={(option, selected) => option.id === selected.id} getOptionLabel={option => option.name}
    onInputChange={(_, text, reason) => { if (reason === 'input' || reason === 'clear') setQuery(text); }}
    openText="نمایش نقش‌ها" closeText="بستن فهرست نقش‌ها" clearText="پاک‌کردن نقش"
    renderInput={params => <TextField {...params} required label="نقش کارمند" error={!!error || !!searchError} helperText={error || searchError || 'یک نقش انتخاب کنید؛ برای یافتن نقش‌های بیشتر، نام آن را بنویسید.'} slotProps={{ ...params.slotProps, htmlInput: { ...params.slotProps.htmlInput, maxLength: 100 } }} />} />
    {searchError && <Button size="small" sx={{ alignSelf: 'flex-start' }} startIcon={<RefreshRounded />} onClick={() => { setOpen(true); setRetry(value => value + 1); }}>تلاش دوباره برای دریافت نقش‌ها</Button>}
  </Stack>;
}

function EmployeeDialog({ employee, onClose, onSaved, onFailure }: { employee: StaffEmployee | null; onClose: () => void; onSaved: () => void; onFailure: OnFailure }) {
  const [form, setForm] = useState<StaffEmployeeForm>({ username: employee?.username || '', display_name: employee?.display_name || '', role: employee?.role || null, password: '', password_confirm: '', is_active: employee?.is_active ?? true });
  const [errors, setErrors] = useState<StaffEmployeeErrors>({});
  const [busy, setBusy] = useState(false);
  const [cause, setCause] = useState<unknown>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  function field<K extends keyof StaffEmployeeForm>(name: K, value: StaffEmployeeForm[K]) { setForm(current => ({ ...current, [name]: value })); setErrors(current => ({ ...current, [name]: undefined })); }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const invalid = staffEmployeeErrors(form, !!employee);
    setErrors(invalid); setCause(null);
    if (Object.keys(invalid).length) { requestAnimationFrame(() => formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()); return; }
    const request = new AbortController(); controller.current = request; setBusy(true);
    try {
      await api<StaffEmployee>(`/manage/staff/employees${employee ? `/${employee.id}` : ''}`, { method: employee ? 'PATCH' : 'POST', body: staffEmployeePayload(form, employee || undefined), signal: request.signal });
      if (!request.signal.aborted) onSaved();
    } catch (error) {
      if (request.signal.aborted) return;
      setCause(error); onFailure(error);
      if (error instanceof ApiError && error.fields) {
        const next: StaffEmployeeErrors = {};
        for (const [name, messages] of Object.entries(error.fields)) {
          const key = name === 'role_id' ? 'role' : name;
          if (['username', 'display_name', 'password', 'role'].includes(key)) next[key as keyof StaffEmployeeErrors] = Array.isArray(messages) ? messages.join(' ') : messages;
        }
        setErrors(next);
      }
    } finally { if (!request.signal.aborted) setBusy(false); }
  }
  return <ManagementDialog title={employee ? 'ویرایش کارمند' : 'کارمند جدید'} onClose={onClose} busy={busy}>
    <Box component="form" ref={formRef} noValidate onSubmit={submit}><Stack spacing={2}>
      <FailureAlert cause={cause} onReload={onSaved} />
      {!employee?.role && employee && <Alert severity="info">برای این کارمند هنوز نقشی تعیین نشده است. با انتخاب نقش، دسترسی‌های او به همان نقش محدود می‌شود.</Alert>}
      <TextField label="نام نمایشی" value={form.display_name} required autoFocus disabled={busy} error={!!errors.display_name} helperText={errors.display_name} autoComplete="off" slotProps={{ htmlInput: { maxLength: 150 } }} onChange={event => field('display_name', latinInputDigits(event.target.value))} />
      <TextField label="نام کاربری ورود" value={form.username} required disabled={busy || !!employee} error={!!errors.username} helperText={errors.username || (employee ? 'نام کاربری ورود قابل تغییر نیست.' : undefined)} autoComplete="off" slotProps={{ htmlInput: { maxLength: 150, dir: 'ltr', autoCapitalize: 'none', spellCheck: false } }} onChange={event => field('username', event.target.value)} />
      <RoleSelector value={form.role} onChange={role => field('role', role)} error={errors.role} disabled={busy} onFailure={onFailure} />
      <TextField type="password" label={employee ? 'رمز تازه (اختیاری)' : 'رمز اولیه'} value={form.password} required={!employee} disabled={busy} error={!!errors.password} helperText={errors.password || (employee ? 'برای حفظ رمز فعلی، این دو کادر را خالی بگذارید.' : 'رمز باید اعتبارسنجی امنیتی سامانه را بگذراند.')} autoComplete="new-password" onChange={event => field('password', event.target.value)} />
      <TextField type="password" label="تکرار رمز" value={form.password_confirm} required={!employee || !!form.password} disabled={busy} error={!!errors.password_confirm} helperText={errors.password_confirm} autoComplete="new-password" onChange={event => field('password_confirm', event.target.value)} />
      <FormControlLabel control={<Switch checked={form.is_active} disabled={busy} onChange={event => field('is_active', event.target.checked)} />} label={form.is_active ? 'کارمند فعال است' : 'کارمند غیرفعال است'} />
      <FormActions busy={busy} onClose={onClose}>{employee ? 'ذخیرهٔ تغییرات' : 'ایجاد کارمند'}</FormActions>
    </Stack></Box>
  </ManagementDialog>;
}

function EmployeeList({ onFailure }: { onFailure: OnFailure }) {
  const list = useStaffList<StaffEmployee>('employees', onFailure);
  const [editing, setEditing] = useState<StaffEmployee | null | undefined>(undefined);
  const columns: GridColDef<StaffEmployee>[] = [
    { field: '__actions__', headerName: 'عملیات', width: 72, sortable: false, renderCell: params => params.row.is_owner ? null : <RowMenu label={params.row.display_name || params.row.username} focused={params.hasFocus} onEdit={() => setEditing(params.row)} /> },
    { field: 'display_name', headerName: 'نام و نام کاربری', minWidth: 190, flex: 1, renderCell: params => <Stack sx={{ minWidth: 0 }}><Typography variant="body2" noWrap>{params.row.display_name || params.row.username}</Typography><Typography variant="caption" color="text.secondary" dir="ltr" noWrap sx={{ textAlign: 'start' }}>{params.row.username}</Typography></Stack> },
    { field: 'role', headerName: 'نقش', minWidth: 160, flex: 1, renderCell: params => <Chip size="small" variant="outlined" label={params.row.is_owner ? 'مدیر اصلی' : params.row.role?.name || 'نقش تعیین نشده'} color={params.row.is_owner ? 'primary' : 'default'} /> },
    { field: 'is_active', headerName: 'وضعیت', width: 110, renderCell: params => <Chip size="small" color={params.row.is_active ? 'success' : 'default'} label={params.row.is_active ? 'فعال' : 'غیرفعال'} /> },
  ];
  return <Stack spacing={2}>
    <ListToolbar query={list.query} onQuery={list.setQuery} onReload={list.reload} onAdd={() => setEditing(null)} />
    <Typography variant="body2" color="text.secondary">هر کارمند یک نقش دارد. مدیر اصلی از این فهرست قابل تغییر نیست.</Typography>
    {list.error && <Alert severity="error">{list.error}</Alert>}
    <StaffGrid title="فهرست کارمندان سامانه" columns={columns} list={list} />
    {editing !== undefined && <EmployeeDialog employee={editing} onClose={() => setEditing(undefined)} onFailure={onFailure} onSaved={() => { setEditing(undefined); list.reload(); }} />}
  </Stack>;
}

function RoleDialog({ role, catalog, onClose, onSaved, onFailure }: { role: StaffRole | null; catalog: StaffSection[]; onClose: () => void; onSaved: () => void; onFailure: OnFailure }) {
  const [name, setName] = useState(role?.name || '');
  const [sections, setSections] = useState<StaffSectionKey[]>(role?.sections || []);
  const [errors, setErrors] = useState<{ name?: string; sections?: string }>({});
  const [cause, setCause] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const invalid = staffRoleErrors(name, sections); setErrors(invalid); setCause(null);
    if (Object.keys(invalid).length) { requestAnimationFrame(() => formRef.current?.querySelector<HTMLElement>(invalid.name ? '[aria-invalid="true"]' : 'input[type="checkbox"]')?.focus()); return; }
    const request = new AbortController(); controller.current = request; setBusy(true);
    try {
      await api<StaffRole>(`/manage/staff/roles${role ? `/${role.id}` : ''}`, { method: role ? 'PATCH' : 'POST', body: staffRolePayload(name, sections, role?.revision), signal: request.signal });
      if (!request.signal.aborted) onSaved();
    } catch (error) { if (!request.signal.aborted) { setCause(error); onFailure(error); } }
    finally { if (!request.signal.aborted) setBusy(false); }
  }
  return <ManagementDialog title={role ? 'ویرایش نقش' : 'نقش جدید'} onClose={onClose} busy={busy}>
    <Box component="form" ref={formRef} noValidate onSubmit={submit}><Stack spacing={2}>
      <FailureAlert cause={cause} onReload={onSaved} />
      <TextField label="نام نقش" required autoFocus disabled={busy} value={name} error={!!errors.name} helperText={errors.name} slotProps={{ htmlInput: { maxLength: 80 } }} onChange={event => { setName(latinInputDigits(event.target.value)); setErrors(current => ({ ...current, name: undefined })); }} />
      {role && role.member_count > 0 && <Alert severity="info">تغییر این نقش روی دسترسی {role.member_count.toLocaleString('fa-IR')} کارمندِ دارای این نقش اعمال می‌شود.</Alert>}
      <Box component="fieldset" sx={{ m: 0, p: 0, border: 0 }} disabled={busy}>
        <Typography component="legend" variant="subtitle2" sx={{ mb: 1 }}>دسته‌های دسترسی</Typography>
        <Stack spacing={1}>{catalog.map(section => <Box key={section.key} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, p: 1.5 }}>
          <FormControlLabel sx={{ m: 0, alignItems: 'flex-start', width: '100%' }} control={<Checkbox checked={sections.includes(section.key)} disabled={busy} onChange={event => { setSections(current => event.target.checked ? [...current, section.key] : current.filter(key => key !== section.key)); setErrors(current => ({ ...current, sections: undefined })); }} />} label={<Stack spacing={.5} sx={{ pt: .75 }}><Typography variant="body2" sx={{ fontWeight: 600 }}>{section.label}</Typography><Typography variant="caption" color="text.secondary">{section.description}</Typography></Stack>} />
        </Box>)}</Stack>
        {errors.sections && <FormHelperText error role="alert">{errors.sections}</FormHelperText>}
      </Box>
      <FormActions busy={busy} onClose={onClose}>{role ? 'ذخیرهٔ نقش' : 'ایجاد نقش'}</FormActions>
    </Stack></Box>
  </ManagementDialog>;
}

function DeleteRoleDialog({ role, onClose, onSaved, onFailure }: { role: StaffRole; onClose: () => void; onSaved: () => void; onFailure: OnFailure }) {
  const [busy, setBusy] = useState(false);
  const [cause, setCause] = useState<unknown>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function remove() {
    if (busy || role.member_count > 0) return;
    const request = new AbortController(); controller.current = request; setBusy(true); setCause(null);
    try {
      await api(`/manage/staff/roles/${role.id}`, { method: 'DELETE', body: { revision: role.revision }, signal: request.signal });
      if (!request.signal.aborted) onSaved();
    } catch (error) { if (!request.signal.aborted) { setCause(error); onFailure(error); } }
    finally { if (!request.signal.aborted) setBusy(false); }
  }
  return <ManagementDialog title="حذف نقش" onClose={onClose} busy={busy}>
    <FailureAlert cause={cause} onReload={onSaved} />
    {role.member_count ? <Alert severity="warning">این نقش به {role.member_count.toLocaleString('fa-IR')} کارمند اختصاص دارد. ابتدا نقش آن‌ها را تغییر دهید.</Alert> : <Typography>نقش «{role.name}» حذف شود؟</Typography>}
    <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}><Button disabled={busy} onClick={onClose}>انصراف</Button><Button color="error" variant="contained" disabled={busy || role.member_count > 0} onClick={() => void remove()} startIcon={busy ? <CircularProgress color="inherit" size={18} /> : <DeleteOutlineRounded />}>حذف نقش</Button></Stack>
  </ManagementDialog>;
}

function RoleList({ onFailure }: { onFailure: OnFailure }) {
  const list = useStaffList<StaffRole>('roles', onFailure);
  const [catalog, setCatalog] = useState<StaffSection[]>([]);
  const [catalogError, setCatalogError] = useState('');
  const [catalogRetry, setCatalogRetry] = useState(0);
  const [editing, setEditing] = useState<StaffRole | null | undefined>(undefined);
  const [deleting, setDeleting] = useState<StaffRole | null>(null);
  useEffect(() => {
    const controller = new AbortController(); setCatalogError(''); setCatalog([]);
    void api<{ sections: StaffSection[] }>('/manage/staff/catalog', { signal: controller.signal }).then(result => {
      if (!controller.signal.aborted) setCatalog(result.sections);
    }).catch(cause => { if (!controller.signal.aborted) { setCatalogError(errorMessage(cause)); onFailure(cause); } });
    return () => controller.abort();
  }, [catalogRetry, onFailure]);
  const columns: GridColDef<StaffRole>[] = [
    { field: '__actions__', headerName: 'عملیات', width: 72, sortable: false, renderCell: params => <RowMenu label={params.row.name} focused={params.hasFocus} onEdit={() => setEditing(params.row)} onDelete={() => setDeleting(params.row)} /> },
    { field: 'name', headerName: 'نام نقش', minWidth: 160, flex: 1 },
    { field: 'sections', headerName: 'دسته‌های دسترسی', minWidth: 250, flex: 2, renderCell: params => <Typography variant="body2" noWrap title={params.row.sections.map(key => catalog.find(section => section.key === key)?.label || 'دستهٔ دسترسی').join('، ')}>{params.row.sections.map(key => catalog.find(section => section.key === key)?.label || 'دستهٔ دسترسی').join('، ')}</Typography> },
    { field: 'member_count', headerName: 'کارمندان', width: 115, valueFormatter: (value: number) => value.toLocaleString('fa-IR') },
  ];
  return <Stack spacing={2}>
    <ListToolbar roleView query={list.query} onQuery={list.setQuery} onReload={() => { list.reload(); setCatalogRetry(value => value + 1); }} onAdd={() => setEditing(null)} />
    <Typography variant="body2" color="text.secondary">دسترسی هر نقش از این دسته‌ها انتخاب می‌شود. نقشِ دارای کارمند تا انتقال کارمندان حذف نمی‌شود.</Typography>
    {list.error && <Alert severity="error">{list.error}</Alert>}
    {catalogError && <Alert severity="error" action={<Button onClick={() => setCatalogRetry(value => value + 1)}>تلاش دوباره</Button>}>{catalogError}</Alert>}
    <StaffGrid title="فهرست نقش‌های کارمندان" columns={columns} list={list} />
    {editing !== undefined && (catalog.length ? <RoleDialog role={editing} catalog={catalog} onFailure={onFailure} onClose={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); list.reload(); }} /> : <ManagementDialog title="دریافت دسته‌های دسترسی" onClose={() => setEditing(undefined)}>{catalogError ? <Alert severity="error" action={<Button onClick={() => setCatalogRetry(value => value + 1)}>تلاش دوباره</Button>}>{catalogError}</Alert> : <Stack direction="row" spacing={1} role="status"><CircularProgress size={20} /><Typography>در حال دریافت دسته‌های دسترسی…</Typography></Stack>}</ManagementDialog>)}
    {deleting && <DeleteRoleDialog role={deleting} onFailure={onFailure} onClose={() => setDeleting(null)} onSaved={() => { setDeleting(null); list.reload(); }} />}
  </Stack>;
}

export function ManagementStaff({ view = 'employees', onFailure }: { view?: 'employees' | 'roles'; onFailure: OnFailure }) {
  return <Stack spacing={3} sx={{ minWidth: 0 }}>
    <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}><GroupsOutlined color="primary" /><Typography component="h2" variant="h5">کارمندان سامانه</Typography></Stack>
    <Tabs value={view} aria-label="مدیریت کارمندان و نقش‌ها" variant="fullWidth">
      <Tab value="employees" label="کارمندان" icon={<GroupsOutlined />} iconPosition="start" component={Link} href="/manage/staff" />
      <Tab value="roles" label="نقش‌ها" icon={<BadgeOutlined />} iconPosition="start" component={Link} href="/manage/staff/roles" />
    </Tabs>
    {view === 'roles' ? <RoleList onFailure={onFailure} /> : <EmployeeList onFailure={onFailure} />}
  </Stack>;
}
