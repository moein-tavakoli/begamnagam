# Production security assessment implementation plan

> **For agentic workers:** Use executing-plans for the sequential assessment and verification-before-completion before recording outcomes. Steps use checkboxes for tracking.

**Goal:** Perform the user's authorized non-disruptive penetration tests and server/container vulnerability assessment, remediate confirmed issues, and preserve honest evidence of what is and is not fixed on production.

**Architecture:** Record live image identifiers, service health and installed packages. Run vulnerability matching on the operator machine; send bounded read-only probes to the owned application. Reproduce state-changing attacks only against isolated synthetic databases with provider network access disabled.

**Tech stack:** Django, Next.js, Docker Compose, Debian, Alpine, Trivy, Nmap, Python.

**Spec:** User request of 2026-11-17 and repository AGENTS.md; prior evidence in docs/security-audit-2026-11-17.fa.md.

## Global constraints

- Preserve live data, queued deliveries and availability; no stress tests, real OTP/SMS, AI/payment calls, live account mutation or credential guessing.
- Read only exact owned hosts, images and public paths; no network-range scan or third-party target.
- Never export mounted database volumes, credentials, private messages or customer records. Keep raw image/config artifacts private and out of Git.
- Development stays on dev; no push or server release inferred from a local version. Bot-specific behavior remains outside this website task.
- Do not install heavy scanners or patch/restart live services during evidence gathering.

## Review focus

- Installed version findings require actual image/package evidence and vendor applicability; a CVE match is not proof of exploitation.
- Network tests from the LAN cannot establish exposure from an independent Internet vantage point.
- Container OS packages, application dependencies and host kernel have separate ownership and update paths.
- Failed or unavailable advisory databases are incomplete scans, never clean results.
- Compare health and restarts before/after; interrupted checks must remain explicitly incomplete.

## Tasks

- [x] Capture sanitized live inventory, package metadata, service baseline and access limits in private .local/pentest-20261117/ artifacts.
- [x] Verify the scanner release checksum and database freshness, scan all six distinct running images and the Debian host package inventory locally, and record exact image digests and limitations.
- [x] Run bounded port, TLS, HTTP authorization, path/host/header and sensitive-file probes; isolate all stateful exploit scenarios and check service health afterwards.
- [x] Validate each actionable finding against authoritative advisories, reproduce where safe, and add targeted regression tests before code/config fixes.
- [x] Validate changes and obtain an independent final review; record unresolved operational requirements without claiming deployment.
- [x] Publish a sanitized Persian report and machine-readable evidence; synchronize a PATCH version, render/check Persian release notes and commit only task files locally.

## Outcome

- Recorded version 3.1.4 as local work; live application remains 3.1.2.
- Repaired Fail2Ban and upgraded 48 host packages; verified all 13 original service starts, image IDs and restart counts unchanged.
- Passed 53 bounded web probes, 791 backend tests on the final amd64 image, 129 frontend tests, typecheck, four probe regression tests, final frontend HTTP checks and Compose validation.
- Independent final review checked scan summaries, evidence hashes, manifests, residual risks and documentation; no blocker remained.
- New image rollout, runtime/base-library maintenance and excluded edge/kernel scope remain explicitly pending. No push or application deployment performed.
