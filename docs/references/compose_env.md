# Compose & ENV Vereinheitlichung

Status: Stable

## Prinzip
- Container verwenden Service‑Namen statt 127.0.0.1 für DB/Keycloak.
- Web/App-DSNs werden aus `APP_DB_USER/APP_DB_PASSWORD` gebaut.
- Der Learning-Worker verwendet getrennte Credentials über `LEARNING_WORKER_DB_USER` / `LEARNING_WORKER_DB_PASSWORD`.
- Web und Learning-Worker verwenden den Backend-Code aus dem gebauten Image. Das verbindliche Compose-Profil mountet keinen Host-Quellcode nach `/app/backend`.
- Ein noch nicht erreichbarer Supabase-Stack führt zu `503` Readiness; die Runtime wechselt niemals implizit auf flüchtige In-Memory-Daten.

## Beispiel (docker-compose.yml)
```yaml
environment:
  - APP_DB_USER=${APP_DB_USER:-gustav_app}
  - APP_DB_PASSWORD=${APP_DB_PASSWORD:-CHANGE_ME_DEV}
  - DATABASE_URL=postgresql://${APP_DB_USER}:${APP_DB_PASSWORD}@supabase_db_gustav-alpha2:5432/postgres
  - LEARNING_DATABASE_URL=${LEARNING_DATABASE_URL:-postgresql://${APP_DB_USER}:${APP_DB_PASSWORD}@supabase_db_gustav-alpha2:5432/postgres}
  - LEARNING_WORKER_DB_USER=${LEARNING_WORKER_DB_USER:-gustav_worker}
  - LEARNING_WORKER_DB_PASSWORD=${LEARNING_WORKER_DB_PASSWORD:-CHANGE_ME_DEV}
  - LEARNING_WORKER_DATABASE_URL=${LEARNING_WORKER_DATABASE_URL:-postgresql://${LEARNING_WORKER_DB_USER}:${LEARNING_WORKER_DB_PASSWORD}@supabase_db_gustav-alpha2:5432/postgres}
  - TEACHING_DATABASE_URL=${TEACHING_DATABASE_URL:-postgresql://${APP_DB_USER}:${APP_DB_PASSWORD}@supabase_db_gustav-alpha2:5432/postgres}
  - SESSION_DATABASE_URL=${SESSION_DATABASE_URL:-postgresql://postgres:postgres@supabase_db_gustav-alpha2:5432/postgres}
```

## Anti‑Pattern
- `SESSION_DATABASE_URL=postgresql://...@127.0.0.1:54322/postgres` im Container → Verbindungsfehler.
