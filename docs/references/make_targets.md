# Make Targets (Developer Ergonomie)

Status: Stable

## Ziele
- `make up` – Dienste bauen/starten (web, keycloak, caddy)
- `make ps` – Statusübersicht (docker compose ps)
- `make reset-local` – Supabase DB reset + Services recreate (Hinweis: Keys rotieren; `.env` ggf. via `supabase status` aktualisieren)
- `make db-login-user` – Login‑User erstellen/aktualisieren (IN ROLE gustav_limited)
- `make test` – Unit/Integration
- `make test-h5p` – H5P Sidecar (Node) Unit-Tests
- `make test-supabase` – Supabase Storage Integration (`-m supabase_integration`)
- `make test-openai` – OpenAI-kompatibler Endpoint Smoke-Tests (`-m openai_integration`)
- `make test-e2e` – E2E (`-m e2e`, startet Dienste)
- `make verify` – Alles (Unit + Integrationen + E2E)
- `make supabase-status` – Supabase Status/URLs
- `make docker-validate` – `docker compose config` (Syntax/ENV)

## ENV
- `APP_DB_USER`/`APP_DB_PASSWORD` – für DSNs/`db-login-user`
- `DB_HOST`/`DB_PORT`/`DB_SUPERUSER`/`DB_SUPERPASSWORD` – für psql im Make‑Target

## Hinweis (KISS)
- RUN_* Flags (`RUN_E2E`, `RUN_SUPABASE_E2E`) immer zusammen mit den passenden Markern laufen lassen (`-m e2e` / `-m supabase_integration`). Sonst mischt man bewusst „ohne externe Services“ mit „mit echten Services“ und bekommt vermeidbare Rotläufe.
