"use client";

import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import Switch from '@mui/material/Switch';
import OutlinedInput from '@mui/material/OutlinedInput';
import NativeSelect from '@mui/material/NativeSelect';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import IconButton from '@mui/material/IconButton';
import { forwardRef, useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes, type ComponentProps, type ReactNode } from 'react';
import { DigitInput } from './digit-input';
import { Icon } from './icons';

// Keep the existing native form contract (FormData, constraint validation and
// Persian digit normalization) while using MUI controls throughout management.
export function ManagementButton({ className = '', type = 'submit', ...props }: Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'color'>) {
  return <Button {...props} type={type} className={className} variant={className.includes('secondary') ? 'outlined' : 'contained'} color={className.includes('danger') ? 'error' : 'primary'} />;
}

export function ManagementInput({ type, className, onChange, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  if (type === 'checkbox') {
    const { role, ...inputProps } = props;
    const Control = role === 'switch' ? Switch : Checkbox;
    return <Control className={className} name={props.name} disabled={props.disabled} checked={props.checked} defaultChecked={props.defaultChecked} onChange={onChange} required={props.required} slotProps={{ input: { ...inputProps, role } }} />;
  }
  return <OutlinedInput className={`manage-mui-field ${className || ''}`} fullWidth type={type} name={props.name} disabled={props.disabled} required={props.required} error={props['aria-invalid'] === true || props['aria-invalid'] === 'true'} value={props.value} defaultValue={props.defaultValue} onChange={onChange} slotProps={{ input: props }} />;
}

export function ManagementSelect({ children, className, onChange, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <NativeSelect className={`manage-mui-field ${className || ''}`} fullWidth input={<OutlinedInput />} inputProps={props} value={props.value} defaultValue={props.defaultValue} onChange={onChange} disabled={props.disabled} required={props.required}>{children}</NativeSelect>;
}

export function ManagementTextarea({ className, rows = 3, onChange, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <OutlinedInput className={`manage-mui-field ${className || ''}`} fullWidth multiline rows={Number(rows)} value={props.value} defaultValue={props.defaultValue} onChange={onChange} name={props.name} required={props.required} disabled={props.disabled} slotProps={{ input: props as NonNullable<ComponentProps<typeof OutlinedInput>['slotProps']>['input'] }} />;
}

const DigitAdapter = forwardRef<HTMLInputElement, ComponentProps<typeof DigitInput>>(function DigitAdapter(props, ref) {
  return <DigitInput {...props} inputRef={ref} />;
});
export function ManagementDigitInput(props: ComponentProps<typeof DigitInput>) {
  return <OutlinedInput className="manage-mui-field" fullWidth inputComponent={DigitAdapter} name={props.name} value={props.value} defaultValue={props.defaultValue} required={props.required} disabled={props.disabled} error={props['aria-invalid'] === true || props['aria-invalid'] === 'true'} slotProps={{ input: props }} />;
}

export function ManagementDialog({ title, children, onClose, busy = false }: { title: string; children: ReactNode; onClose: () => void; busy?: boolean }) {
  const titleId = useId();
  return <Dialog open dir="rtl" aria-labelledby={titleId} onClose={() => { if (!busy) onClose(); }} fullWidth maxWidth="sm">
    <DialogTitle id={titleId} className="manage-mui-dialog-title">{title}<IconButton aria-label="بستن پنجره" disabled={busy} onClick={onClose}><Icon name="close" size={20} /></IconButton></DialogTitle>
    <DialogContent className="manage-app manage-mui-dialog-content">{children}</DialogContent>
  </Dialog>;
}
