# Monitoring and support composer implementation plan

> **For agentic workers:** Use executing-plans with independent backend/support work via dispatching-parallel-agents. Steps use checkboxes.

**Goal:** Staff-only Persian TV monitoring with MUI charts and 30-second default polling, plus requested support composer reversal.
**Architecture:** A read-only aggregate GET endpoint feeds an isolated client monitoring route. Existing permissions/session/frame remain shared. No provider calls, scheduler writes or infrastructure-health claims.
**Tech Stack:** Django, PostgreSQL, Next App Router, React, MUI X Charts Community.
**Spec:** ../specs/2026-11-08-monitoring-design.md (approved by user).

## Global constraints
- Work on dev, native Fast Refresh, no deployment/push, paid calls or real support-message submission.
- Persian values, private staff permission view_operations, no phone/text/ID payloads.
- Default refresh30s, choices30/60/120/300; persist browser choice; one request at a time; hidden/offline pause; stale/error visible; auth loss clears data.
- TV target1920x1080 with sidebar hidden; smaller screens may scroll. Provider balances overview only.

## Review focus
- Tehran bucket boundaries and created-vs-delivered semantics: backend boundary/denominator tests.
- Anonymous, inactive/member/limited staff access: endpoint tests and navigation tests.
- No data and failed refresh: empty charts and retained stale data, error clearly displayed.
- Race/unmount/hidden/offline: cleanup and serialized polling, browser request checks.
- TV/mobile fit and support composer direction: native1920/375 screenshot and focus inspection, no live writes.

### Task1 Backend monitoring aggregates
Files: backend/core/management_monitoring.py, backend/config/urls.py, backend/core/test_management_monitoring.py.
Interface: GET /api/v1/manage/monitoring, @staff_api GET core.view_operations.
Return generated_at/window(start,end,timezone), totals(accounts_new,requests,delivered,support_unanswered), hourly[{at,accounts,requests}], delivery[{status,count}], moderation[{status,count}], queue[{kind,status,count}], operations(snapshot()), alerts[{code,severity,count}], environment(demo,sms,otp,payment,paid_enabled).
Window: 24 hourly buckets including current partial Tehran hour, lower inclusive/upper now exclusive. Request and moderation audit creations use their created_at. Delivered counts/partition use MessageDelivery created_at within window (cohort), with explicit UI label. Queue includes live pending/submitting/unknown only, messages+invitations. Alerts active top5 ordered high first then recent, aggregate counts only. Do not call refresh_alerts or providers. Tests verify permission, exact boundaries/buckets, aggregate partitions, no private fields/no writes.
- [x] Write failing tests, observe404, implement bounded query aggregates, run scoped PostgreSQL tests.

### Task2 Monitoring UI
Files: frontend/lib/monitoring.ts, frontend/components/management-monitoring.tsx, frontend/components/management-frame.tsx, frontend/components/management-console.tsx, frontend/components/management-icons.tsx, frontend/lib/management.ts, frontend/tests/monitoring.test.ts, frontend/package*.
- [x] Test interval validation/default and restricted navigation, observe failures then implement typed schema/helpers.
- [x] Install compatible MUI X Charts Community exact version; LineChart, BarChart and PieChart with Persian formatting and empty states.
- [x] Implement serialized timer hook with abort, visibility/online listeners, saved interval and clear on auth errors; last-success timestamp and stale indicator.
- [x] Add monitoring navigation/route and frame TV query ?tv=1: hide sidebar, compact topbar, exitTV link; no Fullscreen permission required.
- [x] Create responsive dense cards, hourly trends, delivery/moderation donut, queue bar and translated alerts. Charts lazy route import, no artificial data.

### Task3 Support composer
Files owned by independent worker: frontend/components/support-chat.tsx and relevant shared support composer/CSS only.
- [x] Locate both public/staff renderers; reverse field/button order and flip send icon in all. Preserve keyboard order, submission/limits/drafts/real endpoints. Native verify without sending.

### Task4 Validate and release locally
- [x] Scoped backend/frontend tests and TypeScript; independent review of permissions, polls and data meanings.
- [x] Authenticated native TV1920x1080 and mobile375 visual checks, support form desktop/mobile; capture proof.
- [x] Update approved spec, API/ops guide, Persian changelog catalog and generatedMD; choose MINOR0.26.0 from latest; sync package/lock.
- [x] Review only task diff, run parity/diff checks and local version commit on dev. No push/deploy.

## Completion evidence

- Backend RED404 then8 scoped tests; full671 PostgreSQL tests passed. No model
  changes. After catalog edit,3 catalog access/shape tests passed again.
- Frontend RED helpers/permission test then GREEN, alert-unit RED then GREEN;
  full104 tests and TypeScript passed. Independent reviewer found critical-alert
  severity and payment wording issues; both corrected and reviewer confirmed.
- Native TV1920x1080: document width1920/height1080, no scroll. Mobile375: no
  horizontal overflow. Persian ticks visible, interval60 survives reload, reset30
  observed timestamp21:47:57 ->21:48:27 with no intervening edit/reload.
- Staff composer inspected at375 and1280: field left, button right, icon right.
  Public shared CSS reviewed; no fresh realOTP login or support sends performed.
- Proof local-only .local/monitoring-tv.png and monitoring-mobile.png; no fake
  rows, paid provider tests, push or deployment. Local version0.26.0.

Ruling: keep actual provider balances overview-only; show configured payment
provider rather than treating an env flag as effective checkout availability.
Ruling: chart window uses24 Tehran hourly buckets including current partial hour,
not a rolling exact24h, and delivery is a creation cohort; labels/docs state this.
