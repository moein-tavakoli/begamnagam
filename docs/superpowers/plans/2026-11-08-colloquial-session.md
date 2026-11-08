# Colloquial rewriting and monthly product login implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Minimize rewriting, preserve colloquial Persian and meaning, and persist verified product login for 30 days.

**Architecture:** Keep the existing independent generation/review pipeline and safety checks. Share explicit minimal-edit/register guidance across both providers and tones; require a boolean register-preserved review result. At successful OTP login set an absolute 30-day session expiry; keep anonymous/staff defaults and private Swagger's eight-hour policy unchanged.

**Tech Stack:** Django 5.2, existing GapGPT/Ollama clients; no dependencies or model changes.

**Spec:** User request in this chat: keep colloquial language and original meaning; require ordinary login about once a month.

## Global constraints

- Work on dev; preserve the unshipped 0.20.1 queue patch.
- No deployment, real OTP/SMS or paid AI test is authorized by this task.
- Never bypass moderation or independent review; keep sensitive-action recent-auth checks at 300 seconds.

## Review focus

- Formalization without a semantic change must be rejected by review.
- Harmless, already suitable colloquial text may stay unchanged.
- Role, payer, polarity and concrete details must survive compression.
- Cookie persistence must survive a new browser client while hard expiry still works.
- Existing short documentation expiry must not leak into a later OTP product login.

## Task 1: Monthly product sessions

- [x] Add cookie/database expiry, reopening, hard-expiry and inherited-short-expiry tests; observe failures.
- [x] Set explicit fixed 30-day expiry only at verified OTP login.
- [x] Run session/API/documentation/bot regression checks.

## Task 2: Minimal colloquial editing

- [x] Add independent style-review rejection and colloquial success tests for both providers; observe failures.
- [x] Update shared minimal-edit guidance, tone instructions and review schema/failure mapping.
- [x] Run provider, tone, freeform and moderation regression checks.

## Finish

- [x] Update operating/API guidance, version metadata and release notes.
- [x] Review task diff, run relevant checks, make local version commit; do not push or deploy.

## Implementation review

- Red phase: all four monthly-session tests failed under the old seven-day/inherited-expiry behavior. Style tests exposed missing register enforcement and acceptance of the old incomplete verdict.
- Both transports share source-purpose/register rules; Ollama retains its existing two-field generation schema. No raw-text fallback or extra provider call was added.
- User supplied forgiveness and friendly-wish examples are covered with local guards and controlled provider responses. These tests verify the pipeline contract, not real-model semantic accuracy.
- Expiry is set only after successful OTP, as a fixed timestamp. Existing sessions are not retroactively extended; documentation login remains eight hours.
- Final diff review checks: no secrets, dependencies, migrations, historical snapshots, provider budgets, queued sends or server state changed.

Validation: 611 PostgreSQL backend tests, 81 frontend tests and TypeScript passed. Independent code review reported no critical/important findings. Version 0.20.2; local commit only.
