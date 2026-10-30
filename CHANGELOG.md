# Changelog

Codex chooses MAJOR.MINOR.PATCH for each completed, coherent change and creates
its local version commit on dev after relevant checks. Keep work in progress
under Unreleased; move only completed work into its versioned section before
committing. Local versions do not imply prod promotion or server deployment.
Push requires an explicit user request. See [versioning policy](docs/versioning.fa.md).
Historical release reports below contain deployment evidence and limitations.

## Unreleased

## 0.16.0 — 2026-10-30 — Lightweight homepage entrances (local)

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
