# Full phone display implementation plan

User explicitly requests unmasked numbers everywhere on the website, including support.
Use canonical full-phone fields only after existing owner/staff guards; preserve
anonymous-message sender secrecy and encrypted storage/log redaction. Keep old
masked API fields for compatibility, but never use them as UI display fallbacks.
Unavailable/pruned ciphers display an unavailable/deleted label, never reconstruct.

- [x] Owner API worker: add phone to own bootstrap/OTP and staff-only support;
  recipient_phone to owned order serializers, phone to owned invitation serializer;
  optional additive v2 schemas/me + guide as required by shared serializers.
  TDD ownership/anonymous/support/privacy tests, no actual sends.
- [x] Management worker: replace masked phone display columns in Next generic
  records, per-user invitation activities and Django admin; decrypt bounded pages
  after existing guards. No plaintext at rest/logs/audits. Regression tests.
- [x] Root: update all UI types/renderers to full phone fields; no masked fallback;
  safe unavailable label. Review all mask sites to leave storage/log/API legacy only.
- [x] Run backend/frontend tests/typecheck and staff browser support proof. Preserve
  real profile; no synthetic public session or SMS/paid tests. Update operating docs,
  Persian changelog and synchronized version, then local commit on dev only.

Completed as local0.27.0. RED: new owner fields absent and management masked
columns; scoped69 owner/API +44 management tests passed. Full685 suite initially
found3 legacy masking assertions; updated only those expectations and strengthened
post-logout no-phone checks, then full685 PASS. Front104 and typecheck PASS;
Persian catalog parity PASS. Independent review clean. Native staff support1280
and375 full-phone assertions true and no horizontal overflow; private screenshot
.local/full-phone-support.png. No fresh realOTP/public synthetic session, SMS,
support message, paid calls, push or deployment. Encrypted/pruned/log behavior
unchanged; legacy payload fields retained solely for API compatibility.
