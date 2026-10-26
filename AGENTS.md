# Contributor guide

This repository is a Persian RTL local-demo product. Read `README.md` and the
relevant document in `docs/` before changing behavior. Current architecture is a
Django monolith with Next.js, PostgreSQL, Redis, RabbitMQ and Celery.

## Documentation

Use Context7 MCP whenever working with a library, framework, SDK, API, CLI or
cloud service: start with `resolve-library-id`, then `query-docs` with the selected
ID and the complete relevant question. Prefer official sources. General business
logic, refactoring and code review do not need Context7. If the service is
unavailable or quota-limited, report that fact and consult official primary docs;
do not invent current APIs.

## Product invariants

- Demo remains the default. Provider protocol clients are present but network access
  defaults to disabled. External activation requires credentials, contract/refund
  approval, bounded budget and a pilot allowlist for paid activation; never infer permission to spend
  from implementation work. Local contract simulations are not vendor sandbox tests.
  Keep demo labeling explicit; `delivered_demo` is not a real delivery receipt.
- The user separately authorized live OTP and three real gift SMS per verified
  account on begamnagam.ir, with paid sends disabled. The explicit
  `config.live_sms_settings` profile permits all valid recipients, preserves
  cost accounting/moderation/opt-outs, and does not attest contract or legal approval.
  Do not activate paid checkout or replay demo orders under this authorization.
- The user explicitly removed the aggregate daily provider cost cap for this live
  gift profile. `PROVIDER_DAILY_BUDGET_UNLIMITED=1` opts in; keep default/demo and
  paid pilots bounded. Preserve the ledger, per-call anomaly checks, three gift
  credits, recipient controls and retry idempotency. Never replay cancelled orders.
- A separately authorized local real-OTP test may keep `DEMO_MODE=1`, payment demo,
  message delivery console and the general provider network disabled. It requires
  `LOCAL_REAL_OTP_ENABLED`, Kavenegar credentials and positive per-code/daily
  budgets. Login OTP accepts all valid phone numbers; do not reintroduce a
  recipient allowlist for authentication. This permission applies only to fixed OTP
  text and does not activate order SMS, payment providers or public deployment.
- Recipients must never see sender identity. Sender-facing errors must not expose
  whether a target opted out or has an account. The explicitly requested authenticated
  invitation panel alone reports existing membership and signup after a phone invitation;
  it must not reveal opt-out or another inviter's identity. Preferences apply to the verified
  account's own number only.
- A product session requires a verified phone `Account`; Django admin login alone
  is insufficient. Mutating requests require CSRF protection.
- Prices are integer toman values. A preview snapshots the reviewed price and text.
  Retries preserve the checkout idempotency key. Payment and outbox creation stay
  transactional; queue payloads contain identifiers rather than private content.
- Reviewed templates remain the default. The user also requested opt-in GapGPT
  freeform rewriting with credentials left empty for now. Only locally filtered,
  independently model-reviewed, locally rechecked output sealed to its exact
  preview may reach either SMS adapter. Raw input and unapproved model text must
  not be dispatched. Missing credentials or uncertain checks must fail closed;
  never silently substitute a topic template for a requested AI rewrite.
- Rate limits must account for the Next.js reverse proxy: do not interpret the
  frontend container's address as a unique end user or blindly trust forwarded IPs.
- Keep phones encrypted at rest and use keyed hashes for matching. Do not log full
  phones, OTPs or private input. Do not commit `.env`, local databases or secrets.

## UI development workflow

- Use `make dev-ui` / `npm run dev` for all UI editing and previews. Next.js
  Fast Refresh must apply source changes while the dev server stays running.
- Do not rebuild Docker images, run `make up`, or restart the frontend for each
  UI edit. Keep the backend/data services running and run the UI natively.
- `npm ci` is for initial setup or lockfile changes, not each UI edit.
- Production builds and Compose image builds are separate release/PWA checks,
  run only when that validation is needed; service-worker installation/offline
  acceptance is checked in production mode, not inferred from hot reload.

## Validation

Backend: `DJANGO_TESTING=1 python manage.py test` inside `backend/`, with
`DATABASE_URL` and `REDIS_URL` supplied for PostgreSQL integration tests. Check
migration consistency after model changes. SQLite skips row-lock concurrency tests.

Frontend: use hot reload during UI iteration. Run `npm test` and
`npm run typecheck` inside `frontend/` as appropriate; reserve `npm run build`
for release/PWA validation rather than each visual edit.
Check the full journey at desktop and 375px mobile widths, including OTP, retry,
history and recipient preferences. Keep labels, focus, keyboard navigation,
Persian typography and reduced motion intact.

Full stack: `docker compose config --quiet`, `docker compose up --build -d --wait`,
then `python3 scripts/smoke.py`. The smoke script is restricted to local demo
instances. Do not prune unrelated Docker networks or volumes to fix local setup.

Update API and operating docs when behavior or environment variables change.
