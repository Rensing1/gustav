# E2E How‑To

Status: Stable

## Voraussetzungen
- `make up` (startet web + keycloak + caddy + h5p + worker)
- Nach `supabase db reset`: `make reset-local` (Key/Env resync + Services werden neu erstellt)
- `.env` mit korrekten `KC_BASE`/`WEB_BASE`/`KC_REALM`/`KEYCLOAK_ADMIN_PASSWORD` und docker-intern erreichbarem `SESSION_DATABASE_URL`

## Ausführen
```bash
make test-e2e
# oder manuell:
# RUN_E2E=1 .venv/bin/pytest -q -m e2e
```

## Typische Fehler
- Health 502/Timeout → Web nicht erreichbar (Logs prüfen: `docker compose logs -n 200 web`).
- 500 bei `/auth/callback` → Session-DB nicht erreichbar (`SESSION_DATABASE_URL` zeigt fälschlich auf `127.0.0.1:54322` im Container).
- 401 bei `/api/me` → meist Folgefehler von `/auth/callback` (Cookie wird nicht gesetzt).
