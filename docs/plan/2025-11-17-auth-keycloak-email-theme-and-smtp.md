# Plan: Keycloak Email Theme & SMTP for GUSTAV

Why
- Enable registration confirmation and password reset emails without storing passwords or SMTP logic in GUSTAV itself.
- Ensure all auth-related emails are branded, DSGVO-konform and understandable for students and teachers.
- Keep configuration consistent across local and production deployments (`lokal = prod`).

User Story
- As a school administrator, I want GUSTAV to send clearly branded registration and password reset emails via our school mail server so that students and teachers can self-service account activation and password resets in a secure and predictable way.

BDD Scenarios (Given–When–Then)
- Happy Path: Registration Confirmation Email
  - Given `verifyEmail=true` is enabled in the `gustav` Keycloak realm
  - And SMTP is correctly configured for the realm
  - And a user completes the registration form via `/auth/register` → Keycloak
  - When Keycloak creates the account
  - Then a registration confirmation email is sent to the user
  - And the email uses the GUSTAV email theme (subject, logo/branding, explanatory text).
- Happy Path: Password Reset Email
  - Given `resetPasswordAllowed=true` in the `gustav` realm
  - And SMTP is correctly configured
  - And a user triggers `/auth/forgot` or clicks „Passwort vergessen?“ on the login page
  - When Keycloak processes the reset request
  - Then a password reset email is sent to the user with a time-limited link
  - And the email uses the same GUSTAV email theme.
- Edge: SMTP Misconfiguration
  - Given the SMTP configuration in Keycloak is invalid (wrong host, credentials, or port)
  - When a registration or password reset email should be sent
  - Then Keycloak logs an error and the user sees a generic error message on the IdP page
  - And GUSTAV itself does not expose SMTP details or internal error messages.
- Edge: Local vs Production
  - Given local and production environments use the same SMTP variables from `.env` (Host `gymalf.de`, Port `587`, User `hennecke`)
  - When a developer tests registration and password reset flows locally
  - Then the same Keycloak email flows work without Codeänderungen
  - And switching to a mail catcher is possible by overriding only the SMTP ENV values (optional, not required).

Design/Contract (Architecture & Config)
- Responsibility split
  - Keycloak sends emails and renders templates (email theme).
  - GUSTAV stays a pure OIDC client; it does not send auth emails and does not know SMTP credentials.
- Keycloak Realm Configuration
  - Realm `gustav`:
    - Set `verifyEmail=true` for mandatory email confirmation after registration (soll Standardverhalten sein).
    - Keep `resetPasswordAllowed=true` for password reset flow.
    - Configure `emailTheme="gustav"` to use the custom theme.
  - SMTP settings (via environment or admin UI, values kommen aus `.env`):
    - Host/Port/User an das bestehende Schul-Setup angelehnt:
      - `KC_SMTP_HOST=gymalf.de`
      - `KC_SMTP_PORT=587` (STARTTLS)
      - `KC_SMTP_USER=hennecke`
    - Passwort nur als Secret in der Umgebung:
      - `KC_SMTP_PASSWORD=` (wird in `.env` gesetzt, bleibt im Repo leer).
    - Absenderadresse und Anzeigename:
      - `KC_SMTP_FROM=hennecke@gymalf.de`
      - `KC_SMTP_FROM_NAME="GUSTAV-Lernplattform"`
- Email Theme (Keycloak)
  - Extend existing theme under `keycloak/themes/gustav`:
    - Add HTML templates under `email/html/`:
      - `email-verification.ftl` for registration confirmation.
      - `password-reset.ftl` for reset emails.
    - Optionally add plain-text variants under `email/text/` for clients that prefer text-only emails.
  - Use a single shared HTML layout (logo, colors, typography, footer) for all email types and vary only:
    - Subject line and main text (via `messages_{locale}.properties`, z.B. `messages_de.properties`), in a friendly, neutral tone (gleiche Formulierungen für Schüler*innen und Lehrkräfte).
    - The call-to-action label and target link (Keycloak-provided URL).
    - A simple footer with school name and a contact line such as „Bei Fragen melde dich unter: hennecke@gymalf.de“.
  - Verwende ein einheitliches Template für alle Rollen; neue Nutzer*innen starten als „student“, die Lehrer-Rolle wird später manuell vergeben.
- GUSTAV App Contract
  - No changes to `api/openapi.yml` endpoints are required for email sending itself.
  - Auth endpoints (`/auth/register`, `/auth/forgot`) remain pure redirects; documentation may reference that emails are sent by the IdP (Keycloak).

TDD / Validation Plan (Red → Green)
1) Red: Configuration and Theme Presence
   - Add a small documentation-oriented test or check script (if feasible) that:
     - Verifies that the `gustav` theme contains the expected email templates (paths exist).
     - Optionally parses `realm-gustav.json` to ensure `emailTheme` is set to `gustav` in test fixtures.
   - For app-level integration tests:
     - Ensure existing auth e2e tests for `/auth/register` and `/auth/forgot` still pass when `verifyEmail=true`.
2) Green: Implement Email Theme & Realm Settings
   - Create the email templates and localization files under `keycloak/themes/gustav/email/...`.
   - Update the Keycloak realm config (JSON or Admin UI) to set `emailTheme="gustav"` and configure SMTP (via environment variables in Docker Compose).
   - Introduce environment variables in `docker-compose.yml` and `.env.example` for SMTP settings (without hardcoding secrets in the repo).
3) Refactor / Hardening
   - Document the setup clearly in a dedicated runbook (`docs/runbooks/`), including:
     - Required DNS and SPF/DKIM/DMARC steps for the school domain.
     - How to test emails locally with a mail catcher.
   - Keep theme logic simple and KISS-compliant (no complex dynamic content; focus on clear instructions for students).

Open Questions / To Clarify with Felix
- Gibt es schulweite Vorgaben für Corporate Design (Logo, Farben) in E-Mails, die wir in den HTML-Templates berücksichtigen müssen?
- Soll zusätzlich eine technische Kontaktadresse/Support-Adresse im Footer genannt werden (z.B. IT-Support der Schule)?
