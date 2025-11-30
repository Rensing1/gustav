# Plan: Keycloak Login Theme — Reset Password Page & Remember‑me Checkbox

Why
- Schließen der UX-Lücke zwischen GUSTAV-Login/Registrierung und der „Neues Passwort setzen“-Seite von Keycloak.
- Sichtbar machen der bereits in Keycloak vorhandenen „Remember me“-Funktion im vereinfachten GUSTAV-Login-Theme.
- Sicherstellen, dass alle auth-relevanten Seiten (Login, Passwort vergessen, Passwort zurücksetzen) konsistent das GUSTAV-Branding und die Barrierefreiheitsprinzipien aus dem UI/UX-Leitfaden nutzen.

User Stories
- Reset Password Theme
  - As a student or teacher, I want the reset password page that opens from the email link to look like the GUSTAV login screen so that I can be sure I am still on the official school platform and not on a phishing site.
- Remember‑me Checkbox
  - As a frequent GUSTAV user, I want an optional “keep me signed in” checkbox on the login page so that I do not have to re-enter my password every time on my personal device, while still staying within the school’s security policies.

BDD Scenarios (Given–When–Then)

Reset Password Page (Update Password Flow)
- Happy Path: Reset Link → Themed Update Password Page
  - Given a user requested a password reset and received an email from Keycloak
  - And the email contains a secure link to the reset flow
  - When the user clicks the link
  - Then the browser opens a reset password page that uses the GUSTAV login theme (same logo, typography, button styles)
  - And the page clearly shows fields to enter and confirm a new password
  - And after a successful reset the user is redirected back to the GUSTAV app.
- Edge: Invalid or Expired Reset Link
  - Given a user opens an outdated or invalid reset link
  - When Keycloak detects that the action is no longer valid
  - Then the user sees a clear error message in the GUSTAV-styled layout
  - And the message explains that the link expired or is invalid
  - And the page offers a neutral way back to the login screen.
- Edge: Mismatching Password and Confirmation
  - Given the user is on the themed reset password page
  - And the user enters two different values into the password and confirmation fields
  - When the form is submitted
  - Then the page is re-rendered using the GUSTAV theme
  - And a clear, accessible error message is shown near the fields
  - And focus / screen reader behavior follows Keycloak’s default accessibility patterns.
- Security: No Local Password Handling in GUSTAV
  - Given all password reset logic is handled by Keycloak as the IdP
  - When the user sets a new password on the themed reset page
  - Then the new password is never logged or transmitted through the GUSTAV backend
  - And GUSTAV continues to rely on OIDC tokens only.

Remember‑me Checkbox (Login Page)
- Happy Path: Remember‑me Enabled in Realm
  - Given the Keycloak realm `gustav` has the “Remember me” feature enabled
  - And the GUSTAV login page uses the custom `login.ftl` template
  - When the user opens the login page
  - Then the page shows a checkbox with a clear label (e.g. “Angemeldet bleiben”) below the password field
  - And when the user ticks the checkbox and logs in
  - Then the IdP issues a longer-lived session according to Keycloak’s remember-me configuration.
- Happy Path: Remember‑me Disabled in Realm
  - Given the Keycloak realm `gustav` has “Remember me” disabled
  - When the user opens the login page
  - Then no remember‑me checkbox is rendered
  - And the login page layout remains visually balanced and aligned with the UI/UX guidelines.
- Edge: Keyboard-Only Navigation
  - Given a user navigates the login form using only the keyboard
  - When the Tab key is used to move focus through the fields
  - Then the tab order visits email, password, remember‑me checkbox (if present), and the login button in a logical sequence
  - And each interactive element has a visible focus state.
- Edge: Screen Reader Labels
  - Given a user relies on a screen reader
  - When the focus moves to the remember‑me checkbox
  - Then the screen reader announces a meaningful label (e.g. “Angemeldet bleiben”)
  - And the checkbox behaves as a standard HTML checkbox.
- Security: Shared Devices
  - Given some devices are shared (e.g. in computer labs)
  - When a user logs in on a shared device
  - Then the remember‑me checkbox should default to unchecked
  - And any help text or documentation should remind users to only use “stay signed in” on personal devices.

Design/Contract (API & Schema)
- `api/openapi.yml`
  - No new REST endpoints or request/response payloads are required for these tickets.
  - All changes happen inside the Keycloak login theme (`login.ftl` and new reset/update-password template).
  - Contract-First Check:
    - Verify that existing `/auth/login`, `/auth/forgot`, `/auth/register` remain unchanged.
    - Add a short note in the documentation section (if needed) that password resets and “Remember me” are implemented fully on IdP level (Keycloak) and are reflected in the login theme.
- Database / Supabase Migrations
  - No new tables, columns or constraints are needed.
  - Session behavior for “Remember me” is controlled by Keycloak session and token lifetimes, not by GUSTAV’s own schema.
  - Migration Plan:
    - No SQL migration file for this change set.
    - Ensure existing documentation (`docs/references/user_management.md`) clearly states that app sessions and IdP sessions can have different lifetimes, and that “Remember me” only extends the IdP side.

TDD Plan (Red → Green)
1) Red — Theme Contract Tests
   - Extend `backend/tests/test_keycloak_theme_files.py`:
     - Add presence check for the new update-password template (e.g. `update-password.ftl` or similar), accepting either root or `templates/` subfolder as with other templates.
     - Add assertions that the template uses the same CSS hooks as `login.ftl` (`kc-card`, `kc-title`, `kc-form`, `kc-label`, `kc-input`, `kc-submit`, `kc-message`).
     - Add tests that `login.ftl` contains a correctly wired remember‑me checkbox block guarded by `${realm.rememberMe}`, using a semantic `<input type="checkbox" name="rememberMe">` and a `<label>` with the standard message key.
     - Extend message bundle tests to require `rememberMe=` keys in `messages_de.properties` and `messages_en.properties`.
2) Green — Minimal Theme Implementation
   - Create the new reset/update-password FTL template in the login theme:
     - Copy layout skeleton from `login.ftl` or `login-reset-password.ftl`.
     - Insert Keycloak’s standard fields for new password and confirmation, using our `kc-*` CSS classes.
   - Update `login.ftl` to render the remember‑me block only if `realm.rememberMe` is enabled:
     - Follow Keycloak’s default template structure but adapt to the simplified GUSTAV layout.
   - Add translations for `rememberMe` to both message bundles (`messages_de.properties`, `messages_en.properties`).
3) Refactor — Clarity, Accessibility, Docs
   - Review the new templates for readability and alignment with `docs/UI-UX-Leitfaden.md` (minimalism, clear hierarchy, focus states).
   - Add short comments in the FTL files where non-obvious Keycloak variables or conditions are used to help learners understand the template logic.
   - Extend `docs/references/user_management.md` or `docs/plan/auth_*` docs with a brief note about how “Remember me” interacts with IdP sessions and the app cookie.

Status (2025-11-30)
- Noch offen (RED-Phase geplant)
  - Reset/Update-Password-Seite nutzt in Prod noch das Standard-Keycloak-Layout.
  - Die „Remember me“-Checkbox wird im GUSTAV-Login-Theme nicht angezeigt, selbst wenn das Feature im Realm aktiviert ist.
- Dieses Plan-Dokument definiert die nächsten Schritte:
  - Kein neues API- oder DB-Schema, Fokus auf Keycloak-Theme und Dokumentation.
  - Testgetriebene Ergänzung von Templates, i18n-Keys und Layout-Anpassungen.

Open Questions / To Clarify with Felix
- Bezeichnung für die Checkbox:
  - Ist „Angemeldet bleiben“ die bevorzugte deutsche Formulierung oder gibt es schulische Vorgaben (z. B. „Auf diesem Gerät angemeldet bleiben“)?
- Hinweise für geteilte Geräte:
  - Soll im UI (z. B. kleiner Text unter der Checkbox) ein expliziter Hinweis erscheinen, diese Funktion nur auf privaten Geräten zu nutzen, oder reicht eine Dokumentation im Lehrer- bzw. Admin-Handbuch?
- Passwort-Reset-UX:
  - Gibt es Wünsche für zusätzliche Hinweise auf der Update-Password-Seite (z. B. kurze Erinnerung an Schulpasswortrichtlinien), oder sollen wir möglichst nahe am schlanken Standard bleiben?

