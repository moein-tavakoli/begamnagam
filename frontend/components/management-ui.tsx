"use client";

import Button, { type ButtonProps } from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import CloseRounded from '@mui/icons-material/CloseRounded';
import { forwardRef, useId, type ButtonHTMLAttributes, type ChangeEvent, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes, type ComponentProps, type ReactNode } from 'react';
import { DigitInput } from './digit-input';

type FieldCopy = { label?: ReactNode; helperText?: ReactNode; error?: boolean };
type ActionButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'color'> & Pick<ButtonProps, 'startIcon'|'endIcon'|'sx'|'variant'|'color'|'size'>;
export function ManagementButton({ className = '', type = 'submit', variant, color, ...props }: ActionButtonProps) {
  return <Button {...props} type={type} className={className} variant={variant || (className.includes('secondary') ? 'outlined' : 'contained')} color={color || (className.includes('danger') ? 'error' : 'primary')} />;
}

// Keep native constraints and FormData on the actual input element.
export function ManagementInput({ type, className, label, helperText, error, onChange, ...props }: InputHTMLAttributes<HTMLInputElement> & FieldCopy) {
  if (type === 'checkbox') {
    const { role, ...native } = props;
    const Control = role === 'switch' ? Switch : Checkbox;
    return <Control className={className} name={props.name} disabled={props.disabled} checked={props.checked} defaultChecked={props.defaultChecked} onChange={onChange} required={props.required} slotProps={{ input: { ...native, role } }} />;
  }
  return <TextField id={props.id} fullWidth size="small" label={label} helperText={helperText} error={error ?? (props['aria-invalid'] === true || props['aria-invalid'] === 'true')} className={className} type={type} name={props.name} disabled={props.disabled} required={props.required} value={props.value} defaultValue={props.defaultValue} onChange={onChange} autoComplete={props.autoComplete} slotProps={{htmlInput:props}} />;
}

export function ManagementSelect({ children, className, label, helperText, error, onChange, ...props }: SelectHTMLAttributes<HTMLSelectElement> & FieldCopy) {
  return <TextField id={props.id} select fullWidth size="small" className={className} label={label} helperText={helperText} error={error} name={props.name} value={props.value} defaultValue={props.defaultValue} onChange={event => onChange?.(event as unknown as ChangeEvent<HTMLSelectElement>)} disabled={props.disabled} required={props.required} slotProps={{ select: { native:true, inputProps:props as unknown as InputHTMLAttributes<HTMLInputElement> }, inputLabel:{shrink:true} }}>{children}</TextField>;
}

export function ManagementTextarea({ className, rows = 3, label, helperText, error, onChange, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & FieldCopy) {
  return <TextField id={props.id} fullWidth size="small" multiline rows={Number(rows)} label={label} helperText={helperText} error={error} className={className} value={props.value} defaultValue={props.defaultValue} onChange={onChange} name={props.name} required={props.required} disabled={props.disabled} slotProps={{htmlInput:props}} />;
}

const DigitAdapter = forwardRef<HTMLInputElement, ComponentProps<typeof DigitInput>>(function DigitAdapter(props, ref) {
  return <DigitInput {...props} inputRef={ref} />;
});
export function ManagementDigitInput({ label, helperText, error, ...props }: ComponentProps<typeof DigitInput> & FieldCopy) {
  return <TextField id={props.id} fullWidth size="small" label={label} helperText={helperText} error={error ?? (props['aria-invalid'] === true || props['aria-invalid'] === 'true')} name={props.name} value={props.value} defaultValue={props.defaultValue} required={props.required} disabled={props.disabled} slotProps={{input:{inputComponent:DigitAdapter},htmlInput:props,inputLabel:{shrink:true}}} />;
}

export function ManagementDialog({ title, children, onClose, busy = false }: { title: string; children: ReactNode; onClose: () => void; busy?: boolean }) {
  const titleId = useId();
  return <Dialog open dir="rtl" aria-labelledby={titleId} onClose={() => { if (!busy) onClose(); }} fullWidth maxWidth="sm" slotProps={{paper:{sx:{m:2,width:'calc(100% - 32px)',maxHeight:'calc(100dvh - 32px)'}}}}>
    <DialogTitle component="div"><Stack direction="row" sx={{alignItems:"center",justifyContent:"space-between",gap:1}}><Typography id={titleId} component="h2" variant="h6">{title}</Typography><IconButton aria-label="بستن پنجره" disabled={busy} onClick={onClose}><CloseRounded /></IconButton></Stack></DialogTitle>
    <DialogContent><Stack spacing={2} sx={{pt:1}}>{children}</Stack></DialogContent>
  </Dialog>;
}
