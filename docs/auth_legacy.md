# GUSTAV Authentication (v1 – Supabase) and Migration Notes

This document describes how authentication and session management work in the current GUSTAV release (v1). It is intended to support the upcoming migration to a different auth framework (Keycloak) in GUSTAV v2 by providing a thorough, implementation‑level reference of the status quo.

## Scope

- Covers identity/auth provided by Supabase Auth (GoTrue), app‑level profiles, FastAPI Auth Service with HttpOnly cookies, and database session storage.
- Excludes authorization details for domain entities beyond a brief RLS overview (see ARCHITECTURE.md and SECURITY.md for broader context).

## Components Overview

- Supabase Auth (GoTrue): user registration, login, email verification, password reset.
- public.profiles: application profile linked to `auth.users` via UUID.
- Auth Service (FastAPI): issues/verifies sessions via HttpOnly cookies, stores sessions in Postgres.
- Database RPC & RLS: data access through SQL functions that validate sessions and enforce role‑based constraints.
- nginx: reverse proxy, integrates with Auth Service via `auth_request`.
- Streamlit app: uses Auth Service cookies; calls RPC functions with session context.

High‑level flow (simplified):

- Browser → nginx → Auth Service → Supabase Auth → DB `public.auth_sessions` → HttpOnly cookie

See also: `ARCHITECTURE.md:403`.

## Supabase Auth Configuration (GoTrue)

Primary configuration lives in `supabase/config.toml`:

- Enabled; base URL and allowed redirects: `supabase/config.toml:auth`.
- Token lifetime: `jwt_expiry = 5400` (90 minutes), refresh rotation enabled.
- Signups: `enable_signup = true`, anonymous sign‑ins disabled.
- Password policy: `minimum_password_length = 6` (requirements field currently empty).
- Email confirmations: enabled; SMTP configured via environment variables; templates in `supabase/templates/`.
- Rate limits: increased to accommodate classroom scenarios (e.g., `sign_in_sign_ups = 200`).
- OTP length/expiry for email flows (recovery/magic link) configured.

File references:
- `supabase/config.toml:auth` (JWT, rotation, signups, OTP, SMTP)
- `supabase/templates/confirmation.html`, `supabase/templates/recovery.html`, `supabase/templates/otp.html`

## User Model and Storage

### Identity (Supabase Auth)
- Canonical user is stored in `auth.users` (managed by Supabase). Typical fields include `id`, `email`, various confirmation timestamps, `app_metadata`, `user_metadata`, etc. See client model for a reference structure: `test_venv/lib/python3.12/site-packages/gotrue/types.py:200`.
- Passwords and password hashes are handled by Supabase Auth; no application table stores user passwords.

### Application Profile (`public.profiles`)
- Created on user signup via trigger on `auth.users`.
- Fields (initial + extensions):
  - `id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE`
  - `role user_role NOT NULL` where `user_role` enum = `student|teacher`
  - `full_name text` (optional), `email text` (added later)
  - `created_at timestamptz DEFAULT now()`, `updated_at timestamptz DEFAULT now()`
  - Indices: `idx_profiles_role`, `idx_profiles_email`
- Creation flow (trigger):
  - `public.handle_new_user()` inserts profile with default role `student` and copies `NEW.email`, with optional domain checks against `public.allowed_email_domains`.
- RLS:
  - Users can select/update only their own profile; insert handled by trigger; delete cascades from `auth.users`.

Key files:
- Schema: `supabase/migrations/20250408153120_initial_schema.sql:5`
- Add email: `supabase/migrations/20250416112404_fix_profile_email_and_course_links.sql`
- Trigger v1: `supabase/migrations/20250411073257_handle_new_user_trigger.sql`
- Trigger (domain restriction + email fix): `supabase/migrations/20250808095750_fix_handle_new_user_profile_fields.sql`
- RLS: `supabase/migrations/20250409111502_rls_policies.sql`

### Derived View (`profiles_display`)
- View adds a `display_name` computed from email/role to avoid storing redundant columns.
- File: `supabase/migrations/20250909090328_fix_display_name_and_missing_columns.sql`

## Password Hashing

- Passwords are stored and verified by Supabase Auth (GoTrue) inside `auth.users`.
- The repository does not store password hashes in application tables. The actual algorithm in use is provided by Supabase’s GoTrue (commonly bcrypt or argon2). The Supabase client models support both for imports/migrations (see `gotrue/types.py:password_hash`).
- To confirm the active algorithm at runtime, query `auth.users.encrypted_password` and inspect the prefix (`$2a|$2b` → bcrypt, `$argon2id$` → Argon2id) in an operational environment.

## Session Management (HttpOnly Cookies)

Sessions are stored in Postgres instead of Redis for simplicity and unified backups.

### Table: `public.auth_sessions`
- Columns: `id uuid`, `session_id varchar(255) UNIQUE`, `user_id uuid REFERENCES auth.users`, `user_email text`, `user_role text CHECK IN ('teacher','student','admin')`, `data jsonb`, `expires_at timestamptz`, `last_activity timestamptz`, `created_at timestamptz`, `ip_address inet`, `user_agent text`.
- Indices on `session_id`, `expires_at`, `user_id`, `last_activity`.
- RLS:
  - Authenticated users can select their own sessions (`auth.uid() = user_id`).
  - Service role policy for full access (used by backend service operations).
- Functions & triggers:
  - `cleanup_expired_sessions()` removes expired/inactive sessions.
  - `get_session_with_activity_update(session_id)` atomically updates last activity and extends expiry.
  - `enforce_session_limit` trigger caps concurrent sessions per user to 5.
  - `update_last_activity` trigger keeps `last_activity` fresh on updates.
  - Optional cron job via `pg_cron` (if available) to periodically clean up.

File: `supabase/migrations/20250906065856_auth_sessions_table.sql`

### Alternative Service Access
- Dedicated DB role `session_manager` can manage sessions without using the service role.
- API key table `public.auth_service_keys` (with `key_hash` intended to store bcrypt) + validation function to create sessions via API key guarded path.

File: `supabase/migrations/20250906070000_secure_session_management.sql`

## Auth Service (FastAPI)

A companion service that mediates between browser, nginx, and Supabase.

- Endpoints:
  - `POST /auth/login` – login with email/password, set HttpOnly cookie
  - `POST /auth/logout` – delete session and clear cookie
  - `GET /auth/verify` – for nginx `auth_request` to gate upstream routes
  - `POST /auth/refresh` – refreshes access tokens/sessions
  - `GET /auth/session/info` – returns session/user info
- Session policy:
  - 90‑minute sliding timeout, max 5 concurrent sessions per user, IP/User‑Agent tracked.
- Security:
  - HttpOnly + `Secure` cookies (in production), CSRF via Double‑Submit, SameSite to mitigate CSRF, rate limiting.
- Supabase usage:
  - Uses only Anon Key (no Service Role key) and calls SQL functions for secure operations.

References:
- Overview: `auth_service/README.md`
- Client calls for OTP and password update: `auth_service/app/services/supabase_client.py`
- Docker integration and env: `docker-compose.yml:auth`

## nginx Integration

- Uses `auth_request` to call `/auth/verify` before proxying to the app, and forwards user headers if needed.
- Example and details in `auth_service/README.md`.
- Compose wiring: service `nginx` depends on `auth` and `app` (`docker-compose.yml:nginx`).

## Streamlit App Integration

- App interacts with Supabase via RPC functions that internally validate session context. The Auth Service manages cookies; the app retrieves session info via service endpoints as needed.
- Core philosophy: “All data access through session‑validated RPC” to keep authorization in the database.

## Authorization & RLS (Brief)

- `public.profiles` and other domain tables enforce RLS; helper function `get_my_role()` returns role of current `auth.uid()`.
- Policies grant teachers vs students appropriate access in domain tables.

Reference: `supabase/migrations/20250409111502_rls_policies.sql`

## Password Reset & Email Flows

- OTP‑based flows (6‑digit codes) via Supabase Auth; templates in `supabase/templates/`.
- Auth Service wrappers coordinate `verify_otp` and `update_user(password)` calls using temporary sessions.
- SMTP configured via `supabase/config.toml` with secrets from environment.

Files:
- `supabase/templates/recovery.html`, `supabase/templates/otp.html`
- `auth_service/app/services/supabase_client.py`

## Security Considerations

- Cookies: HttpOnly, Secure (prod), SameSite policy.
- No secrets in repo; SMTP password and keys via environment (`.env`).
- Domain‑restricted registrations via `public.allowed_email_domains` in the `handle_new_user` trigger.
- PII‑safe logging helpers (hashing) available in utilities (see SECURITY.md section 17).
- RLS across tables; RPC functions validate session via DB before returning data.

References:
- `SECURITY.md`
- `supabase/migrations/*auth_sessions*`
- `supabase/config.toml`

## Operational Notes

- Health endpoints: `GET /health`, `/health/ready`, `/health/live` on Auth Service.
- Validate nginx config with `docker compose exec nginx nginx -t`.
- Token/Session timeouts aligned at 90 minutes by default (`jwt_expiry = 5400`).
- Session cleanup handled by function and optionally `pg_cron`.

## Known Limitations / Risks

- Tight coupling to Supabase Auth (GoTrue); password hashing algorithm specifics are opaque unless inspected at runtime.
- Domain restriction logic in trigger assumes `public.allowed_email_domains` is curated.
- API key validation function in `secure_session_management.sql` includes a warning (bcrypt comparison recommended in production).

## Migration to Keycloak (v2) – Considerations

This section outlines the primary areas to address when replacing Supabase Auth with Keycloak.

- Concept mapping:
  - Supabase `auth.users` → Keycloak Users in a Realm.
  - `public.profiles.role` (`student|teacher`) → Keycloak realm roles or client roles.
  - Email verification and password reset → Keycloak built‑in workflows.
- Passwords:
  - Plaintext passwords are not available; either
    - import hashed passwords if Keycloak supports the hashing algorithm and parameters (requires compatible import or custom provider), or
    - force password reset on first login post‑migration using email OTP/reset links.
- Sessions:
  - Replace DB‑backed `public.auth_sessions` with Keycloak tokens, or
  - Keep a lightweight session bridge: verify Keycloak JWTs server‑side and optionally persist session metadata to `public.auth_sessions` for activity tracking and rate limiting.
  - Update `/auth/verify` to validate Keycloak tokens (introspection or JWKS) and set user headers accordingly.
- Database RPC functions:
  - Today they assume a session id that maps to a user via SQL functions; in v2 consider:
    - Decode and validate Keycloak JWT in the Auth Service, then call RPC with an authenticated role and pass `auth.uid()` context via Postgres settings (e.g., `set_config`) or maintain a minimal session row that maps JWT subject → `user_id` for RLS.
  - Replace `validate_session_and_get_user(...)` (if present) with a Keycloak‑aware equivalent.
- Registration/domain restrictions:
  - Replicate domain allow‑list in Keycloak via custom validator or policy.
- Email delivery & templates:
  - Move from Supabase SMTP/templates to Keycloak’s email provider and templates.
- nginx integration:
  - Keep `auth_request`, but point it to updated Auth Service verification or adopt Keycloak Gatekeeper‑like patterns (or nginx‑lua/oidc if preferred).
- Data export plan:
  - Export users: `SELECT u.id, u.email, p.role, p.full_name, p.created_at FROM auth.users u JOIN public.profiles p ON p.id = u.id;`
  - Migrate profiles into Keycloak attributes/roles; maintain `public.profiles` for app until DB auth functions are refactored.
- Rollout strategy:
  - Pilot Realm with a subset of users; auto‑provision on first login if needed.
  - Enforce password reset if hashed import isn’t feasible.
  - Dual‑run period: keep Supabase Auth disabled once Keycloak is authoritative; switch Auth Service verification logic behind a feature flag.

### Aktueller Stand (Keycloak mit Bcrypt-Import)

- Beim Keycloak-Image wird das Apache-2.0-Plugin [`keycloak-bcrypt`](../keycloak/Dockerfile) eingebunden. Damit können vorhandene Bcrypt-Hashes geprüft werden.
- `keycloak/realm-gustav.json` aktiviert deklarative User Profiles: `display_name` ist Pflichtfeld, `firstName/lastName` sind ausgeblendet. Die Required Action `VERIFY_PROFILE` ist deaktiviert.
- Script `backend/tools/legacy_user_import.py` importiert Nutzer aus der Legacy-Datenbank (`legacy_import`). Es legt den Benutzer mit seinem Bcrypt-Hash an, weist Realm-Rollen zu und setzt `display_name` / `legacy_user_id` Attribute. Der Importer maskiert E‑Mails in Logs (PII‑Minimierung) und akzeptiert nur valide Host‑Header (Hostname[:Port]) für Admin‑Requests.
- Nach dem ersten Login rehashed Keycloak das Passwort automatisch gemäß der aktuellen Password Policy (`pbkdf2-sha512`).

Importer ausführen:

```bash
python -m backend.tools.legacy_user_import \
  --legacy-dsn postgresql://postgres:postgres@127.0.0.1:54322/legacy_import \
  --kc-base-url http://127.0.0.1:8100 \
  --kc-host-header id.localhost \
  --kc-admin-user gustav-admin \
  --kc-admin-pass '<ADMIN-PASSWORT>'
```

Optional: `--emails` (Whitelist) oder `--dry-run` (nur Ausgabe). Tests: `pytest -k legacy_user_importer`.

**Ablauf in Stichpunkten**

1. **Lesen**: Aus `legacy_import.auth.users` + `public.profiles` werden UUID, E-Mail, Rolle, optionaler Name und bcrypt-Hash geladen.
2. **Mapping**: `display_name` = `full_name` oder (Fallback) lokaler Teil der E-Mail; Attribute `legacy_user_id` / `display_name` werden gesetzt; optional vorhandene Nutzer werden gelöscht.
3. **Schreiben**: Keycloak-Admin-API (`admin-cli`) legt den Nutzer neu an, weist Realm-Rollen zu und speichert den bcrypt-Hash unverändert.
4. **Rehash beim Login**: Beim ersten Login prüft Keycloak den Hash via Plugin, schreibt ihn dann gemäß Password Policy (`pbkdf2-sha512`) um.

**Fehlerszenarien / Hinweise**

- Anzeige-Name im Web (DTO): Die Web‑Schicht bevorzugt den OIDC‑Claim `gustav_display_name` (aus dem Keycloak‑Attribut `display_name`). Falls nicht vorhanden, wird `name` (Standard‑Claim) genutzt; finaler Fallback ist der lokale Teil der E‑Mail. Dies wird in `/api/me` als `name` ausgeliefert.
- Mapper in `keycloak/realm-gustav.json`: Der Protocol‑Mapper „Display Name (gustav_display_name)“ exportiert das Attribut `display_name` als Claim `gustav_display_name` in ID‑, Access‑ und Userinfo‑Token. Der Importer setzt deshalb konsequent `display_name`.
- Sicheres Verhalten des Importers: Standardmäßig werden bestehende Nutzer nicht gelöscht. Mit `--force-replace` kann das Überschreiben bewusst aktiviert werden. HTTP‑Requests an die Admin‑API nutzen ein konfigurierbares Timeout (`--timeout`, Standard 5s).
- Host‑Header Sicherheit: `--kc-host-header` darf nur aus Zeichen `[A-Za-z0-9.-]` und optionaler Portangabe bestehen. Dies verhindert Header‑Injection.

- Unbekannte Rollen ⇒ Nutzer wird übersprungen und im Log vermerkt.
- Netz-/API-Fehler ⇒ Import stoppt mit Ausnahme (prozessuell über Retry oder Fortsetzung möglich).
- `--dry-run` eignet sich für einen Preview-Lauf; per `--emails` kann ein kleiner E-Mail-Ausschnitt getestet werden.
- Nach dem Import empfiehlt sich ein stichprobenartiger Login-Test sowie ein Blick auf `/admin/realms/gustav/users/<id>/credentials` (der Hash sollte nach dem Login `pbkdf2-sha512` sein).

## Quick References (Files)

- Supabase Auth config: `supabase/config.toml`
- Profile schema & RLS: `supabase/migrations/20250408153120_initial_schema.sql`, `20250409111502_rls_policies.sql`, `20250416112404_fix_profile_email_and_course_links.sql`
- New‑user trigger (+domain): `supabase/migrations/20250411073257_handle_new_user_trigger.sql`, `20250808095750_fix_handle_new_user_profile_fields.sql`
- Sessions: `supabase/migrations/20250906065856_auth_sessions_table.sql`, `20250906070000_secure_session_management.sql`
- Auth Service overview: `auth_service/README.md`
- Email templates: `supabase/templates/*`

---

For broader architecture, data flows, and security posture, see `ARCHITECTURE.md` and `SECURITY.md`.
