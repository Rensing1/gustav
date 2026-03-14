# Plan: Keycloak Error Pages in GUSTAV Theme

Status: umgesetzt und verifiziert (2026-03-14)

## Re-Verification 2026-03-14
- Die gethemten Error-/Expired-Seiten sind im Repo-Stand vorhanden.
- Verifiziert mit:
  - `backend/tests/test_keycloak_theme_files.py` -> `27 passed`

## Why
Users intermittently hit Keycloak error pages during registration and email verification
(`cookie_not_found`, expired or invalid action tokens). Those pages currently fall back to
the parent Keycloak theme and break visual consistency.

## Goal
- Keep error and expired flows in the GUSTAV login look.
- Provide clear, actionable recovery guidance.
- Keep locale switching available but visually de-emphasized.
- Add contract tests so template regressions are caught in CI.

## Scope
- Add login theme templates:
  - `keycloak/themes/gustav/login/error.ftl`
  - `keycloak/themes/gustav/login/login-page-expired.ftl`
- Add i18n keys in DE/EN bundles for titles, hints, and CTA labels.
- Add subtle locale-link styling in `gustav.css`.
- Extend `backend/tests/test_keycloak_theme_files.py` with template and i18n checks.

## Non-goals
- No changes to cookie policy, reverse proxy headers, or Keycloak realm flow wiring.
- No API contract changes.

## Design Notes
- Templates use defensive Freemarker guards (`??`, `?has_content`) for optional context values.
- Primary CTA points back to the app via fallback chain:
  1. `pageRedirectUri`
  2. `client.baseUrl`
  3. `url.loginUrl`
- Locale switch is rendered as compact footer links instead of the default prominent dropdown.

## Test Plan
1. RED:
   - Add failing tests in `backend/tests/test_keycloak_theme_files.py` for:
     - template presence
     - branded hooks
     - de-emphasized locale links
     - required i18n keys
2. GREEN:
   - Implement templates, i18n keys, and CSS additions until tests pass.
3. Regression:
   - Re-run `backend/tests/test_keycloak_theme_files.py`.

## Risks and Mitigation
- Risk: Keycloak context variables differ between error flows.
  - Mitigation: guarded access and robust fallback links.
- Risk: Missing i18n keys render raw key names.
  - Mitigation: explicit message-key tests for both DE and EN bundles.
