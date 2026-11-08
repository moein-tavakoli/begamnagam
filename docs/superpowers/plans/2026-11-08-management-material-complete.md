# Complete Material management workspace

**Goal:** Rebuild every `/manage` surface with MUI primitives and Material icons,
including mobile navigation, and verify original rejected AI input is inspectable
in authorized per-user history across website/API entry points.

**Design:** Keep existing handlers, auth, audit, CSRF, revisions, idempotency and
private-content permissions. Replace management-only visual primitives with
Typography, Stack, Grid, labeled TextField, Drawer, Breadcrumbs, Badge, Chip,
Material icons, menus and dialogs. Service balances mount only on overview.
Public product and Django advanced admin are separate surfaces. Staff support
gets a MUI renderer with the existing conversation state machine; public support
keeps its renderer. Never fabricate or dispatch a real test message.

**Tasks / ownership:**

- [x] Root: management shell/console, shared fields/theme/icons and overview balances.
- [x] Settings worker: all settings/catalog/payment forms with responsive MUI layout.
- [x] Support worker: staff inbox/thread MUI renderer without changing retry/read logic.
- [x] History worker: trace v2→preview→encrypted attempts→authorized text retrieval;
  add regression coverage and fix any missing persistence, preserving admission limits.
- [x] Integrate, run frontend tests/typecheck and relevant isolated backend tests.
- [x] Browser QA at desktop/375px: Drawer focus/Escape, breadcrumbs, every route,
  overview-only balances, labeled Persian numeric/date fields, thread draft retention,
  row menu geometry and history inspection. No account/payment/send mutations.
- [x] Independent final review; fix material issues, version/docs and local commit
  on dev. No push or deployment.


Validation ledger: 95 frontend tests; TypeScript; 28 isolated PostgreSQL tests.
Browser: all24desktop routes, 375px users/menu/dialogs/overview/settings/support;
correct RTL Drawer physical right edge and Escape focus; only overview balances;
57→57 row height; labels + Persian12→ASCII12; future date rejected; draft survives
cancelled discard and route round-trip. No SMS, paid AI or form mutations submitted.
Final independent review found field ID/label mismatch: actual browser regression
RED→GREEN after forwarding explicit IDs to TextField. No deferred findings.
PATCH0.23.2: compatible UI completion and regression coverage; local commit only.
