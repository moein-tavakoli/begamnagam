# Staff roles and monitoring refinements implementation plan

> **For agentic workers:** Use dispatching-parallel-agents for isolated backend,
> staff UI and monitoring work, followed by whole-change independent review.

**Goal:** Owner-managed employees with one role, editable six-section roles,
server-enforced access, and a shell-free monitoring screen with severity cards.
**Architecture:** Django Group/Permission-backed StaffRole + EmployeeProfile;
owner-only JSON CRUD. Next management routes, MUI DataGrid/dialogs. Existing
unmanaged employees keep current rights until assigned a role; owner protected.
**Spec:** ../specs/2026-11-08-staff-roles-design.md (approved user2026-11-08).

## Global constraints
- dev only; preserve current live local profile; no real employee/account creation,
  credential changes or paid calls during QA. No push/deploy.
- Only active superuser can manage employees/roles, never create/edit superuser.
- Exactly one role per managed employee; assignment replaces old groups/direct
  permissions (owner chose role scope), no auth user/group admin rights granted.
- Role capabilities limited to six application section bundles. Password validated
  and hashed, never returned/logged/audited. No Account/OTP/SMS created.
- Legacy unmanaged staff retain support/changelog rights; managed roles require
  explicit capability for each. All existing endpoint guards remain authoritative.
- Keep MUI/DataGrid Persian, no ID columns, page sizes10/25/50/100, server max100.

## Review focus
- Role/employee payload privilege injection and direct URL/API access must fail.
- Revision conflicts, owner protection, assigned-role deletion must fail safely.
- Inactive employees and revoked role changes take effect on next request.
- No password/cipher/private phone in audit/output; existing users not autochanged.
- Monitoring low/medium/high boundaries, native/mobile shell absence and route exit.

### Task1 Backend (isolated worker)
Files: core/models.py + migration; core/staff_roles.py (catalog/helpers/services),
core/staff_management.py (owner endpoints); config/urls.py; management_api.context;
support.staff_required; management_changelog guard; new test_staff_roles.py.

Models: StaffRole(name unique <=80, group OneToOne protected, sections JSON,
revision default0); StaffMembership(user OneToOne, role FK PROTECT, revision0).
Seed four default roles (support/finance/operations/admin) with no user assignment;
Group names unique private prefix, never collide with existing bootstrap_roles.
Synchronize role permissions from six bundles only. Existing custom permissions
already available; support uses view_supportconversation/add_supportmessage;
legacy unmanaged staff fallback remains. Changelog: legacy/owner or settings bundle.

API under /api/v1/manage/staff:
GET /catalog -> {sections:[{key,label,description}]} keys support,finance,operations,users,content,settings.
GET /roles?page=1&page_size=25&query=... -> {rows:[{id,name,sections,revision,member_count}],total,page,page_size}.
POST /roles {name,sections} -> role; PATCH /roles/<id> {name,sections,revision} ->role;
DELETE /roles/<id> {revision} ->{ok:true}, forbid assigned roles409.
GET /employees same pagination -> {rows:[{id,username,display_name,role:{id,name}|null,is_active,is_owner,revision}],total,page,page_size}.
POST /employees {username,display_name,password,role_id,is_active} -> employee;
PATCH /employees/<id> {display_name,role_id,is_active,revision,password?} ->employee.
No employee delete; owner rows read-only. Legacy row revision0; first assignment
creates membership with revision1. All payloads strict; UI password confirm local.
Audit IDs/sections/active flags only. Method CSRF, status401/403/404/409/422.
Context adds manage_staff owner only, support_chat conditional, view_changelog
conditional. Tests RED then GREEN, migrate consistency, report exact bundle mapping.

### Task2 Staff frontend (isolated worker)
Files: components/management-staff.tsx, lib/staff.ts, tests/staff.test.ts,
app/manage/staff/page.tsx, app/manage/staff/roles/page.tsx only. Consume above schema;
root owns console/frame/navigation. Props onFailure(error). Tabs routes /manage/staff
and /manage/staff/roles. Server DataGrid tables no IDs; name/status/role and compact
MUI row menu, page-size/count localization. Employee/role MUI dialogs; role editor
six checkboxes, employee only autocomplete role selector + password confirmation.
Autocomplete fetches paginated role search with abort; no unbounded role list.
No live save/delete/credential entry in browser QA. Errors Persian/revision conflict
reload; don't expose technical permissions. Test transport payload/form validators
where meaningful; root runs combined frontend checks.

### Task3 Monitoring refinements (isolated worker)
Files: management-monitoring.tsx, monitoring.ts, monitoring.test.ts,
NEW management-monitoring-layout.tsx. Root console selects this shell instead of
ManagementFrame on every monitoring route; no header/nav/footer regardless tv query.
Shell applies dir rtl, material marker, background/minHeight/padding only.
Monitoring own toolbar gets accessible return-to-management link (always) and keeps
refresh/interval; TV link may remain optional compact spacing but never restores
admin chrome. No frame edits by worker. Support0normal,1..9warning,>=10error;
queue age<120normal,120..599warning,>=600error. Pure helper tested exact boundaries,
color plus Persian severity text; new user card accent background/border/icon and
larger value (not alert). No API data/schema changes or fabricated metrics.

### Task4 Root integration and validation
- [x] Mark approved spec, record Unreleased; delegate3 independent tasks.
- [x] Wire context-based staff/support/changelog navigation and first authorized
  landing via router; stop support badge requests without capability.
- [x] Compose standalone monitoring shell without frame; preserve session/permission
  checks and private data cleanup. Add navigation/landing unit regressions.
- [x] Run scoped and full PostgreSQL tests once workers done; migrations --check.
  Run frontend tests/typecheck; independent security review, address findings.
- [x] Native owner staff/roles dialogs read-only and monitoring at1466/1920/375,
  no real employee or role mutations in product. Save screenshot proof.
- [x] Update API/operating docs, Persian catalog/changelog, sync next local MINOR
  version from latest0.27.0; scoped reviewed local commit only.

## Completion evidence and rulings

- Backend RED catalog404, scoped45 then18 staff tests passed; full703 PostgreSQL
  tests passed. The18 include actual row-lock races and every section API matrix.
- Opaque username search RED fixed (operator۱۲ stays exact); normalized human
  names still match. No schema drift: makemigrations --check --dry-run clean.
- Frontend116 tests and TypeScript passed. After catalog/copy edits,21 staff+
  changelog PostgreSQL tests passed again; no new runtime changes remained.
- Independent security review reported no material findings. Owner-onlyCRUD,
  group replacement, support/changelog boundaries, seed and revisions checked.
- Native migration0042 applied only to isolated local real-product database;
  it seeded4roles, changed no existing user, and no employee/credential mutation
  was submitted in browser QA. Employee dialog/remote roleoptions4 and roleeditor
  sixcheckboxes inspected/cancelled. Grids have no displayedID column.
- Native monitor normal1466x827 scrollHeight827,1920x1080 scrollHeight1080;
  mobile375 no horizontaloverflow. Management banner/nav/footer absent; shared
  public site-header remains hidden by existing Chrome behavior, not displayed.
- Captures local-only .local/staff-roles-desktop.png, staff-roles-mobile.png,
  staff-monitoring-desktop.png, staff-monitoring-tv.png and staff-monitoring-mobile.png.
- Ruling: compact desktop alert panel has bounded inner scrolling for long alerts,
  preserving all warnings without expanding the TV page. Mobile uses normal scroll.
- Ruling: legacy staff rights are preserved until explicit role assignment; new
  managed staff must have capability. Owner protected; staff active flag uses
  User.is_active (also impacts any pre-existing shared product login), documented.
- Local coherent MINOR0.28.0; no push, server deployment or paid/live message tests.
