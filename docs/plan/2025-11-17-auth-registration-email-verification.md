# Plan: Auth Registration Email Verification Awareness (Keycloak)

Why
- Ensure that only email-verified accounts can effectively use GUSTAV (compliance, classroom control).
- Make the verification state transparent in the UI without duplizierten E-Mail-Flows in GUSTAV (Keycloak bleibt Quelle der Wahrheit).

User Story
- As a teacher, I want that only students with verified school email addresses can log in to GUSTAV so that I can rely on their identity and avoid misuse of unverified accounts.

BDD Scenarios (Given–When–Then)
- Happy Path: Verified Email
  - Given a user has completed email verification in Keycloak (`email_verified=true`)
  - And the user logs in via `/auth/login` and `/auth/callback`
  - When GUSTAV validates the ID token
  - Then a normal session is created
  - And `/api/me` returns the usual `Me` DTO
  - And the UI behaves unchanged.
- Error: Unverified Email (Block Login)
  - Given a user exists in Keycloak with `email_verified=false`
  - And the user attempts to log in via `/auth/login` and `/auth/callback`
  - When GUSTAV inspects the token claims
  - Then GUSTAV DOES NOT create a session
  - And the user is redirected to a small info page that explains that the email must be verified first
  - And the page shows the message: „Bitte bestätige zuerst deine E-Mail-Adresse. Überprüfe dafür dein E-Mail-Postfach.“
  - And the response contains no sensitive details (generic error).
- Alternative: Soft Warning Only (No Enforcement)
  - Given `EMAIL_VERIFICATION_REQUIRED=false` in `.env`
  - And a user logs in with `email_verified=false`
  - When GUSTAV inspects the token claims
  - Then a normal session is created
  - And the UI may show a small non-blocking banner recommending email verification
  - And `/api/me` remains unchanged.
- Edge: Missing email_verified Claim
  - Given Keycloak does not provide `email_verified` in ID tokens for some clients
  - And a user logs in
  - When GUSTAV inspects the token claims and finds no `email_verified`
  - Then GUSTAV treats the user as verified (backwards compatible default)
  - And no additional error is shown.
- Security: Direct Access & Logout
  - Given a user is blocked due to `email_verified=false`
  - When the user later verifies the email and retries login
  - Then GUSTAV accepts the token and creates a session without extra admin steps.

Design/Contract (API Contract-First)
- `api/openapi.yml`
  - Option A (Blocking behavior)
    - Extend `/auth/callback` description to mention that the server MAY reject ID tokens where `email_verified=false` if `EMAIL_VERIFICATION_REQUIRED=true`.
    - Add a 400 response variant with `Error` payload (e.g. `error: email_not_verified`) documenting the behavior.
  - `Me` DTO remains unchanged by design (privacy-first; no email field, no verification flag exposed to clients).
- Environment
  - New variable `EMAIL_VERIFICATION_REQUIRED`:
    - Boolean flag; in real deployments default `true` (email verification is mandatory).
    - When `true`, GUSTAV blocks creation of sessions for `email_verified=false`.

TDD Plan (Red → Green)
1) Red
   - Add tests in `backend/tests/test_auth_email_verification.py`:
     - Simulate ID tokens with `email_verified=true` and `email_verified=false` (using existing test stubs or fakes).
     - Assert that, with `EMAIL_VERIFICATION_REQUIRED=true`, only verified tokens lead to created sessions and redirect 302.
     - Assert that unverified tokens yield 400 with `{ "error": "email_not_verified" }` (or similar).
     - Assert that missing `email_verified` keeps login working (graceful fallback).
2) Green
   - Implement minimal claim check in `/auth/callback` path in `backend/web/main.py`:
     - Read `EMAIL_VERIFICATION_REQUIRED` from environment.
     - If required and `claims.get("email_verified") is False`, return 400 with the existing `Error` schema and `Cache-Control: private, no-store`.
3) Refactor
   - Optionally extract a small pure helper (e.g. `is_email_verified(claims, required: bool) -> bool`) to keep callback route focused on flow control.

Open Questions / To Clarify with Felix
- Soll die Lehrer-UI später zusätzliche Auswertungen oder Statistiken zu „E-Mail bestätigt ja/nein“ bekommen, obwohl nicht-verifizierte Accounts bereits am Login scheitern?
