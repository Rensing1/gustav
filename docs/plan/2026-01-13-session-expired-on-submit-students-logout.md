# Plan: Session expires on submit (students get logged out)

Status: abgeschlossen (Hinweis ergänzt am 2026-02-12)
Stand: 2026-01-13 · Ticket: `docs/tickets/session-expired-on-submit-students-logout-2026-01-13.md`

## Why
- In Unterrichtssituationen bleiben Tabs oft >60 Minuten offen → beim Abgeben/Upload kommt `401`/Redirect und der Entwurf geht verloren.
- Root Cause ist eine **separate GUSTAV App-Session** (`gustav_session` + `public.app_sessions`) mit fixer Default-TTL `3600s`, unabhängig von Keycloak-SSO.

## User Story
- As a student, I want to submit solutions after a long-open tab (>2h) without being logged out, so that I don’t lose my work.

## Acceptance Criteria (aus Ticket)
- Nach >2h in geöffnetem Tab kann ein:e Schüler:in weiterhin abgeben, ohne Loginverlust (oder erhält eine klare Re-Login-Recovery ohne Datenverlust).
- `401`-Fehler führen nicht mehr zu „stillem“ Abbruch; UI zeigt handlungsfähige Recovery.

## BDD Scenarios (Given/When/Then)
### Backend (Session TTL)
1) Given `APP_SESSION_TTL_SECONDS=86400` (24h) and `GUSTAV_ENV=prod`, When `/auth/callback` creates a session, Then the `gustav_session` cookie has `Max-Age=86400`.
2) Given the default configuration (no `APP_SESSION_TTL_SECONDS` set), When a session is created, Then its TTL is **86400s** (24h).
3) Given `APP_SESSION_TTL_SECONDS` is invalid (non-integer / out of bounds), When the app starts, Then it falls back to a safe default and logs a warning (no crash, no insecure “infinite” session).

### UX (Recovery on 401)
4) Given a student is submitting and the backend returns `401 unauthenticated`, When the frontend receives the response, Then it guides to re-login (with return-to) and the student does not lose their draft text.
5) Given a student is preparing an upload-intent and the backend returns `401 unauthenticated`, When the frontend receives the response, Then it shows a clear “session expired” hint and redirects to re-login (with return-to).

## Design (minimal invasive)
### API Contract-First
- No OpenAPI change required: the backend already uses `401 {error:"unauthenticated"}` for `/api/*` when the app-session is missing/expired.
- If we later add explicit “return-to” parameters or new recovery endpoints, we update `api/openapi.yml` first.

### Configuration (Local = Prod)
- Introduce `APP_SESSION_TTL_SECONDS` (integer seconds).
- Default: **24h (86400s)** (decision: match typical “day-level” SSO expectations, still bounded).
- Bounds (defense-in-depth): e.g. min 900s, max 604800s (7d). Invalid values → fallback to default + warning log.

### Code Changes (targeted)
1) `backend/web/main.py`
   - Load `APP_SESSION_TTL_SECONDS` once at startup (small helper function).
   - Pass `ttl_seconds=...` into `SESSION_STORE.create(...)` in `/auth/callback`.
   - Cookie `Max-Age` stays derived from `sess.ttl_seconds` (so cookie and DB/in-memory session remain aligned).
2) `backend/web/main.py` (auth middleware UX)
   - Add **return-to** on unauthenticated redirects:
     - HTML: redirect to `/auth/login?redirect=<current_path>` for GET/HEAD.
       For non-idempotent requests (e.g. POST `/submit`), prefer the `Referer`
       page path to avoid returning to a POST-only endpoint (would 405 after login).
     - HTMX: set `HX-Redirect: /auth/login?redirect=<current_page_path>` using `HX-Current-URL` (fallback: request path).
   - Keep response semantics (`302` for HTML, `401` for HTMX/API) unchanged; only improve the redirect target.
3) `backend/web/static/js/gustav.js` (draft persistence)
   - Save draft **text + mode** to `sessionStorage` (decision: privacy-friendly; survives re-login redirects in the same tab).
   - Restore the draft on page load so a forced re-login does not discard the work.
   - Clear the draft after a successful submit (HTMX success or PRG `ok=submitted`).
4) `backend/web/static/js/gustav.js` + `backend/web/static/js/learning_upload.js` (401 recovery)
   - If an upload-intent request fails with `401`, show a clear hint and redirect to `/auth/login?redirect=<current_path>`.

### DB / Migration
- No schema change needed for the baseline fix (`expires_at` already exists).
- Sliding sessions are explicitly out of scope for this ticket.

## TDD Plan (Red → Green → Refactor)
1) Red: update/add tests so the bug is reproducible as a contract:
   - Update `backend/tests/test_auth_phase2_hardening.py` to assert Max‑Age matches `APP_SESSION_TTL_SECONDS` (instead of hard-coded 3600).
   - Add a small unit test for TTL parsing/bounds (invalid env → default).
   - Update `backend/tests/test_auth_middleware.py` to assert return-to behaviour:
     - HTML unauthenticated → `302 Location: /auth/login?redirect=/...`
     - HTMX unauthenticated (with `HX-Current-URL`) → `401` + `HX-Redirect` including `redirect=...`
2) Green: implement minimal code to satisfy the tests:
   - Add env parsing helper + wire TTL into `/auth/callback`.
   - Add return-to redirect building in middleware.
   - Implement minimal draft persistence + 401 recovery JS.
3) Refactor: keep it boring & readable:
   - Centralize the TTL default in one place.
   - Add a short English docstring explaining “why” and the security bounds.
   - Keep JS changes small and scoped to learning task forms.

## Rollout / Ops Checklist
- Set `APP_SESSION_TTL_SECONDS` in prod env (start with `86400`).
- Redeploy/restart web service.
- Observe logs for `401` on submit endpoints (`POST /learning/**/submit`, upload intents) and confirm the drop.
 - Manual smoke (student):
   - Type a longer draft → force logout (delete cookie) → click “Abgeben” → re-login → draft is restored on return.
   - Upload flow: trigger upload-intent with expired session → UI guides to re-login instead of failing silently.

## Risks / Security Notes
- Longer TTL increases the window for stolen-cookie misuse. Mitigations already in place: `HttpOnly`, `Secure`, `SameSite`, server-side session store, logout deletes DB record.
- Keep TTL bounded and configurable to match school policy.

## Open Questions (for Felix)
1) Default TTL: decided `24h` (86400s). Are the bounds (min/max) okay?
2) Storage for drafts: decided `sessionStorage`.
3) Upload drafts: decided to persist only `text+mode` (no upload metadata).
