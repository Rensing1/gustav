# E2E How‑To

Status: Stable

## Voraussetzungen
- `docker compose up -d keycloak web` (oder `make up`)
- `.env` mit korrekten KC_BASE/WEB_BASE/REALM/ADMIN

## Ausführen
```bash
RUN_E2E=1 .venv/bin/pytest -q -m e2e
```

## Typische Fehler
- Health 502/Timeout → Web nicht gestartet (DSN/Session‑DSN prüfen).
- 401 bei /api/me → Kein Set‑Cookie (Cookie‑Flags/Host prüfen).

