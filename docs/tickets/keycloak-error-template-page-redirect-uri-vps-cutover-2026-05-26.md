# Ticket: Keycloak-Error-Template wirft 500 nach VPS-Cutover

## Status

Open. Production logs after the VPS cutover confirm that the Keycloak theme
still crashes in selected error flows when `pageRedirectUri` is missing from the
FreeMarker context.

Related ticket:

- `docs/tickets/keycloak-error-templates-500-missing-page-redirect-uri-2026-03-22.md`

## Summary

After the production VPS cutover on 2026-05-25, Keycloak emitted HTTP 500
responses while rendering themed error pages for invalid or expired auth flows.
The failing template path is again the GUSTAV error component resolver around
`pageRedirectUri`.

The observed production impact is limited in volume, but the behavior is still
wrong: invalid, expired, or cookie-less Keycloak flows must render a stable
GUSTAV recovery page instead of turning the recovery path itself into a server
error.

No user names, tokens, session IDs, IP addresses, or private operational details
are included in this ticket.

## Observed Evidence

Sanitized log review window: 2026-05-25 after cutover through 2026-05-26.

Key findings:

- Four IdP HTTP 500 responses were observed on Keycloak login-action paths.
- The failures involved registration, login/authenticate, and action-token
  recovery flows.
- Keycloak logged FreeMarker `InvalidReferenceException` for missing
  `pageRedirectUri`.
- The failing render path included `error.ftl` and
  `_gustav_error_components.ftl`.
- Triggering conditions included missing cookies and an expired action token.
- No matching Keycloak warning/error entries were observed after the initial
  post-cutover window, but the template bug remains reproducible by these edge
  conditions.

## Technical Cause

The shared Keycloak theme component assumes `pageRedirectUri` is always
available or safely defaulted. In some Keycloak error contexts that assumption is
false. When the resolver is evaluated, FreeMarker treats the missing value as an
invalid reference and the error page render fails with HTTP 500.

Files of interest:

- `keycloak/themes/gustav/login/error.ftl`
- `keycloak/themes/gustav/login/login-page-expired.ftl`
- `keycloak/themes/gustav/login/info.ftl`
- `keycloak/themes/gustav/login/_gustav_error_components.ftl`

## Required Behavior

- Missing `pageRedirectUri` must never crash a Keycloak error, info, expired, or
  action-token page.
- The fallback destination must be deterministic and safe, preferably the public
  GUSTAV app base URL.
- Expired verify/reset/action-token links must show a themed recovery page with
  clear next steps.
- Cookie-less scanner or stale-tab requests may still be rejected, but they must
  not produce template-level HTTP 500 responses.

## Suggested Implementation

- Harden the shared FreeMarker resolver so all access to `pageRedirectUri` is
  guarded with missing/null-safe defaults.
- Review call sites in `error.ftl`, `login-page-expired.ftl`, and `info.ftl` for
  other Keycloak-context variables that may be absent in error paths.
- Add regression coverage that renders the relevant templates with no
  `pageRedirectUri` in the model.
- Confirm that expired verify-email and reset/action-token paths return a
  themed non-500 response.

## Acceptance Criteria

1. Keycloak error/info/expired pages render without HTTP 500 when
   `pageRedirectUri` is missing.
2. Expired action-token and cookie-less login-action flows return a themed
   recovery page.
3. Regression tests cover at least `error.ftl` with absent `pageRedirectUri`.
4. Production logs no longer show FreeMarker `InvalidReferenceException` for
   `pageRedirectUri`.
