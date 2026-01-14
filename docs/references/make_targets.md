# Make Targets (Developer Ergonomie)

Status: Stable

## Ziele
- `make up` – Dienste bauen/starten (web, keycloak, caddy)
- `make ps` – Statusübersicht (docker compose ps)
- `make reset-local` – Supabase DB reset + Env resync + Services recreate
- `make db-login-user` – Login‑User erstellen/aktualisieren (IN ROLE gustav_limited)
- `make test` – Unit/Integration
- `make test-supabase` – Supabase Storage Integration (`-m supabase_integration`)
- `make test-ollama` / `make test-ollama-vision` – Ollama Integration (`-m ollama_integration`)
- `make test-e2e` – E2E (`-m e2e`, startet Dienste + resynct Supabase env)
- `make verify` – Alles (Unit + Integrationen + E2E)
- `make supabase-status` – Supabase Status/URLs
- `make supabase-sync-env` – Schreibt aktuelle SUPABASE_URL + SERVICE_ROLE_KEY in `.env`

## ENV
- `APP_DB_USER`/`APP_DB_PASSWORD` – für DSNs/`db-login-user` (werden vom SQL‑Skript aus der Umgebung gelesen; keine Passwort‑Übergabe per CLI)
- `DB_HOST`/`DB_PORT` – für psql im Make‑Target
- `KEYCLOAK_ADMIN_PASSWORD` – für `make import-legacy*` (nicht als Flag übergeben)

## Hinweis (KISS)
- RUN_* Flags (`RUN_E2E`, `RUN_SUPABASE_E2E`, `RUN_OLLAMA_E2E`) immer zusammen mit den passenden Markern laufen lassen (`-m e2e` / `-m supabase_integration` / `-m ollama_integration`). Sonst mischt man bewusst „ohne externe Services“ mit „mit echten Services“ und bekommt vermeidbare Rotläufe.
