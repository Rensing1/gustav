# Make Targets (Developer Ergonomie)

Status: Stable

## Ziele
- `make up` – Dienste bauen/starten (web, keycloak, caddy)
- `make ps` – Statusübersicht (docker compose ps)
- `make db-login-user` – Login‑User erstellen/aktualisieren (IN ROLE gustav_limited)
- `make test` – Unit/Integration
- `make test-e2e` – E2E (RUN_E2E=1)
- `make supabase-status` – Supabase Status/URLs

## ENV
- `APP_DB_USER`/`APP_DB_PASSWORD` – für DSNs/`db-login-user` (werden vom SQL‑Skript aus der Umgebung gelesen; keine Passwort‑Übergabe per CLI)
- `DB_HOST`/`DB_PORT` – für psql im Make‑Target
- `KEYCLOAK_ADMIN_PASSWORD` – für `make import-legacy*` (nicht als Flag übergeben)
