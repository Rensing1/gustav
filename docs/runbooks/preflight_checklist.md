# Preflight Checklist (Hardware/Env)

Status: Stable
Owner: Ops/Platform

## Ziel
Vor Inbetriebnahme validieren, dass alle Abhängigkeiten erreichbar und korrekt konfiguriert sind.

## Checks (schnell)
- Dienste laufen: `docker compose ps`
- Supabase lokal: `supabase status`
- Health: `curl -s -D- $WEB_BASE/health | head -20` → `200` + `Cache-Control: no-store`
- Keycloak OIDC: `curl -s -o /dev/null -w '%{http_code}\n' $KC_BASE/realms/$KC_REALM/.well-known/openid-configuration` → `200`

## DB/Rollen
- Login-User vorhanden und Mitglied der App-Rolle:
  - `psql -h <DB_HOST> -U <LOGIN_USER> -c "select pg_has_role(current_user, 'gustav_limited', 'member');"` → `t`
- App-Rolle NOLOGIN: `\du gustav_limited` → `No Login`

## DSNs / ENV
- Host‑DSN (Host‑Tests): `postgresql://$APP_DB_USER:$APP_DB_PASSWORD@127.0.0.1:54322/postgres`
- Container‑DSN (Compose): `postgresql://$APP_DB_USER:$APP_DB_PASSWORD@supabase_db_gustav-alpha2:5432/postgres`
- SESSION_DATABASE_URL zeigt im Container auf den DB‑Service‑Host.

## Smoke‑Tests
- `.venv/bin/pytest -q` (Unit/Integration) → grün
- `RUN_E2E=1 .venv/bin/pytest -q -m e2e` → grün

## Tools
- `scripts/preflight.sh` für automatisierte Aggregation der Checks.

