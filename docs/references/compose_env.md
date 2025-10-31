# Compose & ENV Vereinheitlichung

Status: Stable

## Prinzip
- Container verwenden Service‑Namen statt 127.0.0.1 für DB/Keycloak.
- DSNs im Container werden aus `APP_DB_USER/APP_DB_PASSWORD` gebaut.

## Beispiel (docker-compose.yml)
```yaml
environment:
  - APP_DB_USER=${APP_DB_USER:-gustav_app}
  - APP_DB_PASSWORD=${APP_DB_PASSWORD:-CHANGE_ME_DEV}
  - DATABASE_URL=postgresql://${APP_DB_USER}:${APP_DB_PASSWORD}@supabase_db_gustav-alpha2:5432/postgres
  - TEACHING_DATABASE_URL=${TEACHING_DATABASE_URL:-postgresql://${APP_DB_USER}:${APP_DB_PASSWORD}@supabase_db_gustav-alpha2:5432/postgres}
  - SESSION_DATABASE_URL=${SESSION_DATABASE_URL:-postgresql://postgres:postgres@supabase_db_gustav-alpha2:5432/postgres}
```

## Anti‑Pattern
- `SESSION_DATABASE_URL=postgresql://...@127.0.0.1:54322/postgres` im Container → Verbindungsfehler.

