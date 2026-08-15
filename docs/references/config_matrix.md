# Konfigurationsmatrix (Quelle der Wahrheit)

Status: Stable
Owner: Platform/App

| Service | Variable | Dev Default | Prod/Stage | Quelle | Wirkung |
|---|---|---|---|---|---|
| Web | GUSTAV_ENV | dev | prod/stage | env | Nur nicht-sicherheitskritische Flags (z. B. CSP-Lockerung in dev) |
| Web | DATABASE_URL | postgresql://gustav_app@127.0.0.1:54322/postgres | Secret | env/.env | App‑DSN (RLS) |
| Web | TEACHING_DATABASE_URL | =DATABASE_URL | Secret | env/.env | Repo DSN |
| Web | SESSION_DATABASE_URL | postgresql://postgres@supabase_db_gustav-alpha2:5432/postgres | Secret | env/.env | Sessions (Service Role) |
| Web | SERVICE_ROLE_DSN | postgresql://postgres@supabase_db_gustav-alpha2:5432/postgres | Secret | env/.env | Server-seitige Metadaten-Cleanups (z. B. Teaching-Storage) |
| Web | CLI_TOKENS_BACKEND | =SESSIONS_BACKEND | db | env/.env | Persistenz für opake CLI-Tokens |
| Web | WEB_BASE | https://app.localhost | FQDN | env/.env | Browser Base |
| Web | REDIRECT_URI | https://app.localhost/auth/callback | FQDN/callback | env/.env | OIDC Callback |
| KC | KC_BASE_URL | https://id.localhost | HTTPS FQDN | env/.env | IdP Base |
| KC | KC_PUBLIC_BASE_URL | https://id.localhost | HTTPS FQDN | env/.env | IdP Public |
| KC | KC_REALM | gustav | gustav | env/.env | Realm |
| KC/Worker | KC_SMTP_* | smtp.school.example / 587, STARTTLS=true | Relay-Secrets, STARTTLS zwingend | env/.env | Gemeinsames Relay für Keycloak-Systemmails und Kurs-Einladungen |
| Web/Worker | COURSE_INVITE_SIGNING_SECRET | CHANGE_ME… | Eigenständiges Secret, mindestens 32 zufällige Bytes | env/.env | Signatur und datensparsame HMAC-Digests für Klassenlinks |
| Supabase | SUPABASE_URL | http://127.0.0.1:54321 | FQDN | env/.env | Storage/API |
| Supabase | SUPABASE_SERVICE_ROLE_KEY | DUMMY_DO_NOT_USE | Secret | env/.env | Backend Storage |
| Web/H5P | H5P_INTERNAL_SHARED_SECRET | CHANGE_ME_DEV | Secret | env/.env | Interne Web→H5P-Authentifizierung für CLI-Paket-Workflows |

Hinweise:
- Compose nutzt für DSNs Service‑Namen (z. B. `supabase_db_gustav-alpha2`) statt 127.0.0.1.
- Der Webcontainer setzt `SERVICE_ROLE_DSN` bewusst auf den containerinternen
  Supabase-DB-Host und lässt diesen Wert nicht aus der Host-`.env`
  überschreiben. Host-DSNs wie `127.0.0.1:54322` sind für pytest auf dem Host
  gültig, aber im Container falsch.
- In Containern empfiehlt sich der interne Gateway-Dienst der Supabase-CLI
  (z. B. `http://supabase_kong_gustav-alpha2:8000`). Alternativ funktioniert
  weiterhin das Host-Gateway (`http://host.docker.internal:54321`), falls das
  Netzwerk noch nicht geteilt ist. Prüfe die verfügbaren Service-Namen per
  `docker network inspect supabase_network_gustav-alpha2`.
- Start‑Guard blockiert in PROD/Stage Logins als `gustav_limited`.
- Start‑Guard blockiert unsichere Keycloak‑URLs (http→Fehler); nutze https.
- Start‑Guard blockiert Dummy‑Schlüssel (`SUPABASE_SERVICE_ROLE_KEY=DUMMY_DO_NOT_USE`).
- `COURSE_INVITE_SIGNING_SECRET` darf nicht mit Session-, CSRF- oder SMTP-Secrets geteilt werden. Eine Rotation macht vorhandene Klassenlinks absichtlich ungültig.
- Der Kurs-Einladungsworker verweigert bei `KC_SMTP_STARTTLS=false` den Versand, bevor eine Nachricht geleast wird; diese Sicherheitsgrenze ist lokal und in Produktion identisch.
