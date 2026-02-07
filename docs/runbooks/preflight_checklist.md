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

## DB-Datenintegrität (Learning)
- Ziel: Vor Deploy sicherstellen, dass `learning_submissions.section_id` konsistent ist.
- Pflichtcheck 1 (Null-Werte):
  - `psql "$SERVICE_ROLE_DSN" -c "select count(*) as missing_section_id from public.learning_submissions where section_id is null;"`
  - Erwartung: `0`
- Pflichtcheck 2 (Task/Submission-Mismatch):
  - `psql "$SERVICE_ROLE_DSN" -c "select count(*) as section_mismatch from public.learning_submissions ls join public.unit_tasks t on t.id = ls.task_id where ls.section_id <> t.section_id;"`
  - Erwartung: `0`
- Pflichtcheck 3 (auflösbare Task-Referenzen vor Backfill):
  - `psql "$SERVICE_ROLE_DSN" -c "select count(*) as missing_task_reference from public.learning_submissions ls left join public.unit_tasks t on t.id = ls.task_id where t.id is null;"`
  - Erwartung: `0`
- Wenn einer der Checks > `0` ist:
  - Deploy/Migration stoppen.
  - Erst Daten bereinigen, dann Preflight erneut ausführen.
  - Recovery-Schritt A (fehlende `section_id` nachziehen):
    - `psql "$SERVICE_ROLE_DSN" -c "update public.learning_submissions ls set section_id = t.section_id from public.unit_tasks t where ls.task_id = t.id and ls.section_id is null;"`
  - Recovery-Schritt B (`missing_task_reference` > 0):
    - Betroffene Submission-`task_id`s ermitteln und Legacy-Mapping korrigieren, bevor `supabase migration up` erneut gestartet wird.

## DSNs / ENV
- Host‑DSN (Host‑Tests): `postgresql://$APP_DB_USER:$APP_DB_PASSWORD@127.0.0.1:54322/postgres`
- Container‑DSN (Compose): `postgresql://$APP_DB_USER:$APP_DB_PASSWORD@supabase_db_gustav-alpha2:5432/postgres`
- SESSION_DATABASE_URL zeigt im Container auf den DB‑Service‑Host.

## Smoke‑Tests
- `.venv/bin/pytest -q` (Unit/Integration) → grün
- `RUN_E2E=1 .venv/bin/pytest -q -m e2e` → grün

## Tools
- `scripts/preflight.sh` für automatisierte Aggregation der Checks.

## CI-spezifische Hinweise
- CI-Läufer stellen eine aktuelle Node.js-Version bereit, damit die
  JS-Behaviour-Tests für die Teaching-Live-UI (`backend/web/static/js/gustav.js`)
  nicht dauerhaft übersprungen werden (`pytest`-Skip bei fehlendem `node`).
