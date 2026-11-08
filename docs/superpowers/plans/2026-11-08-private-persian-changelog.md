# Private Persian release history

**Goal:** Add Persian summaries of recorded versions in a MUI management page,
visible only to authenticated active staff. Do not publish a changelog asset.

**Design:** A packaged backend JSON catalog is the single source for the staff
API and generated `CHANGELOG.fa.md`. Summaries cover all versions recorded in
the technical changelog. Unknown historical dates/install states remain unknown;
new local versions are labeled local. The frontend fetches notes after staff
login, never embeds them in public client modules. Use the existing /manage
shell, icons, typography, cards and responsive pagination-by-reveal.

- [x] Test anonymous/member/inactive staff denial, staff GET-only/no-store and
  catalog/Markdown/version parity before adding the endpoint.
- [x] Add Persian catalog + generator, staff endpoint and management navigation/UI.
- [x] Check source parity, frontend tests/typecheck and related PostgreSQL tests.
- [x] Browser-check authenticated desktop/mobile and anonymous denial without
  changing account or provider state; review independently.
- [x] Document maintenance; version and commit locally on dev. No push/deployment.


Validation: endpoint tests RED at404, then15relatedPostgreSQL tests GREEN;
96frontend tests and TypeScript passed. Generator --check verifies exactFA
Markdown, all61versions and catalog/application0.24.0 parity. Native anonymous
HTTPS GET401; publiccatalogURL404. Authenticated desktop/375px show Persian
notes without overflow; reveal older versions increases renderedcards10→20.
Independent read-only review found no material issues. No push or deployment.
