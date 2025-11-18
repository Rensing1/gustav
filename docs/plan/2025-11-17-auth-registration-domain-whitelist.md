# Plan: Auth Registration Domain Whitelist (Keycloak)

Why
- Restrict self-service registration to school-owned email domains (DSGVO, Abuse-Prevention).
- Keep the rule simple, transparent and centrally configurable via `.env` (KISS).
- Align new behavior with the existing Keycloak-centered auth architecture (no local passwords).

User Story
- As a school administrator, I want students and teachers to register only with approved school email domains so that no private accounts (e.g. `@gmail.com`) can access GUSTAV.

BDD Scenarios (Given–When–Then)
- Happy Path (Allowed Domain)
  - Given `ALLOWED_REGISTRATION_DOMAINS=@gymalf.de` in `.env`
  - And a user opens `/auth/register?login_hint=alice@gymalf.de`
  - When the server validates the email domain
  - Then the request is redirected (302 or HX-Redirect) to Keycloak with `kc_action=register`
  - And no error banner is shown.
- Edge: No login_hint Provided
  - Given `ALLOWED_REGISTRATION_DOMAINS` is configured
  - And a user opens `/auth/register` without `login_hint`
  - When the server cannot validate a domain
  - Then the request is still redirected to Keycloak
  - And the domain check is deferred entirely to Keycloak policies.
- Edge: Mixed Case + Whitespace
  - Given `ALLOWED_REGISTRATION_DOMAINS` is set to `" @GymALF.de "`
  - And a user opens `/auth/register?login_hint=Bob@GYMalf.DE`
  - When the server normalizes domains (trim + lowercase)
  - Then the domain is treated as allowed
  - And the redirect proceeds as in the Happy Path.
- Error: Disallowed Domain in login_hint
  - Given `ALLOWED_REGISTRATION_DOMAINS=@gymalf.de`
  - And a user opens `/auth/register?login_hint=mallory@gmail.com`
  - When the server validates the email domain
  - Then the server DOES NOT redirect to Keycloak
  - And responds with a 400 error page or a small HTML screen
  - And the page shows the message: „Die Registrierung ist nur mit deiner IServ-Adresse (@gymalf.de) möglich.“
  - And no information about which domains are allowed is leaked in machine-readable form (only generic message for students).
- Error: Invalid Email Format in login_hint
  - Given `ALLOWED_REGISTRATION_DOMAINS=@gymalf.de`
  - And a user opens `/auth/register?login_hint=not-an-email`
  - When the server validates the email format
  - Then the server behaves like the "Disallowed Domain" case
  - And responds with a 400 error and no redirect to Keycloak.
- Security: Direct Access to Keycloak
  - Given Keycloak also enforces a domain restriction at the IdP level
  - When a user tries to register by directly opening the Keycloak registration URL
  - Then Keycloak rejects disallowed domains regardless of the GUSTAV pre-check.

Design/Contract (API Contract-First)
- `api/openapi.yml`
  - Document optional environment-driven behavior for `/auth/register`:
    - Add a short description note that the server MAY reject `login_hint` values whose domains are not in a configured allow-list.
  - Keep the HTTP contract simple:
    - 302 / 204 responses unchanged on success (redirect to IdP).
    - Introduce a 400 error response for invalid/disallowed `login_hint` with a generic `Error` payload.
- Environment (no code yet)
  - New variable `ALLOWED_REGISTRATION_DOMAINS`:
    - Comma-separated list of domains, each starting with `@` (initially `@gymalf.de`).
    - Evaluated in application code; Keycloak must still be configured separately to enforce the same rule.

TDD Plan (Red → Green)
1) Red
   - Add tests in `backend/tests/test_auth_register_domain_whitelist.py`:
     - Assert that allowed domains in `login_hint` lead to a redirect.
     - Assert that disallowed or invalid domains cause a 400 with `{"error": "invalid_email_domain"}` (or similar generic code).
     - Assert that missing `login_hint` keeps current redirect behavior.
     - Assert normalization of domains (case-insensitive, trimmed).
2) Green
   - Implement minimal parsing+validation of `ALLOWED_REGISTRATION_DOMAINS` and `login_hint` in `backend/web/routes/auth.py`:
     - Pure helper function for domain-checking (framework-agnostic, easy to unit-test).
     - Use existing FastAPI route for `/auth/register` and return either redirect or 400.
3) Refactor
   - Extract domain-parsing helper to a small, documented function (e.g. `parse_allowed_domains(env_value: str) -> set[str]`).
   - Ensure error responses reuse the existing `Error` schema and cache headers.

Open Questions / To Clarify with Felix
- Reicht eine einheitliche Info-Seite für alle Rollen (Schüler*innen und Lehrkräfte), die kurz auf Schul-/DSGVO-Vorgaben verweist?
