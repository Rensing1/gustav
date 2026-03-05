# Plan: Keycloak Backlink Hardening on Error/Info Pages

## Context

Ticket: `docs/tickets/keycloak-registration-error-backlink-hardening-2026-03-05.md`

Problem:
- In verify/error paths, the primary backlink can resolve to an IdP account URL
  (`.../realms/.../account/`) instead of a useful app return target.
- This creates dead-end UX in incidents like `VERIFY_EMAIL_ERROR`.

Goal:
- Keep branded Keycloak pages unchanged visually.
- Harden backlink target selection so "Back to app" prefers app targets and
  excludes IdP account URLs as primary app CTA.

Non-goals:
- No realm flow changes.
- No cookie policy/proxy changes.
- No API/OpenAPI changes.

## User Story

As a learner or teacher who lands on a Keycloak error/info page,
I want a reliable "Back to app" action,
so I can safely return to the app login/start flow instead of an unhelpful IdP account page.

## BDD Scenarios

1. Given `pageRedirectUri` points to `/realms/.../account`, `/realms/.../account/`,
   or query/fragment variants like `/realms/.../account?x=1`,
   when an error/info template renders the primary app CTA,
   then the template must not use that URL as "Back to app".

2. Given `pageRedirectUri` is a valid app URL,
   when the page renders,
   then "Back to app" uses `pageRedirectUri`.

3. Given `pageRedirectUri` is unsuitable and `client.baseUrl` is suitable,
   when the page renders,
   then "Back to app" uses `client.baseUrl`.

4. Given app candidates are unavailable/unsuitable,
   when the page renders,
   then fallback links still include login/register recovery options.

5. Given `info.ftl` has both `app_link` and `actionUri`,
   when the page renders,
   then it shows exactly one primary CTA and prioritizes `app_link`.

6. Given `info.ftl` has `actionUri` but no usable app backlink,
   when the page renders,
   then the page offers action fallback; otherwise login fallback.

## TDD Plan (Red-Green-Refactor)

1. Red:
- Add failing contract tests in `backend/tests/test_keycloak_theme_files.py`
  for shared resolver usage and IdP account link exclusion.

2. Green:
- Add a shared Freemarker resolver helper in
  `keycloak/themes/gustav/login/_gustav_error_components.ftl`.
- Update `error.ftl`, `login-page-expired.ftl`, `info.ftl` to consume the helper.
- Keep fallback login/register behavior intact.

3. Refactor:
- Remove duplicated link-priority snippets from templates.
- Keep comments short and focused on security/UX intent.

## Verification

- Run:
  - `.venv/bin/pytest -q backend/tests/test_keycloak_theme_files.py`

Acceptance:
- New contract tests pass.
- Existing keycloak theme tests remain green.
- `info.ftl` keeps exclusive CTA priority (`app_link` -> `actionUri` -> `loginUrl`).
