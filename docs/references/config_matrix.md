# Konfigurationsmatrix (Quelle der Wahrheit)

Status: Stable
Owner: Platform/App

| Service | Variable | Dev Default | Prod/Stage | Quelle | Wirkung |
|---|---|---|---|---|---|
| Web | GUSTAV_ENV | dev | prod/stage | env | Flags (Cookies, Headers) |
| Web | DATABASE_URL | postgresql://gustav_app@127.0.0.1:54322/postgres | Secret | env/.env | App‑DSN (RLS) |
| Web | TEACHING_DATABASE_URL | =DATABASE_URL | Secret | env/.env | Repo DSN |
| Web | SESSION_DATABASE_URL | postgresql://postgres@supabase_db_gustav-alpha2:5432/postgres | Secret | env/.env | Sessions (Service Role) |
| Web | WEB_BASE | http://app.localhost:8100 | FQDN | env/.env | Browser Base |
| Web | REDIRECT_URI | http://app.localhost:8100/auth/callback | FQDN/callback | env/.env | OIDC Callback |
| KC | KC_BASE_URL | http://id.localhost:8100 | HTTPS FQDN | env/.env | IdP Base (Prod: nur https) |
| KC | KC_PUBLIC_BASE_URL | http://id.localhost:8100 | HTTPS FQDN | env/.env | IdP Public (Prod: nur https) |
| KC | KC_REALM | gustav | gustav | env/.env | Realm |
| Supabase | SUPABASE_URL | http://127.0.0.1:54321 | FQDN | env/.env | Storage/API |
| Supabase | SUPABASE_SERVICE_ROLE_KEY | DUMMY_DO_NOT_USE | Secret | env/.env | Backend Storage |

Hinweise:
- Compose nutzt für DSNs Service‑Namen (z. B. `supabase_db_gustav-alpha2`) statt 127.0.0.1.
- Start‑Guard blockiert in PROD/Stage Logins als `gustav_limited`.
 - Start‑Guard blockiert in PROD/Stage unsichere Keycloak‑URLs (http→Fehler); nutze https.
 - Start‑Guard blockiert in PROD/Stage Dummy‑Schlüssel (`SUPABASE_SERVICE_ROLE_KEY=DUMMY_DO_NOT_USE`).
