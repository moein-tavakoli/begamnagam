# Management MUI and Persian explanations

> Implementation: execute locally on dev; review the final diff independently.

**Goal:** Use MUI for the management interface and explain stored machine codes
in clear Persian without changing historical data, API values or message text.

**Design:** A management-only RTL MUI theme uses the existing local Farsi-Digits
font and product colors. MUI controls, cards, tables, navigation and dialogs
replace the management primitives. The row IconButton opens a portalled Menu,
so opening it cannot increase row height. Keyboard close/focus and mobile bounds
must work. Authentication, permission filtering, CSRF, audit and proof requirements
stay in the existing handlers. Django advanced admin remains its own interface.

**Plan:**

- [x] Add behavioral tests for Persian reasons, unknown-code fallback and field
  boundaries. Reproduce the existing row-height problem in the native dev UI.
- [x] Install pinned compatible MUI/Emotion packages. Add Next App Router CSS
  collection, RTL theme and management UI primitives scoped to `/manage`.
- [x] Migrate management shell, record table/actions, settings controls and
  dialogs; retain numeric normalization and native constraint validation.
- [x] Display Persian reasons/statuses/categories/provider modes and known
  operational warnings. Unknown machine codes get a Persian fallback; IDs,
  credentials, private text and sealed snapshots are not translated.
- [x] Run frontend tests/typecheck, native dev browser checks at desktop and
  375px; check menu row height, keyboard/focus, routing and dialog form fields.
  Do not send SMS, invoke paid AI or mutate financial/account state for QA.
- [x] Review independently; fix material findings, update docs/version metadata
  and commit only this change locally. Do not push or deploy.


Validation ledger: 93 frontend tests and TypeScript passed; browser measurements
confirmed menu row height 65→65 at desktop and 375px, viewport containment,
Escape/menu and dialog focus restoration, Persian reasons, canonical۱۲→12,
required bank-proof fields and rejection of a future paid_date. No forms submitted.
Final independent review: two important omissions in current wallet/audit/payment
code translations fixed; both regression tests RED→GREEN, full suite93/93.
No deferred findings. PATCH0.23.1: compatible UI fixes; local commit only.
