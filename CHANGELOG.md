# Versions

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
