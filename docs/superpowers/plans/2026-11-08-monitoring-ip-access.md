# Monitoring IP access implementation plan

> Execute inline with the executing-plans workflow; review the auth boundary before committing.

**Goal:** Allow only aggregate monitoring without login from explicitly configured exact IPs.
**Architecture:** Owner-only singleton settings, server-side per-request IP or staff authorization, separate monitoring entry gate; existing staff and product auth stay independent.
**Stack:** Django/PostgreSQL, Next.js/React, MUI.
**Spec:** `docs/superpowers/specs/2026-11-08-monitoring-ip-access-design.md`

## Constraints and review focus

- Empty by default; no live IP grants, SMS, paid calls or deployments for verification.
- Accept canonical IPv4/IPv6 only; reject proxy, loopback, unspecified, multicast, link-local, zone, CIDR and malformed addresses.
- Trust only the existing verified proxy chain; spoofed headers and unresolved proxy peers never grant access.
- Owner-only settings with CSRF, stale-write conflict and atomic audit; revocation checked every read.
- IP authorization does not grant sessions, roles, private records or Swagger; errors fail closed and remove displayed data.

## Steps

- [x] Write `core.test_monitoring_access` API tests, first observe new settings endpoint failing (404).
- [x] Add `MonitoringAccessSettings` singleton and migration; implement strict validation, audited revision-controlled settings and access guard in `core.monitoring_access`; wire URLs and owner capability.
- [x] Test allowed/denied IPs, staff fallback, spoofing through trusted/untrusted hops, IPv6, revoke, malformed input, CSRF, stale/concurrent writes, no leaked data/DB writes and no access to other routes.
- [x] Add MUI settings form in `frontend/components/monitoring-access-settings.tsx` and independent monitoring gate in `management-console.tsx`; verify regular settings/staff login remain protected.
- [x] Run full backend suite with isolated PostgreSQL, migration check, frontend tests/typecheck, native display/settings and Next.js runtime checks.
- [x] Update operating docs and Persian catalog; choose minor version from latest recorded version, review scoped diff and prepare local dev commit only.

## Validation ledger

- RED: initial GET settings returned 404 instead of 200; `.local/monitoring-access-red.log`.
- GREEN: full PostgreSQL suite720/720, including15new tests and concurrent initial-save conflict/atomic audit; `.local/monitoring-access-backend-full.log`.
- Frontend116/116 and TypeScript; native owner settings and monitoring render, 375px layout has no horizontal overflow; Next.js compilation/runtime reports empty errors.
- Independent read-only security review: no material findings. Exact IP grant/revocation is verified in isolated tests; live list remains empty and no login is synthesized for QA.
- Ruling: use PUT to replace the full allowlist (REST semantics), and restrict editing to the owner because this grants anonymous network access. Do not add a delegable role permission or enable loopback for a convenient preview.
- Version0.30.0 adds compatible settings and optional monitoring authorization; deployment remains separate.
