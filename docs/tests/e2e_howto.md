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
# RUN_E2E=1 E2E_VERIFY_TLS=1 REQUESTS_CA_BUNDLE=.tmp/caddy-root.crt .venv/bin/pytest -q -m e2e
```

Hinweis: `make test-e2e` führt vor Pytest automatisch `make keycloak-admin-sync` aus.
Damit werden driftende lokale Keycloak-Admin-Credentials (Snapshot/Import-Nachlauf)
auf den `.env`-Zustand zurückgeführt.

Die E2E-Suite akzeptiert keine unverschlüsselt beziehungsweise ohne Zertifikatsprüfung aufgebauten HTTPS-Verbindungen. `make test-e2e` kopiert die lokale Caddy-Root-CA nach `.tmp/caddy-root.crt` und setzt die erforderlichen TLS-Variablen. Ein manueller Lauf ohne `E2E_VERIFY_TLS=1` oder ohne nichtleeres CA-Bundle bricht vor der Testausführung mit einer Handlungsanweisung ab.

Für die visuellen Playwright-Smokes wird einmalig `make playwright-bootstrap` ausgeführt. `make test-visual-smoke` prüft den Chromium-Browser vor dem Start und meldet den Bootstrap-Befehl frühzeitig, statt erst am Ende des produktnahen Profils zu scheitern.

## Typische Fehler
- Health 502/Timeout → Web nicht erreichbar (Logs prüfen: `docker compose logs -n 200 web`).
- 500 bei `/auth/callback` → Session-DB nicht erreichbar (`SESSION_DATABASE_URL` zeigt fälschlich auf `127.0.0.1:54322` im Container).
- 401 bei `/api/me` → meist Folgefehler von `/auth/callback` (Cookie wird nicht gesetzt).
