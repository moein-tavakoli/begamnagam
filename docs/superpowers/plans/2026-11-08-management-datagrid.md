# Persian server-paginated management DataGrid

**Goal:** Use MUI X Community DataGrid for all existing management tables, with
Persian controls/counts, bounded server pagination and no displayed identifiers.

**Contract:** POST management records accepts page (1-based), page_size (1–100,
default25) or limit alias; conflicting aliases/invalid numbers return422. Apply
the same bound to generic records, account partial search and blacklist. The
UI offers10/25/50/100, resets to first page when query/status/size changes, and
uses server total. Keep IDs solely as internal keys/action targets. Do not
offer client-only sorting/filtering of a single server page. Existing activity
cards are not tables and keep their own pagination contract.

- [x] Backend worker: regression tests and validated dynamic slicing on all paths.
- [x] Root: DataGrid localization, identifier exclusion, stable controlled pages,
  loading/error states, counts, accessible cells/actions and mobile bounds.
- [x] Run relevant backend/frontend tests and TypeScript; independent review.
- [x] Verify native desktop/375px, rows-per-page, server page transitions,
  invisible IDs and row operations without live sends/account/payment changes.
- [x] Update docs/Persian catalog/version and commit locally. No push/deployment.

Validation: 663 PostgreSQL tests, 99 frontend tests, TypeScript; independent
review and authenticated native browser at 1280px and 375px. Mobile size selector
explicitly overrides MUI's default small-screen hiding. Captures are local-only
`.local/datagrid-desktop.png` and `.local/datagrid-mobile.png`. No live mutations,
paid provider calls, push or server deployment. Version 0.25.0 is local only.
