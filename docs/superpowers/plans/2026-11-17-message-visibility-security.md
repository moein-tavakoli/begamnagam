# Permanent website message visibility — implementation plan

**Goal:** Keep a message removed from the website inaccessible to ordinary users on later visits, without cancelling an authorized delivery or removing the staff record.

**Scope:** Website/PWA only, as clarified by the user. Bot checkpoint behavior is reviewed but explicitly excluded from changes. No deployment is authorized for this change.

**Design:** Keep the existing durable `Order.owner_hidden_at` tombstone and ownership filters. Deny attempts to reopen hidden orders through retries/submission/payment routes. Include an opaque, account-scoped visibility revision in website bootstrap responses; reset retained private browser state when it changes. Notify other tabs on deletion and revalidate when a page resumes. Keep public-only PWA caching, staff permissions/auditing, credit accounting and authorized queue processing intact.

**Alternatives:** Hard deletion loses administrative/financial evidence. A frontend-only filter permits stale views and API retries. The existing server tombstone plus browser invalidation fits the requested access-only change without a data migration.

- [x] Add failing regression tests for hidden-order retries, submission/payment routes, fresh sessions, retention, staff access and continuing queued delivery.
- [x] Add account-scoped bootstrap visibility revision and enforce hidden-order access checks at user entry points.
- [x] Add deletion notification, stale-read protection, and browser resume/revalidation behavior; test cross-tab and offline cases with isolated synthetic data.
- [x] Review authentication/authorization, browser/proxy/provider boundaries, dependencies and deployment security read-only; report confirmed findings and limits.
- [x] Run relevant full suites, migration consistency and configuration checks; obtain independent diff review.
- [x] Update API/privacy/operating docs and Persian release notes and synchronize patch version.
- [x] Commit only the reviewed task changes on dev.

**Limits:** Copies already delivered to a browser or SMS cannot be recalled. The tombstone must survive retention jobs and backup recovery. A restore predating deletions must not serve private data until newer deletion records are reconciled. Future changes require the regression suite; this review cannot certify future code or absolute security.
