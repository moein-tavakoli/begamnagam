# Management users workspace

User specification: real /manage subroutes; Users under Overview; compact accessible
row actions; full staff-only phones and partial phone search; user details combining
orders/AI-rejected requests/invitations; remove manual administrative-reason prompts.

Implementation choices: Next shared layout with route segments, account-scoped paginated
activity API, encrypted MessageAttempt for new preview outcomes, legacy moderation
metadata without invented text. Keep existing permission checks, automatic actor/action
accountability, CSRF, financial evidence and encryption. No server deployment authorized.

- [x] Backend: staff full phones/partial scan; scoped activity and text permissions.
- [x] Persistence: encrypted attempts, outcome capture, retention and key rotation.
- [x] Frontend: shared route layout, user details, compact actions, automatic reasons.
- [x] Advanced admin: hidden automatic reason defaults, preserve audit and other fields.
- [x] Integrated tests, migrations, native UI checks, review, version and local commit.

Ownership: frontend agent owns frontend code; management agent owns management_api,
user_activity and URLs/tests; attempt agent owns models/views/retention/rotation/migration;
root owns advanced admin forms, integration, documentation and versioning.

Final validation:645 PostgreSQL tests,87 frontend tests,TypeScript,Django/migration/Compose checks pass. Two review findings fixed: quota admission and limited-role navigation. Native Next routes/compilation pass; authenticated browser verification blocked by local certificate trust, with user handoff requested and no bypass. No deploy/push/provider calls authorized. Local version0.22.0.
