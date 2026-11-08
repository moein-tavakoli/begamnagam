# Blunt tone and monthly-login deployment

Requirements: publish the prior 0.20.2 changes, private Swagger with existing credentials,
three public choices (polite/firm/blunt), firm default, blunt minimal edits without
abuse or changes to moderation. No paid tests or new SMS authorization.

Design: additive blunt ID/config flag; preserve legacy angry snapshots and guarded API
support without offering that mode in new UI. Reuse independently reviewed freeform
pipeline and civil direct templates. Prefer firm among enabled choices. Migration enables
the three requested choices with audited revision change only, leaving provider/budgets intact.

- [x] Add failing blunt/default/safety tests, implement schema, shared prompt and UI defaults.
- [x] Validate backend/frontend, migration consistency and desktop/mobile tone component.
- [ ] Version 0.21.0, local commit, reviewed CI promotion dev to prod.
- [ ] Stage candidate, backup/restore migration check, deploy all six fronts and backend.
- [ ] Verify runtime/session/tone settings and private Swagger; record actual evidence.

Use existing release scripts as reference, preserve source/image manifests and provider
settings. Never replay the archived unknown queue item; archival itself remains a separately
reviewable operational step rather than an automatic release side effect.

Local validation: 113 related PostgreSQL tests, 82 frontend tests, TypeScript, Django checks/migration consistency, Compose config and independent review passed. No important review findings; no paid model or SMS calls.

Automated isolated component rendering at 375/1440px confirms three radios, firm selection, blunt selection and no overflow; this is a component check, not an authenticated product journey. The existing native hot-reload UI remained running.
