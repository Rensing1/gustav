# Ticket: Hard reload can force re-login despite active SSO session

## Summary
On protected Svelte pages, a hard reload can send the user back to the login page even though the underlying Keycloak SSO session is still active.

The user can then recover immediately by clicking `Anmelden` once, without entering credentials again. This points to an app/BFF session continuity failure during reload, not to a real identity logout.

## Impact
- Users appear unexpectedly logged out during active work.
- Hard reload becomes disruptive and can be mistaken for data or progress loss.
- The symptom overlaps with other learner-workspace bugs and makes root-cause diagnosis harder.
- A recoverable session state still produces a visible login interruption.

## Reproduction (PII-free)
1. Open any protected learning or teaching page while already authenticated.
2. Perform a hard browser reload.
3. Observe redirect to the login page.
4. Click `Anmelden`.
5. Observe that access returns immediately without entering credentials again.

## Verified Findings
- SSR bootstrap depends on `GET /api/app/session-bootstrap`.
- Protected Svelte routes redirect to login when that bootstrap returns `null` or `401`.
- `/api/app/session-bootstrap` is a BFF-bearer-only endpoint and does not fall back to the normal app session cookie.
- Production logs on April 21, 2026 show repeated `GET /backend-internal/app/bff-session 200 OK` directly before `GET /api/app/session-bootstrap 401 Unauthorized`.
- Recovery happens only after a fresh login callback recreates the BFF session with `PUT /backend-internal/app/bff-session` and syncs the app session with `POST /api/app/session-sync`.
- Aggregate inspection of active BFF sessions does not show a current pattern of missing `refresh_token` values, so the issue is not simply "active sessions cannot refresh".

## Probable Root Cause
There is a continuity gap between the persisted BFF token session and the SSR bootstrap path.

During hard reload, the application can temporarily fail to translate an existing BFF session into a valid bearer-authenticated `session-bootstrap` request. Because `session-bootstrap` does not fall back to the existing app session, the reload path treats the user as unauthenticated and redirects to login, even though SSO is still active and can immediately restore the app state.

## Fix Specification
### Scope
Frontend and backend session/bootstrap continuity for protected Svelte routes.

### Required changes
1. Harden the hard-reload bootstrap path so recoverable authenticated state does not visibly fall through to login.
2. Make the BFF refresh and retry path deterministic before redirecting to login.
3. Add a safe continuity path when app session state is still valid but BFF bootstrap temporarily fails.
4. Keep this fix separate from the modular learner workspace reload bug.

### Non-goals
- No change to Keycloak realm settings or login UX beyond preventing the unnecessary bounce.
- No learner progression, submission, or unlock logic changes.
- No schema migration unless a minimal follow-up becomes strictly necessary.

## Files of interest
- `frontend/src/routes/+layout.server.ts`
- `frontend/src/lib/server/guards.ts`
- `frontend/src/lib/server/api.ts`
- `frontend/src/lib/server/session.ts`
- `backend/web/main.py`

## Acceptance Criteria
1. Hard reload on a protected page must not send users to login while active SSO and recoverable app/BFF state exist.
2. If the BFF access token is stale but refreshable, bootstrap must recover without a visible login interruption.
3. The current "login page bounce" followed by one-click recovery must no longer happen for this case.
4. The ticket and any related public artifacts must contain no PII, user identifiers, token values, or internal session identifiers.

## Test Scenarios
1. **Hard reload with active SSO**
- Given an already authenticated user on a protected learning page
- When the user performs a hard reload
- Then the page bootstraps successfully without redirecting to login

2. **Expired access token with valid refresh**
- Given an active BFF session whose access token is expired but refresh token is valid
- When SSR bootstrap runs on reload
- Then the BFF session refreshes and `session-bootstrap` succeeds without user-visible reauthentication

3. **App session continuity**
- Given a valid app session and active SSO
- When the BFF bootstrap path fails transiently during reload
- Then the user is not bounced through login if continuity can be recovered safely

4. **Regression**
- Given a truly expired or invalid session
- When the user reloads a protected page
- Then redirect to login still happens as before

## Risk Assessment
Medium. The bug sits on the authentication bootstrap boundary between Svelte SSR, the BFF token session, and the backend bearer gate. The fix must preserve security guarantees while removing false unauthenticated states during reload.

## Rollout Notes
- Validate on both learning and teaching protected pages.
- Verify immediate hard reload during an active session, not only long-idle cases.
- Confirm that truly expired sessions still redirect correctly.
- Confirm that a user with active SSO no longer sees the avoidable login bounce.
