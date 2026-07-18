# Make Targets (Developer Ergonomie)

Status: Stable

## Ziele
- `make up` – Dienste bauen/starten (frontend, web, keycloak, caddy, h5p, learning-worker) inkl. lokaler `.tmp`-Vorbereitung und Caddy-CA-Helferdatei
- `make ps` – Statusübersicht (docker compose ps)
- `make reset-local` – Supabase DB reset + Services recreate (Hinweis: Keys rotieren; `.env` ggf. via `supabase status` aktualisieren)
- `make db-login-user` – Login‑User erstellen/aktualisieren (IN ROLE gustav_limited)
- `make learning-worker-db-login-user` – Worker-Login‑User erstellen/aktualisieren (dedizierte Worker-Rechte)
- `make test` – Unit/Integration
- `make verify-preflight-db` – Prüft vor `verify`, ob die lokale DB den erwarteten Schema-Stand hat (u. a. `unit_tasks_kind_check` inkl. `calliope`)
- `make test-h5p` – H5P Sidecar (Node) Unit-Tests
- `make test-supabase` – Supabase Storage Integration (`-m supabase_integration`)
- `make test-openai` – OpenAI-kompatibler Endpoint Smoke-Tests (`-m openai_integration`)
- `make test-e2e` – E2E (`-m e2e`, startet Dienste)
- `make verify` – deterministische harte Gates (DB-Preflight, Import/API/Architektur/Route/Docker-Smokes, Python-Tests, Frontend und H5P), ohne echte externe OpenAI-/Browser-E2E-Smokes
- `make dependency-audit` – Online-Prüfung der aktuellen npm-Advisories für Frontend und H5P; jeder Befund ab `low` schlägt fehl
- `make playwright-bootstrap` – installiert den von Playwright unterstützten Chromium-Browser für lokale visuelle Smokes
- `make test-visual-smoke` – prüft zuerst die Browserinstallation und führt danach die markierten produktnahen Chromium-Smokes aus
- `make test-full-prod-like` – vollständiges produktionsnahes Freigabeprofil (`verify` + Online-Dependency-Audit + Supabase-Smoke + OpenAI-Smoke + E2E + visueller Browser-Smoke)
- `make supabase-status` – Supabase Status/URLs
- `make docker-validate` – `docker compose config` (Syntax/ENV)
- `make import-legacy` – Legacy Dump importieren (lokal; schreibt Report nach `docs/migration/reports/`)
- `make import-legacy-dry` – Dry-Run des Legacy-Imports (keine Writes)
- `make keycloak-admin-sync` – Synchronisiert lokalen Keycloak-Admin-Client-Secret + Admin-Passwort gemäß `.env`
- `make keycloak-admin-reset` – Erzwingt Neuaufbau des lokalen Master-Admin-Users (guarded reset)

## ENV
- `APP_DB_USER`/`APP_DB_PASSWORD` – für DSNs/`db-login-user`
- `DB_HOST`/`DB_PORT`/`DB_SUPERUSER`/`DB_SUPERPASSWORD` – für psql im Make‑Target
- `DUMP`/`DSN`/`LEGACY_SCHEMA`/`WORKDIR` – Parameter für `import-legacy*`
- `KC_BASE_URL`/`KC_HOST_HEADER`/`KC_REALM`/`KC_ADMIN_USER`/`KC_ADMIN_PASS` – Keycloak Admin Lookup für `import-legacy*`
- `KEYCLOAK_ADMIN`/`KEYCLOAK_ADMIN_PASSWORD` – lokaler Master-Admin für E2E/Reset
- `KC_ADMIN_CLIENT_ID`/`KC_ADMIN_CLIENT_SECRET`/`KC_ADMIN_REALM` – Confidential Client für Admin-API-Sync

## Hinweis (KISS)
- RUN_* Flags (`RUN_E2E`, `RUN_SUPABASE_E2E`, `RUN_OPENAI_E2E`) immer zusammen mit den passenden Markern laufen lassen (`-m e2e` / `-m supabase_integration` / `-m openai_integration`). Sonst mischt man bewusst „ohne externe Services“ mit „mit echten Services“ und bekommt vermeidbare Rotläufe.
- Wenn `verify-preflight-db` fehlschlägt: zuerst `supabase migration up && make db-login-user` ausführen (alternativ `make reset-local`), dann `make verify` erneut starten.
