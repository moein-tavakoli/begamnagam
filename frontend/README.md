# BegamNagam web

A Persian, right-to-left Next.js App Router client. The web app is responsive on phones and desktops, uses locally bundled Vazirmatn fonts, and includes a PWA manifest with standalone display. It deliberately does not cache authenticated API responses or message drafts for offline use.

## Run locally

Use Node.js 22 or newer and start the Django development API on `http://localhost:8000` first.

```sh
npm ci
npm run dev
```

Open `http://localhost:3000`. The top banner reports the backend environment. In demo mode, the OTP is displayed in the form and the payment and delivery are simulated. No external SMS or payment adapter is invoked by this client.

The client only requests the same-origin `/api/v1` path. The Next rewrite forwards it to `INTERNAL_API_URL`, which defaults to `http://localhost:8000`. This keeps session and CSRF cookies on the browser's origin. The Django CSRF trusted origins must include the frontend origin.

**Rebuild after changing `INTERNAL_API_URL`:** Next resolves rewrites during the build. The Docker build accepts it as a build argument and defaults to `http://backend:8000` for Compose. It must never contain credentials. Browser code does not receive this private hostname.

Local builds use the normal Next server for `npm start`. The Docker builder sets `BUILD_STANDALONE=1`, copies the traced standalone server plus static assets, and runs it directly as a non-root user.

## SEO configuration

Public pages (`/`, `/help`, `/privacy`) have unique Persian metadata, canonical URLs, Open Graph and Twitter large-image previews. Their initial HTML includes absolute image URLs, PNG MIME type, dimensions, alt text and an HTTPS secure URL. All use the local 1200×630 asset at `/images/social-card.png`. JSON-LD connects the brand (`Organization`), `WebSite`, logo/social `ImageObject`s and page; the homepage adds `WebApplication` and `Service`, help uses visible shared `FAQPage` answers, and help/privacy include breadcrumbs. No legal business details, contact channels, social accounts, prices or ratings are invented.

Profile, history, invitations, recipient settings/token links, admin/API paths, 404 and offline pages stay excluded from indexing. Private pages have individual generic titles/descriptions and explicitly clear public canonical/social metadata. Root defaults remain safe for unknown routes. JSON-LD must never include phone numbers, recipient tokens or private messages. See [SEO operations and the read-only crawler checker](../docs/seo.md) for the route policy, deployment settings and full verification commands.

`APP_BASE_URL` is the single origin for canonical, social and structured-data URLs and the sitemap; its local fallback is `http://localhost:3000`. `SEO_INDEXABLE=0` is the default for local demo, private CT and staging: pages declare `noindex` and the sitemap contains no URLs. Robots allows HTML crawling so crawlers can observe `noindex`; API/admin paths are disallowed. Only an approved public release with a real public HTTPS origin may use `SEO_INDEXABLE=1`. This setting does not enable real SMS, payments or deployment.

The confirmed public origin is `https://begamnagam.ir` (without `www`), recorded in `deploy/release.env.example`. Use it as `APP_BASE_URL` when building the public frontend image; native development and the private CT retain their local/internal origins and default `noindex` policy.

For native `make dev-ui` / `npm run dev`, copy `.env.example` to `.env.local` **inside `frontend/`**, or export the two variables before starting the process. Next does not automatically load the repository root's Compose `.env` from this app. Restart the development process once after changing environment configuration; source edits continue through Fast Refresh.

**Rebuild after changing `APP_BASE_URL` or `SEO_INDEXABLE`:** both public values are fixed in the frontend build; robots and sitemap are generated then. HTML pages render per request with a fresh CSP nonce and `private, no-store`, including nonce-bearing JSON-LD. The Docker builder accepts both values as build arguments, and `compose.yaml` forwards them from the root `.env`. Prebuilt images in `compose.release.yaml` / `compose.internal.yaml` must already have the correct values baked in: changing their runtime env file or restarting the container is insufficient. Never add credentials to `next.config.ts`'s public `env` object. See [SEO operations](../docs/seo.md) and the [security audit](../docs/security-audit-2026-10-27.fa.md) for validation and rendering tradeoffs.

```sh
npm test
npm run typecheck
npm run build
npm start
```

## Routes and state

- `/`: landing page and message composition. The journey is topic/input → exact reviewed preview → recipient and sender verification → order review → explicit demo payment → actual API status.
- `/history`: sender's own orders, masked recipient, reviewed message, amount, timestamp, tracking ID, and logout.
- `/preferences`: authenticate the number owner, read their own receiving preference, and stop or resume receiving for that number.
- `/help`: instructions, live configured price, limitations, and FAQs.
- `/privacy`: scope of anonymity, processing, acceptable use, recipient choice, and local-demo limitations.
- `/admin/`: proxy to Django's administrator interface. This is separate from phone authentication.

`components/app-provider.tsx` loads the authoritative environment, price, available topics, and login state from `/bootstrap`. A service failure shows a retry action and disables composition; it never substitutes a successful local response.

`lib/api.ts` sends the CSRF cookie as `X-CSRFToken` for mutations, preserves same-origin cookies, applies a 15-second request timeout, and converts network/proxy errors into recoverable Persian messages. Orders retain their `Idempotency-Key` across retries for the same preview/recipient. Payment retry uses the existing order ID.

The template mode is labelled **متن آمادهٔ بررسی‌شده**. Optional Ollama mode is labelled **انتخاب متن با کمک هوش مصنوعی** because it selects a reviewed template rather than generating arbitrary outgoing copy. The backend performs enforcement; client validation only helps users correct mistakes.

## Interface conventions

Design tokens and responsive rules live in `app/globals.css`. The palette uses warm ivory, forest green, and muted olive. Icons are inline SVG and fonts are installed through npm, so building does not require Google Fonts access.

Form labels, inline errors, focused error summaries, visible keyboard focus, native OTP paste/autofill, logical RTL layout, loading states, and reduced-motion support are included. Recipient and OTP forms are independent: do not nest the authentication form inside the order form. Recipient controls use the `recipient-order-form` ID for explicit form association.

No delivery status implies that the recipient opened or read a message. `delivered_demo` is explicitly labelled as a simulation. There is no reply, chat, public profile, or recipient lookup.

## Validation scope

SMS OTP uses native `autocomplete="one-time-code"` plus an optional, consent-based
WebOTP listener started before requesting the message. It stops on manual input,
verification, number changes, page exit, unmount or a 60-second timeout. Autofill
does not submit the form. The backend adds an origin-bound last SMS line for a
valid public HTTPS `APP_BASE_URL`; provider lookup templates require the equivalent
approved template. Codes are never saved to browser storage or logged.

Installed-browser failures in optional Service Worker/BroadcastChannel access
fall back to the working web UI. This is not evidence that a native Huawei Quick
App launcher crash has been fixed. See [OTP and Huawei PWA checks](../docs/otp-pwa.fa.md)
for validation, browser limitations and device recovery steps.

The built-in Node tests cover Persian/Arabic/international phone normalization, rejection of malformed numbers, pending-status handling, CSRF and idempotency headers, API moderation errors, offline/non-JSON proxy failures, and SEO URL/indexing rules. Run the real browser journey against Django in addition to these tests when changing composition or authentication.

The initial implementation was also checked in a real browser against PostgreSQL, Redis, RabbitMQ, and an independent Celery worker: preview → Persian-number OTP → explicit order → demo payment → asynchronous `delivered_demo` → masked history. Stop/resume persisted through reload, logout cleared the private history, rejected content focused an error and recovered after correction, and an unavailable bootstrap disabled sending until retry succeeded. Layout checks found no horizontal overflow at 375×812, 768×1024, and 812×375; reduced motion disabled smooth scrolling. `/admin/` reached Django's login page through the same-origin proxy without a redirect loop.

## Phase-one foundation

UI follows the approved playful mobile reference; see `design-system/begamnagam/MASTER.md`. Production registers `/sw.js`; development does not. CacheStorage allowlist contains only `/offline.html` and three public icons. Private pages, API/RSC responses and mutations are never persisted or replayed. The worker uses the normal waiting lifecycle, without skipWaiting/forced reload. Full installation/update/privacy acceptance remains phase-gated. See `docs/phase-one/README.fa.md` for test evidence and the open Compose build blocker.
