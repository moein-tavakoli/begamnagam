# Versions

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
