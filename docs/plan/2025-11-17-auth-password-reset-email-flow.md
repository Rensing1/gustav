# Plan: Auth Password Reset via Email (Keycloak Redirect UX)

Why
- Align user expectations from GUSTAV v1 (Supabase: Email-Reset) mit dem neuen Keycloak-basierten Flow.
- Bieten eine klare, einfache UX für „Passwort vergessen?“ ohne eigene Passwortspeicherung in GUSTAV.

User Story
- As a student, I want to easily reset my GUSTAV password via my school email address so that I can regain access without asking the admin for manual intervention.

BDD Scenarios (Given–When–Then)
- Happy Path: Reset Link from Login Page
  - Given the login page shows a link „Passwort vergessen?“
  - And the link points to `/auth/forgot`
  - When the user clicks the link
  - Then the browser is redirected (302) to the Keycloak reset-credentials page
  - And Keycloak sends a password reset email to the user (IdP responsibility).
- Happy Path: Reset with Prefilled Email
  - Given a user typed an email address into a small form on the GUSTAV login screen
  - And the app calls `/auth/forgot?login_hint=alice@schule.de`
  - When the server handles the request
  - Then the browser is redirected to the Keycloak reset-credentials page with the email prefilled
  - And GUSTAV does not store the email locally.
- Edge: Invalid Email Format in login_hint
  - Given `/auth/forgot` receives `login_hint=not-an-email`
  - When the server builds the redirect URL
  - Then the server either omits `login_hint` or passes it as-is
  - And Keycloak performs the real validation
  - And GUSTAV still returns 302 with `Cache-Control: private, no-store`.
- Edge: No login_hint Provided
  - Given a user visits `/auth/forgot` directly
  - When the server handles the request
  - Then the server redirects to Keycloak without `login_hint`
  - And the user can enter the email address on the IdP page.
- Security: Rate Limiting & Enumeration
  - Given password reset email flows can be abused for account enumeration or spam
  - When `/auth/forgot` is triggered many times
  - Then GUSTAV SHOULD NOT reveal whether an email exists
  - And primary rate limiting should be implemented in Keycloak / reverse proxy
  - And responses from `/auth/forgot` remain generic 302 redirects.

Design/Contract (API Contract-First)
- `api/openapi.yml`
  - `/auth/forgot` is already documented as redirect to Keycloak reset page.
  - Clarify in description that:
    - GUSTAV does not send emails itself.
    - `login_hint` is optional and only used to prefill the IdP form.
  - Keep responses as currently defined (302 with `Cache-Control: private, no-store`).

TDD Plan (Red → Green)
1) Red
   - Extend existing tests in `backend/tests/test_auth_register_nonce.py` or add a new `backend/tests/test_auth_forgot_flow.py`:
     - Assert that `/auth/forgot` always returns 302 with `Cache-Control: private, no-store`.
     - Assert that, when `login_hint` is provided, the outgoing URL contains a properly encoded `login_hint` query parameter.
     - Assert that GUSTAV does not validate email syntax (Keycloak’s job) beyond safe URL encoding.
2) Green
   - Keep current implementation in `backend/web/routes/auth.py` for `/auth/forgot` and adjust only where tests demand stronger encoding or header guarantees.
3) Refactor
   - Ensure that the Keycloak base URL and realm are read consistently from `OIDC_CFG` (already the case).
   - Add small docstring explaining that password reset is delegated to Keycloak and that no local password logic exists.

Status (2025-11-18)
- Implementiert
  - `/auth/forgot` leitet konsistent per 302 mit `Cache-Control: private, no-store` zur Keycloak-Reset-Page weiter.
  - `login_hint` wird URL-encodiert an Keycloak durchgereicht; GUSTAV validiert die E-Mail nicht (Validierung ist IdP-Aufgabe).
  - SMTP ist auf Keycloak-Seite über Env (`KC_SPI_EMAIL_SENDER_DEFAULT_*`) und `smtpServer` im `realm-gustav.json` verkabelt; Passwort wird ausschließlich aus der Umgebung geladen.
  - Keycloak verschickt Passwort-Reset-E-Mails grundsätzlich korrekt, sobald SMTP-Auth und Relay auf dem Mailserver eingerichtet sind (aktuell: `550 relay not permitted` bei Test-E-Mails an externe Adressen).
- Offene Punkte / Abweichungen vom Ideal
  - Beim Klick auf den Reset-Link in der E-Mail wird der Nutzer aktuell direkt zum Client (`gustav-web`) weitergeleitet, ohne sichtbares Formular „Neues Passwort setzen“. In Tests blieb das alte Passwort unverändert.
  - Der Keycloak-Flow „reset credentials“ ist in der UI standardkonform konfiguriert (inkl. „Reset Password“), die Ursache liegt also im IdP-Verhalten (nicht im GUSTAV-Code).
  - Für Prod bedeutet das: Der „Passwort vergessen?“-Flow funktioniert zuverlässig als E-Mail-basierter Login-/Action-Link, ein tatsächliches Zurücksetzen des Passworts sollte vorerst weiterhin über das Keycloak-Admin-Portal bzw. „Execute Actions › UPDATE_PASSWORD“ erfolgen.
  - Zur vollständigen Umsetzung der User Story ist ein separates Keycloak-Debugging (Event-Logs, ggf. Upstream-Docs/Bugreports) nötig; GUSTAV-seitig sind API, Redirects und E-Mail-Konfiguration bereits prod-fähig.

Open Questions / To Clarify with Felix
- Soll die Login-Seite ein kleines Formular für die E-Mail erfassen oder nur einen simplen „Passwort vergessen?“-Link anbieten (KISS)?
- Soll es im Lehrer-Dashboard Hinweise geben, wie Schüler ihr Passwort selbst zurücksetzen können (z.B. Hilfe-Text)?
- Gibt es besondere Vorgaben der Schule für Passwort-Komplexität, oder wird dies komplett IdP-seitig geregelt?
