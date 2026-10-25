# Versions

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
