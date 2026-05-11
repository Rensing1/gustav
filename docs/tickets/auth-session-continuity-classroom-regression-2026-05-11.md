# Ticket: Auth-Session-Continuity classroom regression

## Summary

GUSTAV still has a recurring classroom blocker around authentication
continuity. Learners sometimes see missing modules, missing feedback, vanished
submissions, generic error pages, or stale learning state. In many cases the
problem disappears after a browser reload or a fresh visit to
`gustav.example`. Often the user is asked to authenticate again but
does not need to enter credentials, which means Keycloak SSO is still active and
GUSTAV failed to preserve or recover its app/BFF session state.

This must be treated as one systemic Auth-Session-Continuity defect, not as a
set of unrelated learning UI bugs.

## Impact

- Learners lose trust in whether work was saved or submitted.
- Teachers receive reports of missing modules, missing feedback, and broken
  learning progress even when persisted data may still exist.
- A recoverable authenticated state is surfaced as an application failure or
  login interruption.
- Reloading can mask the root cause and makes classroom debugging slow.
- Existing learning regressions become harder to diagnose because auth
  instability can produce the same user-visible symptoms.

## Current Architecture

GUSTAV currently uses three separate auth/session layers:

- Keycloak manages identity, login, SSO, remember-me, and password/reset flows.
- SvelteKit acts as Browser-BFF and stores OIDC token material server-side via
  an opaque `gustav_bff_session` cookie.
- FastAPI mints and validates the stable app session `gustav_session` for
  existing cookie-authenticated APIs and H5P/server flows.

The split is intentional, but the recovery semantics are incomplete. A browser
can still have recoverable authenticated state while a protected SvelteKit
loader or later backend request receives `401` and renders a generic failure
instead of doing deterministic session continuity.

## Verified Findings

- Production is configured for persistent DB-backed sessions:
  `SESSIONS_BACKEND=db`, `APP_SESSION_TTL_SECONDS=86400`, and
  `BFF_SESSION_TTL_SECONDS=86400`.
- Auth-relevant containers were stable during inspection; this was not caused
  by recent container restarts.
- Aggregated session-table counts showed active app and BFF sessions, many
  active BFF sessions with expired access tokens, and no active BFF sessions
  missing refresh tokens. This points to refresh/recovery handling, not simply
  absent refresh tokens.
- Web logs showed repeated `GET /api/app/session-bootstrap 401` bursts, while
  direct Learning/Teaching endpoints did not show matching direct `401` counts
  during the checked window.
- Request sequences showed successful BFF session reads directly before
  `session-bootstrap` 401 bursts, then later successful bootstrap or
  session-sync recovery.
- Existing focused auth tests are green, but they do not cover the observed
  mixed state: parent bootstrap or BFF session state partly available, followed
  by a later protected backend request or bootstrap attempt returning `401`.
- Keycloak error flows can still produce HTTP 500 because custom theme
  templates dereference `pageRedirectUri` when Keycloak does not provide it.

No user identifiers, session IDs, token values, or private operational log lines
are included in this ticket.

## Probable Root Cause

The session model has recoverable mixed states, but the application treats too
many of them as final unauthenticated states.

Examples:

- The BFF session exists, but the access token is expired and a refresh/retry
  path races or fails transiently.
- The stable app session remains valid, but the BFF bootstrap path temporarily
  cannot produce a valid bearer-authenticated request.
- A protected route's parent layout obtains enough session state, but a later
  page-level `requireBackendJson` call receives `401` and becomes a generic
  SvelteKit error page.
- Keycloak still has active SSO, so a follow-up login/continue flow can repair
  the application state without credentials.

The current behavior creates the visible classroom pattern: reload or revisit
repairs the session, but the first failing request already disrupted the
learner workflow.

## Required Fix

### 1. Centralize Auth Recovery in the SvelteKit BFF

Protected SvelteKit loaders and actions must handle backend `401` consistently.
When a backend call fails with `401`, the BFF must decide centrally whether the
state is recoverable before surfacing an error.

Required behavior:

- If a fresh token can be read or refreshed, retry the backend request once.
- If the app session is still active or Keycloak SSO may recover the state,
  redirect to `/auth/continue?redirect=<current-path>`.
- If the session is truly expired or unrecoverable, redirect to the normal login
  entry.
- Do not render generic page errors for recoverable auth states.
- Do not hide modules, submissions, feedback, or history because a transient
  auth recovery step was skipped.

Files of interest:

- `frontend/src/lib/server/api.ts`
- `frontend/src/lib/server/session.ts`
- `frontend/src/lib/server/guards.ts`
- protected route loaders under `frontend/src/routes/**/+page.server.ts`

### 2. Make Session Bootstrap Failure Reasons Observable

FastAPI should make `session-bootstrap` failures distinguishable without
leaking secrets.

Required behavior:

- Log structured, token-free reason codes for:
  - missing bearer
  - invalid bearer
  - BFF session missing
  - token refresh failed
  - app session exists but BFF bearer bootstrap is unavailable
- Keep responses `private, no-store`.
- Do not log access tokens, refresh tokens, ID tokens, session IDs, user IDs,
  email addresses, or request cookies.

Files of interest:

- `backend/web/main.py`
- `backend/web/routes/app.py`
- `backend/identity_access/tokens.py`
- `backend/identity_access/bff_sessions_db.py`

### 3. Harden Keycloak Error and Expired Pages

The Keycloak theme must never fail while rendering an error or expired-flow
page.

Required behavior:

- `error.ftl`, `info.ftl`, and `login-page-expired.ftl` must safely default
  missing `pageRedirectUri` before passing it into shared helpers.
- Shared helper functions must tolerate missing arguments defensively.
- Expired action-token, expired login, cookie-not-found, and detached info flows
  must render a usable recovery page instead of HTTP 500.

Files of interest:

- `keycloak/themes/gustav/login/error.ftl`
- `keycloak/themes/gustav/login/info.ftl`
- `keycloak/themes/gustav/login/login-page-expired.ftl`
- `keycloak/themes/gustav/login/_gustav_error_components.ftl`

### 4. Add Regression Tests for Mixed Session States

Current tests verify standard flows but miss the observed failure mode. Add
tests that model partial/recoverable auth state.

Required frontend tests:

- Expired access token plus valid refresh token: backend request refreshes and
  succeeds without visible login.
- Backend request returns `401` after parent bootstrap: route redirects through
  `/auth/continue` rather than throwing a generic page error.
- Valid app session but missing/unusable BFF bootstrap: recover through
  continuation.
- Truly expired BFF/app/SSO state: normal login redirect still happens.

Required backend tests:

- `session-bootstrap` remains strict for invalid bearer tokens.
- Failure reason logging is structured and contains no token/session/user
  values.
- `session-sync` continues to replace stale app sessions.
- DB-backed BFF sessions with expired access tokens but unexpired
  `session_expires_at` remain refreshable.

Required Keycloak tests:

- Error and info templates tolerate missing `pageRedirectUri`.
- Expired-login/action-token templates contain only guarded references to
  optional Keycloak variables.

## Acceptance Criteria

1. A learner with recoverable authenticated state can hard-reload a protected
   learning page without being sent to a generic error page or unnecessary login
   bounce.
2. Expired access tokens with valid refresh tokens recover without user-visible
   interruption.
3. If Keycloak SSO is still active, GUSTAV uses silent continuation instead of
   treating the user as fully logged out.
4. Protected route loaders do not turn recoverable backend `401` responses into
   missing modules, missing submissions, missing feedback, or generic page
   errors.
5. Truly expired or invalid sessions still fail closed and redirect to login.
6. Keycloak error/expired pages render a recovery UI and no longer produce 500
   due to missing optional template variables.
7. Auth logs expose enough reason codes to triage failures without leaking PII,
   tokens, cookies, session IDs, or user identifiers.

## Manual Verification

Run these checks after implementation in a production-like environment:

1. Log in as a learner, open a modular learning unit, submit feedback, and
   reload during or shortly after feedback generation.
2. Verify modules, visible work, submission state, and feedback state remain
   coherent after reload.
3. Leave the tab open until the access token is stale but the BFF/app sessions
   are still valid; reload and verify silent recovery.
4. Expire or delete both app and BFF sessions; verify login redirect still
   happens.
5. Trigger Keycloak expired login/action-token flows and verify recovery pages
   render without 500.

## Rollout Notes

- This ticket belongs upstream as a product/auth fix.
- Do not patch production-only code or private ops files as the primary fix.
- Keep all public PR artifacts sanitized.
- Existing related tickets should be referenced, but this ticket is the final
  blocker for the systemic auth-session continuity issue.
