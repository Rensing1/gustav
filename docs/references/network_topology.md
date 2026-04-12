# Netzwerk-Topologie

Status: Stable

## Übersicht
Client → Caddy (Reverse Proxy) → Frontend (SvelteKit Browser-BFF) / Web (FastAPI API) → DB/Keycloak/Supabase

## Hosts & Ports
- app.localhost → Caddy → gustav-frontend:3000 (default app shell)
- app.localhost `/api/*`, `/internal/*`, `/health` → Caddy → gustav-alpha2:8000 (Web/FastAPI)
- app.localhost `/h5p/*` → Caddy → gustav-h5p:3000
- id.localhost → Caddy → keycloak:8080
- DB (Compose): supabase_db_gustav-alpha2:5432

## Proxy-Vertrauen
- `GUSTAV_TRUST_PROXY=true` im Web, damit `X-Forwarded-*` sauber ausgewertet werden.
- Cookies: Immer `HttpOnly; Secure; SameSite=lax` (host‑only, kein `Domain=`).

## Fehlerbilder
- 502/Health down → Frontend oder Web nicht gestartet; häufig ist ein DSN falsch oder die Session‑DSN zeigt im Container auf `127.0.0.1`.
- 401 nach Login → Session‑Cookie nicht gesetzt (Domain/SameSite/Callback‑Host prüfen).
