# Observability & Triage

Status: Stable

## Endpunkte/Checks
- Web: `GET /health` → 200 + `Cache-Control: no-store`.
- Keycloak OIDC: `/.well-known/openid-configuration` → 200.
- DB Rollen: `select pg_has_role(current_user,'gustav_limited','member');` → t.

## Logs (typische Muster)
- 500 bei `/auth/callback` + psycopg OperationalError → `SESSION_DATABASE_URL` falsch (127.0.0.1 im Container).
- 401 bei `/api/me` nach Login → Kein Set-Cookie, prüfen Cookie‑Flags/Host.
- FATAL/NOLOGIN → Versuchte Verbindung als `gustav_limited`.

## Erste Hilfe
- `docker compose ps`, `docker logs gustav-alpha2 --tail=200`.
- `supabase status` (DB/Storage Reachability).
- `psql`‑Probe mit Login‑User.

