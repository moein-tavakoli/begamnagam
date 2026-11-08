# Changelog

Codex chooses MAJOR.MINOR.PATCH for each completed, coherent change and creates
its local version commit on dev after relevant checks. Keep work in progress
under Unreleased; move only completed work into its versioned section before
committing. Local versions do not imply prod promotion or server deployment.
Push requires an explicit user request. See [versioning policy](docs/versioning.fa.md).
Historical release reports below contain deployment evidence and limitations.

## Unreleased

## 0.25.0 — 2026-11-08 — Persian management DataGrid pagination (local)

### Added

- Move every management records table to MUI X Community DataGrid with Persian
  controls, row ranges and total counts; offer 10/25/50/100 rows on desktop and
  mobile. Use server pagination and reset to the first page on search/status/size
  changes. Keep page-only sorting/filtering disabled in favor of server search.
- Accept optional integer `page_size` or `limit` on management records, default
  25 and bounded to 1–100. Reject invalid/conflicting sizes with 422. Apply sizes
  consistently to normal records and encrypted account/blacklist search while
  preserving permission checks, bounded retained rows and audit privacy.
- Exclude identifier columns from tables while preserving internal keys, user
  links and row action targets. Keep actions first in RTL, accessible cell focus
  and JSON value dialogs without increasing row height.

Validation: 663 PostgreSQL tests, 99 frontend tests, TypeScript and Persian
changelog parity passed. Independent review found no material issues. Native
browser checks cover desktop/375px, page transitions without duplicate rows,
size changes resetting pages, visible Persian mobile size controls, hidden
identifier columns, row menus and value-dialog focus. No live sends, account or
financial changes were submitted. Local version only; no push or deployment.

## 0.24.1 — 2026-11-08 — Simplify management navigation and show version (local)

### Fixed

- Remove the advanced Django management item from the shared desktop/mobile
  navigation. Show the build's canonical package version in the management
  footer using MUI Typography and the local Farsi-Digits font.
- Update the Persian release catalog and generated changelog for this version.

Validation: 96 frontend tests, TypeScript and Persian changelog parity passed.
Authenticated browser checks at 1280px and 375px confirm the removed navigation
item, package version 0.24.1 in the footer, Farsi-Digits font and no page overflow.
Local version only; no push or server deployment.

## 0.24.0 — 2026-11-08 — Private Persian release history (local)

### Added

- Add `/manage/changelog` with Persian summaries for all 61 recorded versions,
  Material cards, responsive layout and progressive reveal of older versions.
  Show local changes separately from historical records without inventing
  missing dates or asserting a server deployment.
- Serve the packaged catalog only through active-staff GET
  `/api/v1/manage/changelog`, with no-store and cookie variation. Deny anonymous,
  inactive and ordinary product users; do not embed notes in public client code
  or static assets.
- Generate `CHANGELOG.fa.md` from the same private catalog. A check command
  verifies exact Markdown parity, complete technical-changelog version coverage,
  unique ordering and the synchronized application version. Document ongoing
  Persian notes maintenance for future releases.

Validation: 15 related PostgreSQL tests, 96 frontend tests and TypeScript passed.
Catalog checks cover Persian text, version/date shape, ordering and uniqueness.
Independent review found no material issues. Anonymous native HTTPS access
returned 401; authenticated desktop/mobile UI checks and generator parity are
recorded with this local change. No push or server deployment.

## 0.23.2 — 2026-11-08 — Complete Material management workspace (local)

### Fixed

- Complete the `/manage` migration to MUI layouts, Typography, Grid/Stack,
  labeled TextFields, Material icons, Breadcrumbs, badges, buttons and menus.
  Replace the bespoke sidebar with an RTL permanent/temporary Drawer and keep
  card/table overflow bounded on mobile. Remove the old management layout CSS.
- Mount provider balances only on the authorized overview. Settings, catalogs,
  bank-proof dialogs and the complete staff support inbox/thread use Material
  components; public support retains its renderer and shared conversation logic.
  Preserve drafts across management routes, retry keys, read/poll behavior,
  permissions, CSRF, auditing, form names, digit normalization and constraints.
- Keep AI-rejected/unavailable inputs inspectable in per-user history. Verify
  existing encrypted capture across website, API v2 and bot-owned sessions with
  integration tests; no backend production behavior change was necessary.
  Legacy unstored text cannot be recovered; existing retention still applies.

Validation: 95 frontend tests, TypeScript and 28 related PostgreSQL tests passed.
Authenticated browser checks covered all 24 menu routes at desktop, representative
pages at 375px, overview-only balances, Drawer Escape/focus, row height 57px before
and after menu opening, native constraints/date rejection and support draft
retention across routes. Independent review found explicit-ID label association
broken in the new field adapters; browser regression failed before and passed
after forwarding IDs to TextField. No SMS/AI calls or account/payment changes
were submitted for QA. Local version only; no push or server deployment.

## 0.23.1 — 2026-11-08 — MUI management controls and Persian explanations (local)

### Fixed

- Replace expanding in-row actions with an anchored, portalled MUI Menu and
  IconButton. Use management-only MUI 9.5 components for navigation, cards,
  tables, controls, tabs and action dialogs, with App Router CSS collection,
  RTL styling and the local Farsi-Digits font. Public UI and Django admin retain
  their existing layouts.
- Explain stored moderation reasons, operational warnings, statuses, providers,
  categories, payment modes and audit actions in Persian. Preserve canonical
  API/database codes, identifiers, private content and sealed messages. Unknown
  machine codes get an honest Persian fallback; no invented cause is inferred.
- Preserve form names, numeric/date normalization and constraints, bank proof,
  permissions, CSRF, automatic auditing, busy guards and keyboard focus restore.

Validation: 93 frontend tests and TypeScript passed. Native authenticated browser
checks at desktop and 375px verified row height 65px before/after menu opening,
menu viewport bounds, Escape/focus, Persian reasons, canonical numeric input,
required bank fields and invalid future-date rejection without submitting changes.
Independent review found missing canonical wallet/audit translations; regression
tests failed before the fix and the complete frontend suite passed afterward.
No paid AI calls, OTP/message sends, account/payment mutations, push or deployment.

## 0.23.0 — 2026-11-08 — Active recipient blacklist (local)

### Added

- Add `/manage/blacklist` for active recipient opt-outs, including nonmembers.
  Require both staff account-view and recipient-state-view permissions; audit
  access without phone/search text. Never expose recipient hashes, cipher,
  sender identity or unsubscribe capabilities, and provide no unblock action.
- Resolve full phones from surviving encrypted accounts/orders/invitations;
  retain entries with an explicit unavailable label after source data deletion.
  Support full/partial Persian-digit phone search and bounded pagination.
  Opening the cancellation link alone remains distinct from confirmed opt-out.

Validation: 28 related PostgreSQL tests, 88 frontend tests, TypeScript, Django
checks, version/diff checks and independent review passed. Tests cover permissions,
nonmembers, cancellation/resumption, unavailable phones, partial search and page 2.
Authenticated local browser checks covered the blacklist empty state, full-phone
user table, Persian partial search, compact actions and invitation deep-link reload.
The local page loaded without a certificate warning; no warning was bypassed.
No paid AI calls, OTP/message sends, consent changes, push or server deployment;
local commit only.

## 0.22.0 — 2026-11-08 — Routed management users workspace (local)

### Added

- Add real management subroutes with a persistent shared shell, Users immediately
  after Overview, compact three-dot row actions and per-user messages/invitations.
  Preserve authorized legacy navigation for staff without account permission.
- Show full account phones only to authorized staff, audit disclosure and support
  Persian-digit partial search by scanning encrypted phones in memory. Keep search
  out of URLs/logs and retain only one page of 25 rows; scans remain linear in users.
- Record new authenticated message preparation outcomes in encrypted MessageAttempt
  history, including AI rejection/unavailability. Deduplicate orders/previews and
  moderation events. Quota/early-invalid requests cannot write private histories.
  Add scoped text review, 31-day redaction, account deletion cleanup and key rotation.
- Remove manual administrative reason prompts in Next/Django forms; keep automatic
  action/actor audits, permissions, CSRF, revisions and mandatory financial proof.

Validation: 645 PostgreSQL tests, 87 frontend tests, TypeScript, Django checks,
migration consistency and Compose configuration passed. Independent review findings
on quota admission and limited-staff navigation were fixed and covered. Native Next
route/compilation checks passed with the project CA; authenticated browser checks
were blocked by untrusted localhost TLS and no certificate warning was bypassed.
Old rejected drafts cannot be recovered if never stored. No provider calls, test SMS,
push or server deployment; local commit only.

## 0.21.1 — 2026-11-08 — Keep AI review classification-only (local)

### Fixed

- Stop sending generation/edit commands to the independent review step. Use
  dedicated tone classification criteria and an exact boolean JSON schema in
  both providers. Preserve meaning/register/safety gates and reject incomplete,
  malformed or generation-shaped reviews without a sendable preview.
- Add bounded schema diagnostics: known missing/nonboolean labels and unknown
  key counts only; never record response text, arbitrary keys or private input.

Validation: 126 related PostgreSQL tests and 82 frontend tests passed; independent
review found no important issues. A new regression test failed before the fix.
Within the explicitly authorized four paid calls, the deployed blunt pipeline
reproduced the invalid review shape and the corrected review canary returned all
seven required booleans with approval for a synthetic safe source/candidate.
All four calls were consumed; no SMS or order was created. This limited canary
is not an evaluation of every input. Local fix only; no push or deployment.

## 0.21.0 — 2026-11-08 — Blunt minimal-edit tone and firm default (local)

### Added

- Offer exactly three public choices: polite, firm (default) and blunt (`blunt`,
  رُک). Preserve already civil colloquial messages with minimal edits; require
  independent meaning, register and tone approval without relaxing moderation,
  consent, privacy or sender/recipient controls. Reviewed templates remain the
  only option when freeform is disabled; no unapproved raw-text dispatch.
- Enable the three requested choices with an audited configuration revision;
  preserve provider/budget settings, historical angry snapshots and guarded
  legacy API support. Set the web composer's initial/default tone to firm and
  expose the additive tone in REST/Swagger and bot schemas.

Validation: 113 related PostgreSQL tests, 82 frontend tests, TypeScript, Django
checks, migration consistency, Compose configuration and independent code review
passed. Isolated tone-component checks passed at 375px/1440px (three choices,
firm selected, blunt selectable, no overflow); authenticated live sending was not
retested. New tests cover defaults, public/legacy choices, safe unchanged text,
unsafe input/output, strict review and migration settings preservation. Provider
responses were controlled; no paid model or SMS calls. This local version does
not itself attest server deployment; release evidence is recorded separately.

## 0.20.2 — 2026-11-08 — Preserve colloquial intent and monthly login (local)

### Fixed

- Require minimal edits and preserve Persian colloquial/formal register, familiar
  address and concrete meaning in both AI providers. Treat ordinary forgiveness
  requests such as «حلالم کن داداش» as valid without inventing harmful context;
  reject unrelated good wishes, literary embellishment and unnecessary formality
  through a required independent register review. Keep all local content checks,
  preview consent and the existing two-call budget; no raw-text fallback.
- Give successful product OTP login a persistent, fixed 30-day session expiry,
  overriding inherited short/browser-close expiry. Reads and writes do not renew
  it; logout revokes it. Existing sessions retain their old deadline until the
  next successful login. Preserve OTP, five-minute recent-auth and private
  documentation's eight-hour lifetimes; update Swagger and integration guidance.

Validation: all 611 PostgreSQL backend tests, 81 frontend tests, TypeScript and
scoped diff checks passed. New tests cover colloquial/forgiveness/wish inputs,
strict independent review, meaning drift, reopening after 20 days, expiry after
30 days, inherited short expiry and logout. Provider responses are controlled;
real-model quality was not retested and no paid AI/OTP/SMS calls were made.
Independent code review found no important issues. Local commit only; no push
or server deployment.

## 0.20.1 — 2026-11-08 — Archive old unknown queue entries (local)

### Fixed

- Support audited archival of an old unknown outbox item from active queue
  metrics and automatic provider polling, preserving delivery uncertainty,
  historical records and balances. Never requeue or resend an archived item.
- Add a privileged, dry-run-first operational command with age/state guards and
  idempotent auditing. A late unknown provider response preserves the archive.

Validation: 30 related PostgreSQL tests and 81 frontend tests passed. Tests cover
history/balance preservation, queue
metrics, direct and scheduled polling, no resend, concurrent response handling,
rejection of recent/nonunknown records and dry-run/apply behavior. Migration
consistency and scoped diff checked. No account or production record changed
by local tests; deployment is separately authorized by the current request.

## 0.20.0 — 2026-11-08 — Per-account sponsored free sending (local)

### Added

- Add a separate, audited per-account unlimited free sending permission and UI.
  Preserve existing daily-count overrides and gift/package balances; sponsored
  failures never manufacture gift credits. No account is enabled by migration.
- Expose the flag in authenticated bootstrap and v2 credit summaries; retain
  finite balances and document bot behavior at zero credit. Update the profile,
  header and balance displays, clarify daily-cap labels and retain provider
  budgets, recipient controls and exact reviewed-message dispatch.

Validation: 252 related backend tests passed on isolated PostgreSQL/Redis,
including real-profile tests with mocked SMS, permission/audit, revocation,
retry and refund checks. Eight sponsored-send tests passed again after the
final balance/requote checks. Eighty-one frontend tests, TypeScript, migration
consistency and native Next browser checks at 375/1440 pixels passed. Browser
API responses were isolated fixtures; no real OTP/SMS/payment was requested.
Migration 0038 defaults existing accounts/orders to false. Local only: no push,
server deployment or actual account activation.

## 0.19.3 — 2026-11-03 — Official Enamad home badge (local)

### Fixed

- Replace the home page's Enamad placeholder with the supplied official embed
  verbatim. Permit its HTTPS image host in CSP and display the badge only on
  desktop, hiding it on mobile as requested, without changing the supplied
  link/image attributes.

Validation: 80 frontend tests and TypeScript passed. Native Next development
HTML and hydrated DOM preserve the exact supplied embed and all attributes.
Browser checks passed at 1440, 375, 320 and 812 pixels: desktop keyboard focus
and badge bounds, hidden mobile badge, and no horizontal overflow.
The external logo did not load from localhost, but a separate HTTPS request
with the registered domain as Referer returned a valid PNG (200). Actual seal
validation on the deployed domain remains unverified. No push or deployment.

## 0.19.2 — 2026-11-01 — OTP session diagnosis and n8n verification guidance (local)

### Fixed

- Describe the anonymous session cookie required by OTP verification in
  OpenAPI, independently of the verified-phone authentication requirement.
  Clarify that invalid_otp also covers a lost/replaced session or a consumed
  challenge; keep authentication checks and public error behavior unchanged.
- Explain the n8n verification endpoint/body, matching challenge/session across
  separate messenger executions, merging Set-Cookie by name, OTP versus session
  expiry and saving the rotated login cookies/CSRF. Correct the bot overview's
  v0.19.0 release status using the existing deployment evidence.
- Add HTTPS tests with explicit manual cookies: missing/replaced session fails
  while the original unexpired challenge succeeds; verify leading zeroes,
  cookie/CSRF rotation, authenticated getMe, replay rejection and actual expiry.

Validation: 116 API, bot, OTP and provider tests passed on isolated PostgreSQL
14.18 and Redis 8.10.2. The official OpenAPI 3.0 meta-schema, all 50 operations,
Django checks, scoped diff and synchronized version metadata passed. Read-only
production metadata showed a 300-second OTP policy and zero attempts on today's
13 challenges, consistent with (but not proof of) a session mismatch. The user's
n8n request was unavailable, so its exact cause remains unconfirmed. No real OTP
was requested; no workflow edit, production mutation, push or deployment occurred.

## 0.19.1 — 2026-11-01 — HTTPS client Origin and n8n guidance (local)

### Fixed

- Send the API Origin on mutations in the Python client. Django's HTTPS CSRF
  protection also checks Origin/Referer; correct cookies and CSRF alone returned
  403 from server-side clients. Keep strict origin validation and CSRF enabled.
- Document n8n's full-response body nesting, dynamic cookie/header expressions,
  local n8n usage and the no-SMS empty-body diagnostic. Add the Origin/Referer
  requirement to Swagger and clarify that the existing server accepts this
  client-side fix without a deployment. Record actual v0.19.0 deployment evidence
  in README while keeping this patch local.
- Close concurrency-test thread connections explicitly so the isolated
  PostgreSQL test database can be removed reliably with persistent connections.

Validation: 74 API/bot/client tests passed on isolated PostgreSQL 14.18 and
Redis 8.10.2, including HTTPS CSRF regression checks. A live HTTPS probe verified
nonempty 64-character JSON tokens from session/bootstrap, reproduced 403 without
Origin/Referer and passed CSRF with either valid header (422 for an intentionally
empty OTP body). The cookie secret also worked as CSRF. No real OTP was requested.
n8n HTTP Request 4.5 node configurations and cookie expressions, the official
OpenAPI meta-schema, Django/migration checks, version metadata and scoped diff
passed. No n8n workflow edit/execution, push or server deployment occurred.

## 0.19.0 — 2026-10-31 — Persistent Telegram/Bale conversations (local)

### Added

- Persist each platform/bot/user identity, private chat routing, OTP-verified
  Account link and encrypted session reference. Restore the same valid session
  after bot restart without retaining a local cookie file; issue fresh CSRF.
  Keep accounts/credits shared across platforms and sessions isolated. Expired
  or revoked authentication requires OTP; account changes clear the old draft.
- Add six bot operations to the private Swagger contract (50 total): discover
  scoped conversations with signed keyset pages, resolve/resume an identity,
  read it, replace/reset a stage and unlink its account. Record bounded,
  encrypted checkpoints with revision checks and deduplicated event ids.
  Return explicit instructions for expired OTP/previews and send reconciliation.
- Issue, rotate and disable scoped adapter credentials through the audited
  `manage_bot_integration` command. Store only secret digests; require the
  current adapter key on every bot-owned session request, including ordinary
  product calls. Preserve CSRF, verified-phone access and provider controls;
  bot cookies cannot access v1, admin or documentation routes.
- Extend the standard-library client with persistence APIs and private-update
  identity parsers for both platforms. Document provisioning, restart discovery,
  account verification, exact retry keys and UI receipt deduplication. Retain
  drafts for 24 hours, prune idle/deleted identities and sessions after 30 days,
  and include the four encrypted bot fields in hardened restore validation.

Validation: 583 backend tests passed on isolated native PostgreSQL 14.18 and
Redis 8.10.2, including 30 bot tests, concurrency races, new-process HTTP
recovery for both platforms, revoked/expired sessions, lost reservation responses
and single-credit/outbox assertions. The official OpenAPI 3.0 meta-schema and
all 50 operations' exercised response contracts passed. Eighty frontend tests,
TypeScript, Django/migration/Compose configuration checks and native Next browser
checks at 375px/1440px passed; private docs stayed protected with no external
requests. Docker daemon was unavailable; no Compose build or PostgreSQL 17/
Redis 7.4 container acceptance was claimed. No real provider calls, live bot
webhook activation, push or server deployment occurred. Local release only.

## 0.18.0 — 2026-10-31 — Scoped documentation handoff and server release

### Added

- Add `/api/v2/document/login` and a CSRF-protected logout for an active account
  holding only `core.view_api_documentation`. Staff privileges and a product
  Account are not needed; product, management and support access remain denied.
  Preserve existing authorized staff sessions. Anonymous Swagger entry leads
  to login; schema, guide and assets remain inaccessible without permission.
- Limit login attempts by address and username, fail closed if the limiter is
  unavailable, preserve opaque credentials, rotate CSRF at login and expire
  documentation sessions after eight hours. Permission removal or account
  deactivation revokes access. The global documentation switch stays off by default.
- Keep same-origin referrers on the two native documentation form pages so
  browsers can submit CSRF-protected forms; other private API responses retain
  no-referrer. Add mobile Persian login and explicit logout controls.
- Prepare the explicitly authorized dev-to-prod/server release, encrypted
  backup and restore checks, exact-image tests and a separate documentation
  credential handoff. [Release procedure](docs/release-v0.18.0.fa.md) and
  [actual deployment evidence](https://github.com/moein-tavakoli/begamnagam/releases/tag/v0.18.0).

Validation before promotion: 553 tests passed on isolated PostgreSQL 17 and
Redis 7.4, including 42 API/documentation/client tests. Eighty frontend tests,
TypeScript, Django/migration/Compose checks and native Next browser checks at
375px/1440px passed. Browser login uses an account without staff privileges,
renders all 44 operations, retains keyboard access and the Farsi-Digits font,
and makes no external schema requests. No real provider call was made.
Deployment completion and final image/CI/backup evidence are recorded separately;
this entry alone does not claim that the server release has finished.

## 0.17.0 — 2026-10-31 — REST integration API and private Swagger (local)

### Added

- Provide 44 documented operations under `/api/v2` for frontend and Telegram/
  Bale adapters: OTP/session, getMe, credit summary, catalog, destination
  normalization, sealed preview creation/retrieval, credit reservation,
  idempotent submission, receipts/history, packages, wallet/topups/ledgers,
  transfer receipts, invitations/rewards, receiving preferences, support,
  recipient capabilities/reports and account redaction requests. Preserve v1.
- Share the executable request/route definitions with an OpenAPI 3.0 contract;
  validate field types, query parameters, consent and idempotency keys before
  forwarding mutations to the existing product services. Keep per-user sessions,
  CSRF, phone verification, moderation, provider controls and recipient privacy.
- Add `/api/v2/document`, protected schema/guide/client/assets and an offline
  `export_api_schema` command. Documentation defaults off, requires active staff
  with `core.view_api_documentation`, and returns 404 otherwise. Migration 0036
  defines this permission without assigning it. Vendor integrity-verified,
  licensed Swagger UI assets; use no external CDN or schema validator.
- Include a Persian walkthrough and standard-library client with separate
  cookie jars, real-provider guards, explicit consent, stored retry keys and
  Telegram/Bale adapter guidance. Add the v2 Next.js proxy and verify that
  service workers do not intercept the API or its private documentation.

### Performance

- Bound history pages to 50 with signed cursors tied to the owner, resource and
  filter. Fetch receipt relations in four queries per page of messages funded
  by credit, instead of querying payments, refunds and delivery for each row.

Validation: 548 tests passed on isolated PostgreSQL 17 and Redis 7.4, including
37 new integration/documentation/client tests and existing concurrency checks;
80 frontend tests, TypeScript, migration consistency and Compose config passed.
The official OpenAPI meta-schema and all 44 operations' exercised responses
passed contract checks. Browser checks through native Next dev at 375px/1440px
passed: all operations rendered, local Farsi-Digits font, keyboard expansion,
no overflow, no console errors/external requests and anonymous docs denied.
No real OTP/SMS/payment/AI call, product-data mutation, bot webhook activation,
push or server deployment occurred. Local release only; messenger adapter
deployment and live Telegram/Bale acceptance remain separate work.

## 0.16.2 — 2026-10-30 — Evidence-backed iTools product introduction

### Documentation

- Deliver the Persian product copy and schema-valid iTools JSON with eight
  features, eight gallery entries, three signature sections, five workflow steps
  and eight FAQs. Document 21 capabilities, their implementation status and
  dependencies, including the boundaries of templates, optional AI, privacy,
  recipient controls and simulated versus real delivery/payment.
- Include 12 authentic, reviewed WebP screenshots from an explicitly authorized
  isolated 0.16.1 demo, the unchanged product icon, capture metadata, reproducible
  demo/QA scripts and a ZIP with SHA-256. Keep the homepage trust-placeholder
  screenshot and controlled freeform error outside the public image directory.

Validation: actual company draft-07 schema, exact JSON/readable-copy parity,
all image references/hashes/dimensions/budgets, source/icon integrity and ZIP CRC
passed. Two main journeys plus invitation reward, demo credit purchase and
private support were exercised. Twelve browser checks at 375px and 1600px passed;
six additional mobile captures use a 390px viewport. Temporary servers and the
synthetic database/keys were removed. No product behavior or company site was
changed, and no real OTP/SMS/payment/paid AI call, push or deployment occurred.
Capture source remains 0.16.1; this is a local documentation release only.

## 0.16.1 — 2026-10-30 — Consistent recipient phone entry

### Fixed

- Align recipient phone entry with login: centered label/digits, 19px text,
  numeric keyboard and an 11-digit ceiling. Share canonical digit handling and
  preserve full formatted/international paste and preview invalidation on edits.

Validation: 80 frontend tests and TypeScript passed. Isolated browser checks at
320px, 375px and 1440px in light/dark confirm matching login/recipient styling,
Persian/Arabic input, canonical ASCII preview payloads, native/state length
limits, incomplete-number rejection and clearing consent/preview when the
recipient changes. No real OTP, SMS or paid provider call was made. This update
is committed and pushed to dev at the user's request; server release remains
0.16.0.

## 0.16.0 — 2026-10-30 — Lightweight homepage entrances

The authorized server release includes all changes since 0.14.0, including
0.14.1, 0.15.0 and 0.15.1 below. Publication requires passing backend, frontend
and compose CI, a dev-to-prod merge PR, exact-image PostgreSQL tests, restored
migration rehearsal and HTTPS verification. This note alone does not attest
deployment success. [Release procedure](docs/release-v0.16.0.fa.md) ·
[Actual deployment evidence](https://github.com/moein-tavakoli/begamnagam/releases/tag/v0.16.0).

### Added

- Add staggered entrances for homepage utilities, two headline lines,
  descriptions, primary/help/invitation actions, trust slots, artwork controls,
  support, logout and version text. Replay on return to Home, honor reduced
  motion and keep focused actions immediately visible.
- Use finite compositor animations without new timers, animation libraries,
  permanent layer hints or text/button loops; release entry styles on completion.

### Changed

- Ignore decorative hero SVG mutations when positioning the support launcher,
  avoiding repeated geometry reads while the existing illustration loop runs.

Validation: 80 frontend tests and TypeScript passed. Browser checks cover
320px/375px mobile, 812px landscape and 1440px desktop, light/dark, stagger order,
finished animations, reduced motion, keyboard focus, theme switching, JavaScript
fallback, Home replay and draft preservation. No SMS/API mutation was used.
Local commit only; no push or deployment.

## 0.15.1 — 2026-10-30 — Centered phone entry (local)

### Changed

- Center the phone-entry form, label and digits; increase the input text from
  16px to 19px. Limit entry to 11 canonical digits with a numeric keyboard,
  preserving Persian/Arabic input and complete formatted/international paste.

Validation: 80 frontend tests and TypeScript passed. Browser checks at 320px,
375px and 1440px in light/dark themes confirm alignment, font size, the input
ceiling, normalized paste and no overflow. No OTP was sent; no push/deployment.

## 0.15.0 — 2026-10-30 — Login, compact receipts and update notices (local)

### Added

- Detect a newer application version through an uncached public version endpoint
  and show a small dismissible update notice. Preserve open OTP/drafts, require
  explicit reload, and retain the service-worker agreement across idle tabs.

### Fixed

- Complete OTP login with one fresh authenticated bootstrap before replacing
  private views. Abort stale bootstrap requests and suspend focus refreshes
  during verification, preserving SMS autofill and cross-tab privacy resets.
- Explicitly leave Compose when Home is selected and hide both navigation
  variants throughout the landing view.

### Changed

- Shorten login SMS to the application name and ASCII Code line, retaining the
  final public-domain WebOTP binding; remove the subtitle, timestamp and unused
  Jalali-date dependencies.
- Show credit and remaining gifts below the masked account phone in the header,
  remove the draft heading/balance row, and keep an accessible textarea label.
- Replace the final receipt details with a green verified icon, queue-admission
  confirmation and a single History action. Keep failed/uncertain/demo outcomes
  truthful, with operational details available in message history.

Validation: 511 PostgreSQL tests, 80 frontend tests, TypeScript and an isolated
production build passed. Browser checks cover autofill/session rotation,
focus/retry, cross-tab logout, landing navigation, compact receipts and safe
updates/offline behavior. No real SMS, payment or paid model call was made.
Local development only; no push or deployment.
[Verification details](docs/login-compose-refinement.fa.md).

## 0.14.1 — 2026-10-30 — Codex-managed versioning (local)

### Changed

- Delegate version selection, package-version synchronization, changelog entries
  and automatic local commits of completed changes to Codex. Require an explicit
  user request before pushing; retain dev/prod PR/CI and deployment boundaries.
- Define MAJOR for incompatible public changes, MINOR for compatible features
  and PATCH for fixes/documentation/maintenance. Keep unrelated pending work out
  of the commit and under Unreleased. Record the policy in AGENTS, README and
  the project master, with a shared operating procedure.
- Align package metadata with the recorded 0.14.0 baseline and bump this
  documentation-only change to 0.14.1; no dependency update is included.

Validation: reviewed the scoped diff, checked policy links and synchronized
version fields. This is a local documentation/version commit; no push, tag,
prod promotion, provider call or server deployment was performed.

## 0.14.0 — 2026-10-30

[Release verification](docs/release-v0.14.0.fa.md) ·
[Deployment evidence](https://github.com/moein-tavakoli/begamnagam/releases/tag/v0.14.0)

### Added

- Recreate the reference Paper Dart motion on the final confirmation button:
  continuous paper folds, shaded wings, a perspective turn, anticipation and
  accelerated takeoff with two trails. Wait for the real order outcome before
  showing registration feedback and the receipt; preserve retry idempotency,
  block concurrent submissions, support reduced motion and clean up on navigation.
- Show a small, Persian-digit version line below the application and mobile
  dock, respecting keyboard/safe-area space and marking native development runs.
- Animate the homepage theme control into view with a short, eased entrance,
  including on return from composition; respect reduced motion.
- Add an authenticated-only square logout action at the homepage's lower right,
  with an entrance animation, pending feedback and a recoverable failure state.
- Add editable message-example categories and prompts in both management UIs,
  with sorting, activation, moving/deleting, permission checks, audited changes
  and revision conflicts. Seed the existing 18 prompts into five categories;
  filter them in the composer without changing the draft or sending a message.
- Animate the homepage illustration with GSAP: sequenced entrances, banking
  envelope, floating/pulsing heart, springing/blinking character and offset
  cloud/star loops. Pause offscreen/in background, provide a pause control and
  respect reduced motion, with complete cleanup on navigation.
- Add a raised moon/sun theme toggle beside Profile on the homepage and the brand in
  the public header. Reveal either theme in a circle from the pressed button, persist
  device preference, follow the system until explicitly chosen, and synchronize
  tabs. Apply shared light/dark tokens to product cards, forms, OTP, messages,
  pricing and support; preserve keyboard focus and reduced-motion/API fallbacks.
  Initialize before paint under the existing CSP nonce and keep one dynamic
  browser theme-color through client navigation.
- Add a shared floating navigation for mobile and desktop, with subtly raised
  edges and application theme colors. A spring-driven crest stretches and leans
  with speed; after arrival a small droplet rises before the selected icon fills.
  Preserve real links, RTL layout, keyboard focus and immediate reduced-motion
  selection; keep the support launcher clear of the mobile dock.
- Display Persian digit glyphs throughout the product and both management UIs
  with self-hosted Vazirmatn Farsi-Digits, retaining canonical input/API/storage
  values, native number validation, copy actions and signed snapshots.
- Replace the OTP text field with four theme-aware slots, an orbiting
  verification state and a green collapse/check animation after server approval.
  Preserve native typing, digit selection, Persian-digit paste and SMS autofill;
  respect reduced motion and automatically verify a complete code through the API.

### Changed

- Make the final send button's registration success label bold and green,
  using the shared success color for light and dark themes.
- Use the shared brand-orange action styling for the Prepare text button.
- Render composition's phone/OTP forms directly inside the main panel, removing
  the nested authentication card while preserving autofill and automatic verification.
- Align the frontend package and lockfile version with the recorded 0.13.0
  release; keep subsequent local development work under Unreleased.
- Automatically verify a complete four-digit OTP from typing, paste or SMS
  autofill through the existing API. Guard concurrent requests and repeated
  automatic attempts after failures; retain explicit retry and server-approved
  success feedback. Blend the OTP stage into its parent and remove repeated
  authentication guidance.
- Keep mobile navigation visible during input focus and OTP, moving it above
  the keyboard alongside the composer actions. Add soft, theme-aware gradient
  edges beneath overlaid example-category arrows.
- Place the homepage support action inside the hero frame, aligned with Logout,
  and remove the short eyebrow above the hero headline.
- Remove the visible composer step strip, reduce category-arrow visuals while
  preserving their touch targets, and use a red homepage logout action.
- Preserve navigation instances across the homepage/compose boundary and retain
  in-flight crest motion through remeasurement, so Compose receives the full
  spring, rising-droplet and icon-fill sequence.
- Move the public navigation theme toggle beside the header brand and show the
  masked signed-in number in place of the redundant history shortcut. Remove
  repeated verified-phone banners and the history/wallet introduction copy.
- Show crest navigation during composition, including the active Compose link;
  keep the fixed action row above the mobile dock and use a conventional home icon.
- Make example-category filters a swipeable, snapping row with visible arrows,
  move the tone caption inline before its choices, and use the brand orange for
  the draft's Next button. Preserve drafts while changing filters.
- Label customer-facing payment methods consistently as a bank gateway.
- Use a shared 16px button radius across primary/secondary actions, profile,
  theme, support, sample filters/cards and management controls.
- Remove the homepage's bottom dot/bar pagination indicator.
- Simplify the draft composer: remove the repeated visible textarea label,
  place privacy guidance directly below the field as helper text, and show all
  active example cards immediately. Remove the disclosure/more controls while
  retaining an accessible field name, helper/error associations and character count.
- Canonicalize digits in new human-entered JSON and admin form data before
  validation, hashing and persistence, with an independent server check. Keep
  credentials, opaque identifiers and signed capabilities exact. Normalize the
  outgoing frontend payload without mutating its displayed form state.
- Accept Persian/Arabic digits in amount, limit, package and date editors in
  both management UIs; retain required, range, step and date validation through
  the browser's native numeric/date validator. Keep the shared Persian glyph font.
- Change login OTPs to four cryptographically random ASCII digits, preserving
  leading zeros across generation, verification, provider submission, WebOTP
  and the animated input. Use a fixed BegamNagam/Code SMS layout with a Jalali
  timestamp in Tehran time and the final public-domain autofill binding.
  Keep session binding, attempt limits, expiry, single use and provider cost
  controls; reject longer codes without truncation.
- Establish `dev` as the default development branch and `prod` as the release
  branch, preserving all history from `0321acf`; remove `codex/product-mvp` after
  verifying both replacements on GitHub.
- Run CI for `dev`/`prod` pushes and pull requests. Require a pull request and
  successful backend, frontend and Compose checks before merging into `prod`.
- Keep the manually dispatched local demo on `dev`. Server deployment still
  requires an explicit request for each release.
- Document the branch/release workflow and restore the missing release summaries
  through 0.13.0 in this changelog.

### Fixed
- Keep the mobile dock hidden throughout OTP entry so it cannot appear under
  the confirmation button between pointer down and pointer up after input blur.
- Match OTP surfaces, digits and feedback to the application theme. Trace an
  ease-in-out line around the focused slot alongside the restored theme-aware glow.
- Restore the existing local real-OTP runtime after Docker Desktop stopped;
  document data-service recovery without rebuilding the UI or replacing data.
- Let the initiating OTP form finish bounded feedback before its local session
  reset; notify other tabs immediately and keep failed verification retryable.
- Align the automated demo smoke check with gift/package credit pricing instead
  of requiring the removed per-message price to be positive.

## 0.13.0 — Pricing, support and account controls

- Add reviewed alternatives after message rejection and per-account send/rewrite
  limits while preserving moderation and exact-preview authorization.
- Add the public pricing page, four message packages and documented bank-transfer
  approval; keep paid checkout disabled and gateway credit subject to verification.
- Add private text support, the shared admin inbox and provider balance visibility.
- Add referenceable product/help content, structured data and crawler policies.
- [Release report and validation](docs/release-v0.13.0.fa.md).

## 0.12.2 — OTP completion and rewrite handling

- Accept zero in configurable hourly limits and spacing controls.
- Improve friendly-message rewriting and distinguish meaning changes from content
  rejection; preserve independent review and final dispatch checks.
- Add domain-bound OTP/WebOTP support and contain optional browser feature errors.
- [Deployment evidence and limitations](docs/deployments/ct115-0.12.2.json).

## 0.12.1 — Public links and bounded rewriting

- Add `/links`, simplify composer wording and show rewrite progress.
- Use `gpt-4.1-mini` with a shared 20-second deadline and ten daily rewrites per
  account; retain configurable site quotas and the authorized unlimited site mode.
- Add the homepage Enamad verification tag.
- [Release evidence](docs/deployments/ct115-0.12.1.json) and
  [Enamad verification](docs/deployments/ct115-0.12.1-enamad.json).

## 0.12.0 — Message packages and live GapGPT rewriting

- Replace fresh single-message purchases with package credits and retain legacy
  obligations, transactional reservations and idempotent credit/refund handling.
- Enable the authorized synchronous GapGPT rewrite/review flow with quotas and
  sealed previews. Keep paid checkout disabled and real OTP/gifts unchanged.
- Add provider selection; keep the evaluated, unapproved Ollama models disabled.
- [Release report and validation](docs/release-v0.12.0/README.fa.md).

## 0.11.2 — Six frontend replicas

- Distribute rendering across six identical frontend replicas and preserve the
  database, queues and backend images; tune the central proxy connection reuse.
- [Capacity report and measurement limits](docs/release-v0.11.2-capacity/README.fa.md).

## 0.11.1 — Capacity configuration

- Add a separate capacity profile with three frontend replicas, bounded process
  memory and backend concurrency, preserving data services and provider settings.
- [Configuration and rollback](docs/release-v0.11.1-capacity/README.fa.md).

## 0.11.0 — Security hardening

- Separate runtime/migration credentials, restrict PostgreSQL/Redis/RabbitMQ access
  and encrypt order/preview bodies at rest.
- Add admin login throttling, security headers and private-response protections.
- Harden the authorized server access and introduce encrypted scheduled backups
  with restore rehearsals; preserve real OTP/gifts and closed paid checkout.
- [Security release and remaining limitations](docs/release-v0.11.0/README.fa.md).

## 0.10.2 — Compact composer and inline terms

- Remove the visible composer toolbar and the selected OTP/rewrite/recipient hints.
- Keep a smaller outlined previous button beside the primary action in a fixed
  bottom row, with safe-area and keyboard viewport clearance.
- Place step numbers beside their labels and the compact gift balance beside the
  draft heading. Open the shared privacy/terms text in an accessible dialog.
- Deploy frontend0.10.2 with31 tests, TypeScript/build and36 HTTPS checks passing;
  retain backend0.10.1, all seven other containers, real sending and79 old assets.

## 0.10.1 — Remove the live gift daily provider cost cap

- Honor the user's explicit request with an opt-in unlimited daily cost mode for
  live gifts, retaining cost accounting, per-call anomaly checks and idempotency.
- Preserve gifts, closed paid checkout, recipient controls and historical orders.
- Record specific bounded pre-provider policy reasons for operators while keeping
  provider credit and system details out of public receipts.
- Deploy backend0.10.1 with263 PostgreSQL tests and35 HTTPS checks passing;
  reuse frontend0.10.0 and all data services, preserve gift balances and ledger.

## 0.10.0 — Prepared GapGPT freeform rewriting

- Make examples optional; custom drafts keep their own intent.
- Locally filter input, generate/review with bounded GapGPT calls, validate the
  output and bind its encrypted snapshot to owner/recipient/price/terms/expiry.
- Enforce durable rewrite quotas and validate the exact confirmed SMS in workers.
- Keep API key/model blank, quotas zero and live template mode as requested.

## 0.9.0 — Phone invitations and signup rewards

- Add a private invitation panel: unique phone claims, membership/self checks,
  three requests per target, 24h cooldown, five requests per sender/day.
- Send only reviewed invitation snapshots with an opt-out capability; durable
  outbox, gross shared budget and query-only uncertain outcomes preserve safety.
- Award the inviter three credits exactly once after first verified signup.
  Invitees retain their three initial gifts; existing balances are preserved.
- Add registration/delivery history, reward status, consent, encryption, retention,
  migrations0013–0014 and authenticated invitation-only membership disclosure.

## 0.8.18 — Recipient SMS introduction

- Start fresh recipient SMS previews with the exact Persian introduction and a
  newline, followed by the reviewed body and the existing opt-out footer.
- Keep the three-segment ceiling by using a fitting complete reviewed alternative
  from the same topic/tone when needed. Never truncate text or rewrite old quotes.
- Preserve the exact confirmed provider payload, retry idempotency and fixed OTP.
- Preserve line breaks in preview/history. Deploy0.8.18 with175 PostgreSQL and26
  frontend tests, typecheck, release build and33 HTTPS route checks passing.

## 0.8.17 — Explain delivery restrictions and cancellations

- Add public status reasons to receipts and history, including account restrictions,
  moderation, order/queue expiry, sending hours and uncertain outcomes.
- Explain sender daily/pair limits and self-recipient validation at request time;
  keep receiver opt-out, cooldown and busy states indistinguishable.
- Preserve internal operator codes while hiding provider credit and system details
  from public status reasons, HTTP5xx messages and unknown client exceptions.
- Keep delivery authorization, refunds, gift balances, budgets and retry behavior.
- Deploy0.8.17 with171 PostgreSQL and26 frontend tests passing; typecheck,
  release build and33 HTTPS route/asset checks pass. Verify receipt/history
  explanations at375px/1440px with synthetic responses; preserve all data services.

## 0.8.16 — Plain SMS links and eighteen reviewed topics

- Use `begamnagam.ir/r/Ab12Cd34` in fresh SMS previews, keeping eight random
  alphanumeric characters and compatibility with existing fragment links.
- Redirect GET/HEAD to the existing recipient screen without lookup or mutation;
  apply no-store/no-referrer/noindex headers. Require private-path log protection
  at every proxy before enabling the new format in production.
- Add eleven topics with reviewed gentle/direct templates; retain moderation,
  three-segment limits and frozen old snapshots. Expand extra topics with an
  accessible disclosure, retaining a selected extra topic when collapsed.
- Deploy0.8.16 with all18 topics enabled on the authorized live site. Protect
  HTTP/HTTPS recipient paths from Nginx access/error logs, preserve the exact
  legacy /r route, and verify private paths are absent while public logging works.
- 163 PostgreSQL tests,25 frontend tests,12 local contract scenarios and33
  HTTPS route/asset checks pass. Preserve gift balances and spending limits;
  no real SMS, payment, database migration or Git push during this release.

## 0.8.15 — Real gift SMS, paid checkout closed

- Add an explicit live gift SMS profile behind the existing trusted HTTPS proxies;
  keep local demo defaults and the full paid-provider approval requirements.
- Allow real delivery to all valid recipients, retain moderation, opt-outs,
  idempotency and bounded spend. Reject stale demo consent and quotes.
- Close paid order creation, demo payment and gateway access in live gift mode.
- Restore demo-only gift balances once while halted, with an operator audit;
  never replay old messages. Update live UI, help and SEO copy.
- 160 PostgreSQL and24 frontend tests pass; HTTPS/SEO/CSRF routing checks pass.
  Deployed0.8.15. After the user enabled link permission, a fresh authorized
  real probe received a delivered receipt at6906 rial. Order dispatch resumed;
  OTP remains real, three gifts are preserved and paid checkout stays closed.
- Track a provider configuration discrepancy: resendfailed updates return disabled
  but an independent GET still reports enabled. Record an operator warning for
  console follow-up; app-level idempotency and spend limits remain enforced.

## 0.8.14 — Login OTP for every valid phone number

- Remove the login recipient allowlist from both the API and Kavenegar adapter;
  authentication no longer depends on outgoing-message pilot membership.
- Remove obsolete OTP_TEST_RECIPIENT_HASHES configuration. Keep explicit real-OTP
  activation, fixed text, per-phone/session limits, CSRF, expiry and spend ceilings.
- Keep payments and order messages simulated in the deployed demo.
-153 PostgreSQL tests pass. Deployed backend/worker/beat0.8.14 to the CT;
  two new-number logins passed with mocked SMS and rolled-back diagnostic data.
  HTTPS routing/CSRF checks pass; data/frontend containers remain unchanged.

## 0.8.13 — Short SMS opt-out links

- Print the SMS URL without its scheme and issue unique random eight-character
  alphanumeric fragment codes; preserve existing43-character links and snapshots.
- Retry collisions transactionally and fail closed; reserve expired delivered
  code digests after clearing recipient links to prevent reassignment.
- Add a per-IP recipient-action limit alongside session/token limits and CSRF.
- HTTPS settings and frontend stay unchanged; no new migration or provider activation.
-151 PostgreSQL tests pass, including collision rollback, expiry, legacy links
  and per-IP guessing limits.

## 0.8.12 — Per-account test sending and respectful direct tone

- Add independently permissioned, audited account checkboxes for unlimited demo
  sends and a clearer respectful outgoing tone; both default off.
- Demo exemption skips sender quotas and cooldowns without changing history,
  opt-outs, active reservations, OTP, free credits, spend or live-provider gates.
- Select direct reviewed templates per sender; model selection stays constrained,
  moderation runs before/after and workers validate either reviewed pool.
- Existing previews keep their approved text when account options change.
-145 PostgreSQL tests and a live CT admin/queue acceptance check pass; six
  synthetic deliveries preserve three free credits and use no real SMS/payment.

## 0.8.11 — Traefik and explicit domain routing

- Replace the CT proxy with Traefik3.7.13; keep public TLS on central Nginx,
  explicit domain/IP routes, secure cookies, CSRF and narrow proxy trust.
- Preserve the private CA; rotate a30-day IP leaf with a daily renewal timer,
  without exposing the CA key to Traefik. Data/frontend containers stay unchanged.
-134 PostgreSQL tests pass. Both HTTPS paths pass33 route/auth/asset checks;
  synthetic queue/free-credit/opt-out journey passes with no real SMS/payment.
- Ordinary public-domain access is refused from this network; browser acceptance
  and www certificate coverage remain open. See the Persian deployment report.
- Local commit only; this task performs no Git push.

## 0.8.10 — Internal CT deployment

- Deployed the private demo on192.168.1.123 with Caddy internal HTTPS, secure
  cookies, explicit CSRF origin, production Next.js and persistent data volumes.
- Kept real OTP limited to the previously authorized allowlist/budget; only an
  explicit RFC1918 HTTPS origin extends loopback testing. Payment/order SMS stay demo.
- Added a separate internal settings/Compose profile. The CT's nested network
  restriction uses host networking with every data/API/metrics listener bound to
  loopback; only Caddy serves LAN ports80/443. No privileged container or old runtime.
- Verified signed Docker packages, built/transferred Linux/amd64 images, and enabled
  restart policies. Build caches support unreliable package downloads without pin changes.
-130 PostgreSQL backend tests and14 frontend tests/typecheck pass. Live CT checks
  cover TLS, secure cookies, CSRF, admin login/test tools, manifest/worker/offline
  assets and synthetic free delivery through RabbitMQ/Celery. No real SMS or payment
  was submitted. Client CA trust and physical-device PWA acceptance remain manual.

## 0.8.9 — Three free sends per verified account

- Grant each existing/new verified phone account3 one-time free sends. Reserve a
  credit transactionally when creating a free order; previews do not spend credits.
- Free checkout queues delivery without a payment intent, capture, financial event
  or gateway redirect. Positive-money constraints remain unchanged.
- Stale free quotes require a fresh review rather than silently charging. Retry
  and concurrent requests cannot double-spend. Expiry/definite failure returns a
  credit once; uncertain delivery retains its reservation.
- Show remaining credits, free price, confirmation and receipt/history labels.
  Daily quotas, moderation, OTP, provider budgets and demo boundaries still apply.
-124 backend tests pass on PostgreSQL, followed by14 focused free-credit tests
  including3 additional failure/constraint cases.14 frontend tests/typecheck pass.
  Isolated HTTP smoke covers free confirmation and balance without live providers.
  Mobile375px and desktop1440px UI checks used mocked checkout responses, preserving
  the user's3 credits. Migration0010 applied locally; Fast Refresh stayed running.

## 0.8.8 — Daily sending limits and admin test reset

- Both sender/recipient and global recipient cooldowns now default to24 hours;
  senders may create up to5 orders in a rolling24-hour window.
- Added an admin-only, permission-checked, CSRF-protected test reset with audit
  records. It restarts simulated quota windows without modifying order history.
- Test resets are opt-in and ignored outside isolated demo delivery/payment.
  Opt-outs, suspension, self-send checks, open reservations, OTP and spend stay intact.
-113 PostgreSQL backend tests and14 frontend tests pass; typecheck, migration
  consistency and Compose configuration pass. Native backend processes reloaded;
  Fast Refresh frontend stayed running. No external send/payment or image build.

## 0.8.7 — Simplified final review

- Removed the separate demo payment/delivery explanation box from final review.
- Kept the demo send-button label and receipt disclosure; provider modes are unchanged.

## 0.8.6 — Recipient within final review and inline writing guidance

- Removed the draft rewrite-mode strip and the redundant recipient-stage teaser.
- Moved privacy/respect tips into an inline warning beneath the textarea while
  keeping the character counter at its existing edge and accessible descriptions.
- Combined recipient entry with final review on one screen. Preparing a preview
  stays on that screen; changing the number clears the old preview and consent.
- Keep authentication, reviewed recipient/text/price, consent and same-order payment
  retry protections. UI changes use the existing Fast Refresh server only.
-14 frontend tests/typecheck pass. Mobile/desktop browser checks cover same-screen
  preview, invalid/changed recipients, renewed consent, order locking and a mocked receipt.

## 0.8.5 — Combined final review and numeric inputs

- Removed the sender verification badge from the recipient form; authentication stays required.
- Convert Persian/Arabic digits to Latin as phone/OTP fields change, preserving leading
  zeroes and normalized payloads across composer, login and reverification routes.
- Combined final text, frozen recipient, cost, consent and sending into the third step;
  removed the separate confirmation/payment screen and continue to the receipt.
- A failed payment retries the same order. Browser failure injection verified one order,
  two attempts on the same payment path, one demo capture/outbox and simulated delivery.
-14 frontend tests/typecheck pass; mobile375×812/375×667 and desktop1440×900 reviewed
  using hot reload. Evidence screenshots use synthetic data without live capabilities.

## 0.8.4 — Native OTP TLS failure and diagnostics

- Configured the private native Python runtime to use the system CA bundle;
  certificate and hostname verification remain enabled. Public no-key probe succeeds.
- Distinguish pre-submission certificate/DNS/connect failures from ambiguous timeouts:
  definite failure returns503, unknown keeps its challenge without automatic resend.
- Added safe OTP diagnostics and explicit accepted/unknown response/UI status;
  failed provider delivery status cannot claim acceptance.
- Fixed HTTP test doubles to model the response object actually read by urllib;
  regression cases cover TLS privacy, DNS, timeout and failed provider status.
-99 backend tests and13 frontend tests/typecheck pass. A single authorized real
  OTP was accepted by Kavenegar; the user completed code verification in the browser.
- Payment/order delivery remain demo. Native services restarted; no image build or push.

## 0.8.3 — Isolated real OTP testing in the local demo

- Added explicit local OTP authorization with a keyed test-number allowlist,
  positive per-code/daily budgets and fixed official Kavenegar HTTPS routing.
- Keep general provider networking disabled, order SMS simulated and payments demo;
  reject configurations that broaden this exception to other providers or origins.
- Publish `otp_is_real` in bootstrap/health and clarify login/payment UI labels;
  real OTP never exposes a debug code. Smoke refuses live OTP before requesting a code.
-96 backend tests and13 frontend tests/typecheck pass, including CSRF, allowlist,
  budget exhaustion, expiry/replay, network scope and a full simulated checkout.
- Private one-number test configuration activated under explicit user instruction;
  phone receipt remains for user testing. No image rebuild, public deployment or push.

## 0.8.2 — Ordinary SMS for OTP

- Default Kavenegar OTP to ordinary `sms/send` using the configured sender and
  fixed six-digit login text; no approved template is needed in `sms` mode.
- Keep opt-in `lookup` mode for a future approved template; reject invalid modes,
  missing lookup templates and non-code OTP input without dispatching.
- Expose `KAVENEGAR_OTP_MODE=sms` in environment templates and backend Compose wiring.
- Preserve OTP privacy, expiry, throttling, budget and network activation gates.
- All90 backend tests pass on PostgreSQL/Redis, including ordinary OTP login,
  lookup opt-in, invalid input/configuration, rejection and a lost send response.
- Compose configuration validates; no live SMS, UI image builds or Git push.

## 0.8.1 — Kavenegar environment configuration

- Exposed existing Kavenegar OTP/SMS/status credentials in the root environment
  template and shared backend/worker Compose environment, with release placeholders.
- Documented API key, sender line and OTP template setup; credentials stay server-side.
- Demo and disabled provider-network defaults remain in effect; no vendor calls.
- All42 provider/API tests pass on PostgreSQL and Redis; synthetic Compose checks
  confirm credentials reach backend services only and the private env stays ignored.

## 0.8.0 — Full-screen mobile onboarding and composer

- Replaced the scrolling home page with intro/composer slides and explicit Next/Back controls.
- Removed the top environment banner, home header and promise strip; hid the mobile footer.
- Split composing into viewport-sized writing, recipient, preview and confirmation screens.
- Topic selection now inserts its example directly into the editable message field.
- Verified six portrait sizes, seven topics, draft preservation, validation and a complete
  demo checkout in the browser;13 frontend tests/typecheck pass. UI uses hot reload only.

## 0.7.0 — Local release candidate and evidence

- Measured1000 synthetic accounts,30 complete flows and2400 successful reads across
  a15-minute baseline and60-second burst; fixed source hash and actual runtime versions recorded.
- Exercised multi-tab PWA update safety, anonymous offline fallback, encrypted restore
  preserving a post-snapshot stop, and recovery from an intentionally failed frontend candidate.
- Added isolated HTTPS release topology, strict proxy settings, aggregate readiness audit,
  required human-evidence checklist and current56-requirement traceability.
- 86 backend/13 frontend tests pass; clean Compose/RabbitMQ4.4, builds and checks verified.
- Human/device/vendor acceptance and public deployment remain pending; no push or live spend.

## 0.6.0 — Synthetic pilot and final dispatch safeguards

- Twelve app/HTTP-provider rehearsal scenarios pass for all seven topics, independent
  payment verification, duplicate callbacks, anonymous reports and a stop-before-send refund.
- Frozen terms consent is recorded on each order; external use requires a reviewed version.
- Redis loss pauses dispatch, expired unsent paid orders refund, and the final wire-call
  check respects sender suspension, recipient stop, sending hours and the global halt.
- Amount/currency mismatches remain unresolved for reconciliation; no false failure/refund claim.
- 83 backend tests pass; volunteer/device testing is explicitly deferred.

## 0.5.0 — Recipient safety and operations

- Activated256-bit fragment capabilities for account-free stop/report; GET is inert,
  CSRF is required, reports deduplicate and expose no party identity.
- Capability snapshots/report details encrypted at rest; additive data migration,
  recent OTP for reactivation/deletion, key rotation and bounded retention/holds.
- Audited, permission-scoped halt/resume/suspend/triage/manual-refund actions and
  aggregate alerts; observed provider cost overages stop further spending.
- Sending-hour/positive-pilot gates, cross-tab logout/account reset and all-tab
  idle acknowledgements before a PWA update can activate.
- Encrypted backup and non-destructive restore rehearsal with latest privacy overlays,
  finance validation and query-only recovery; restored dispatch stays halted.
-79 backend/13 frontend tests pass; human evaluation stays deferred.

## 0.4.0 — Provider protocols and reconciliation

- Bounded Kavenegar OTP/SMS/status and Zarinpal request/verify/inquiry/reverse clients,
  with redirect/host checks, integer toman-to-rial conversion and disabled network by default.
- Durable payment/submission intents, independent verification, late/extra-receipt
  refunds and query-only recovery after ambiguous requests or worker loss.
- Gross daily provider budget reservations and pilot recipient allowlist gates.
- Real HTTP loopback contract simulator and15 integration tests; no vendor calls.
- Post-settlement refunds stay tracked as manual obligations; no false refund result.

## 0.3.2 — UI hot reload workflow

- `make dev-ui` runs the native Next.js development server with Fast Refresh on
  loopback, using the existing backend without building Docker images.
- Generated `next-env.d.ts` is ignored; typecheck generates route types without
  a production build, so fresh checkouts and dev/release switching stay clean.
- Contributor and operating guides require hot reload for UI edit loops; package
  installation and production/PWA image validation are separate steps.

## 0.3.1 — Infrastructure and moderation verification

- A fixed 120-case synthetic Persian/English corpus covers normal topics, prompt
  injection, contact details and obfuscated abuse; Arabic tatweel bypass is fixed.
- Fully resolved backend dependency lock is used by Docker and CI.
- Celery event/control queues use exclusive connections for RabbitMQ4.4; durable
  task messages keep late acknowledgement and worker-loss redelivery.
- Current phase index now follows the approved proposal numbering.
- Full Compose image build succeeds with an optional verified wheel cache.
- Fresh isolated PostgreSQL17/Redis7.4/RabbitMQ4.4 environment passes readiness,
  demo smoke and all 46 backend tests (no skips).
- Actual broker/worker/beat outage preserves the paid outbox and recovers the same
  order; database inspection confirms one capture and one delivery attempt.
- No changes to real-provider activation or push authorization.

## 0.3.0 — Phase-two local demo and PWA

- Final message preview includes service identity, opt-out URL, segment count and frozen recipient.
- Checkout creates independent verified demo payment, capture event, queued delivery and outbox atomically.
- Delivery completion/suppression updates its independent state; terminal failure records one compensating demo refund.
- Recipient cooldown starts on successful simulation; sender/recipient pair also has a 30-day limit enforced with database locks.
- Existing paid demo orders are backfilled into the financial/delivery schema.
- Install UI for supported browsers and iOS Home Screen guidance; explicit safe update with dirty-form/checkout protection.
- Logout and bfcache return clear in-memory private UI; no background replay or private persistent cache.
- Optional official verified Linux wheel cache for restricted/slow Docker networks; no dependency downgrade.
- No live SMS, payment, cloud deployment or Git push.

## 0.2.0 — Foundation snapshot

Phase-zero deliverables, local foundation, mobile-first playful visual direction,
manifest/icons, anonymous offline fallback and separate financial/delivery schemas.
The repository had no commits; this complete existing snapshot was recorded as
local commit 4a327a1 before phase-two changes.
