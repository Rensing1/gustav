# Netzwerk-Topologie

Status: Stable

## Übersicht
Client → Caddy (Reverse Proxy) → Web (FastAPI) → DB/Keycloak/Supabase

## Hosts & Ports
- app.localhost:8100 → Caddy → gustav-alpha2:8000 (Web)
- id.localhost:8100 → Caddy → keycloak:8080
- DB (Compose): supabase_db_gustav-alpha2:5432

## Proxy-Vertrauen
- `GUSTAV_TRUST_PROXY=true` im Web, damit `X-Forwarded-*` sauber ausgewertet werden.
- Cookies: Dev `SameSite=lax`, Prod `SameSite=strict`, `Secure` nur in Prod.

## Fehlerbilder
- 502/Health down → Web nicht gestartet (DSN falsch, Session‑DSN auf 127.0.0.1 im Container).
- 401 nach Login → Session‑Cookie nicht gesetzt (Domain/SameSite/Callback‑Host prüfen).

