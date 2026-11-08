import assert from 'node:assert/strict';
import test from 'node:test';
import { staffEmployeeErrors, staffEmployeePayload, staffListPath, staffRoleErrors, staffRolePayload, type StaffEmployee, type StaffEmployeeForm } from '../lib/staff.ts';

const form: StaffEmployeeForm = { username: 'agent۰۱', display_name: 'کارمند ۱۲', role: { id: 7, name: 'پشتیبانی' }, password: 'Secret۰۱ @ ', password_confirm: 'Secret۰۱ @ ', is_active: true };
const employee: StaffEmployee = { id: 11, username: 'agent۰۱', display_name: 'کارمند', role: form.role, is_active: true, is_owner: false, revision: 4 };

test('staff list URLs use bounded server pagination and encode remote search', () => {
  assert.equal(staffListPath('roles', 1, 25, '  مالی & پشتیبانی  '), '/manage/staff/roles?page=2&page_size=25&query=%D9%85%D8%A7%D9%84%DB%8C+%26+%D9%BE%D8%B4%D8%AA%DB%8C%D8%A8%D8%A7%D9%86%DB%8C');
  assert.equal(staffListPath('employees', -1, 1000), '/manage/staff/employees?page=1&page_size=25&query=');
  assert.match(staffListPath('roles', 0, 100), /page_size=100/);
});
test('employees require a selected role and confirmed initial password', () => {
  assert.deepEqual(staffEmployeeErrors(form), {});
  assert(staffEmployeeErrors({ ...form, role: null }).role);
  assert(staffEmployeeErrors({ ...form, username: '  ' }).username);
  assert(staffEmployeeErrors({ ...form, password: '', password_confirm: '' }).password);
  assert(staffEmployeeErrors({ ...form, password_confirm: 'different' }).password_confirm);
});
test('editing leaves the password optional but validates any attempted change', () => {
  assert.deepEqual(staffEmployeeErrors({ ...form, password: '', password_confirm: '' }, true), {});
  assert(staffEmployeeErrors({ ...form, password: '', password_confirm: 'confirmation only' }, true).password_confirm);
  assert(staffEmployeeErrors({ ...form, password_confirm: '' }, true).password_confirm);
});
test('employee creation sends only allowed fields and preserves credentials exactly', () => {
  const hostile = { ...form, groups: [1], is_superuser: true, permissions: ['manage_staff'] };
  assert.deepEqual(staffEmployeePayload(hostile), { username: 'agent۰۱', display_name: 'کارمند 12', password: 'Secret۰۱ @ ', role_id: 7, is_active: true });
  assert.equal(form.display_name, 'کارمند ۱۲');
});
test('employee edits send a revision and omit immutable username and empty password', () => {
  const payload = staffEmployeePayload({ ...form, password: '', password_confirm: '', is_active: false }, employee);
  assert.deepEqual(payload, { display_name: 'کارمند 12', role_id: 7, is_active: false, revision: 4 });
  assert.equal(staffEmployeePayload(form, employee).password, form.password);
});
test('owner editing and invalid employee submissions fail before transport', () => {
  assert.throws(() => staffEmployeePayload(form, { ...employee, is_owner: true }));
  assert.throws(() => staffEmployeePayload({ ...form, role: null }));
  assert.throws(() => staffEmployeePayload({ ...form, password_confirm: 'wrong' }));
});
test('roles validate the bounded six-section catalog and trimmed name', () => {
  assert.deepEqual(staffRoleErrors('  پشتیبانی  ', ['support']), {});
  assert(staffRoleErrors('  ', ['support']).name);
  assert(staffRoleErrors('ن'.repeat(81), ['support']).name);
  assert(staffRoleErrors('نقش', []).sections);
  assert(staffRoleErrors('نقش', ['manage_staff' as 'support']).sections);
});
test('role payloads canonicalize new labels and include revision only for edits', () => {
  assert.deepEqual(staffRolePayload('  نقش ۱۲ ', ['support', 'finance', 'support']), { name: 'نقش 12', sections: ['support', 'finance'] });
  assert.deepEqual(staffRolePayload('مالی', ['finance'], 9), { name: 'مالی', sections: ['finance'], revision: 9 });
  assert.throws(() => staffRolePayload('', ['support']));
});
