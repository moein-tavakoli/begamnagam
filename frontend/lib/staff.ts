import { latinInputDigits } from './input-digits.ts';

export type StaffSectionKey = 'support' | 'finance' | 'operations' | 'users' | 'content' | 'settings';
export type StaffSection = { key: StaffSectionKey; label: string; description: string };
export type StaffRoleOption = { id: number; name: string };
export type StaffRole = StaffRoleOption & { sections: StaffSectionKey[]; revision: number; member_count: number };
export type StaffEmployee = { id: number; username: string; display_name: string; role: StaffRoleOption | null; is_active: boolean; is_owner: boolean; revision: number };
export type StaffPage<T> = { rows: T[]; total: number; page: number; page_size: number };
export type StaffEmployeeForm = { username: string; display_name: string; role: StaffRoleOption | null; password: string; password_confirm: string; is_active: boolean };
export type StaffEmployeeErrors = Partial<Record<keyof StaffEmployeeForm, string>>;
const sectionKeys: StaffSectionKey[] = ['support', 'finance', 'operations', 'users', 'content', 'settings'];
export function staffListPath(resource: 'employees' | 'roles', page: number, pageSize: number, query = ''): string {
  const params = new URLSearchParams({
    page: String(Number.isInteger(page) && page >= 0 ? page + 1 : 1),
    page_size: String([10, 25, 50, 100].includes(pageSize) ? pageSize : 25),
    query: query.trim(),
  });
  return `/manage/staff/${resource}?${params}`;
}
export function staffEmployeeErrors(form: StaffEmployeeForm, editing = false): StaffEmployeeErrors {
  const errors: StaffEmployeeErrors = {};
  if (!editing && (!form.username.trim() || form.username.length > 150)) errors.username = 'نام کاربری را حداکثر با ۱۵۰ نویسه وارد کنید.';
  if (!form.display_name.trim() || form.display_name.trim().length > 150) errors.display_name = 'نام نمایشی را حداکثر با ۱۵۰ نویسه وارد کنید.';
  if (!form.role) errors.role = 'یک نقش برای کارمند انتخاب کنید.';
  if (!editing && !form.password) errors.password = 'رمز اولیه را وارد کنید.';
  if (form.password !== form.password_confirm) errors.password_confirm = 'رمز و تکرار آن یکسان نیستند.';
  return errors;
}
export function staffEmployeePayload(form: StaffEmployeeForm, employee?: StaffEmployee): Record<string, unknown> {
  if (employee?.is_owner) throw new Error('مدیر اصلی از این بخش قابل ویرایش نیست.');
  const errors = staffEmployeeErrors(form, !!employee);
  if (Object.keys(errors).length) throw new Error(Object.values(errors)[0]);
  const payload: Record<string, unknown> = {
    display_name: latinInputDigits(form.display_name.trim()), role_id: form.role!.id, is_active: form.is_active,
  };
  if (employee) payload.revision = employee.revision;
  else payload.username = form.username;
  if (form.password) payload.password = form.password;
  return payload;
}
export function staffRoleErrors(name: string, sections: StaffSectionKey[]): { name?: string; sections?: string } {
  const errors: { name?: string; sections?: string } = {};
  if (!name.trim() || name.trim().length > 80) errors.name = 'نام نقش را حداکثر با ۸۰ نویسه وارد کنید.';
  if (!sections.length) errors.sections = 'حداقل یک دستهٔ دسترسی انتخاب کنید.';
  else if (sections.some(section => !sectionKeys.includes(section))) errors.sections = 'دستهٔ دسترسی انتخاب‌شده معتبر نیست.';
  return errors;
}
export function staffRolePayload(name: string, sections: StaffSectionKey[], revision?: number): Record<string, unknown> {
  const errors = staffRoleErrors(name, sections);
  if (Object.keys(errors).length) throw new Error(Object.values(errors)[0]);
  return { name: latinInputDigits(name.trim()), sections: [...new Set(sections)], ...(revision === undefined ? {} : { revision }) };
}
