# 2026-01-11 – Prod-like Local Setup für E2E (dev=prod) + Fail-Fast

Status: abgeschlossen

## Hintergrund / Problem
- Die E2E-Tests rufen `https://app.localhost/*` (Web) und `https://id.localhost/*` (Keycloak) über Caddy auf.
- Wenn der `web`-Container in `GUSTAV_ENV=prod` wegen fehlender Secrets/Guards neu startet, liefert Caddy oft `502` → jeder E2E-Test wartet bis zu ~60s und bricht dann erst ab.
- Zusätzlich braucht der Web-Container für server-to-server OIDC (Token-Exchange) TLS-Trust für das lokale Caddy-Root-CA-Zertifikat.

## Ziel
- Lokal so prod-nah wie möglich testen:
  - `GUSTAV_ENV=prod` aktiv (Startup-Guards laufen wirklich)
  - Keycloak Admin API in prod-like Mode via `client_credentials` (kein password grant in der App)
  - TLS-Verifikation innerhalb von Containern möglich (Caddy CA wird vertraut)
- E2E-Suite soll schnell und deterministisch scheitern, wenn Abhängigkeiten nicht ready sind (Fail-Fast statt 60s pro Test).

## Lösung (KISS)
### 1) `.env` automatisch synchronisieren (wie Supabase-Key-Sync)
- `scripts/sync_prod_env.py` setzt gezielt prod-like Variablen (ohne Secrets zu drucken) und ruft Sync-Helfer auf:
  - `scripts/sync_caddy_ca.py`: kopiert Caddy-Root-CA nach `.tmp/caddy-root.crt` und setzt Permissions so, dass der non-root `web`-Container lesen kann.
  - `scripts/sync_supabase_env.py`: aktualisiert `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` nach `supabase db reset`.
  - `scripts/sync_keycloak_env.py`: provisioniert/liest ein Confidential Client Secret für Admin-API und schreibt `KC_ADMIN_CLIENT_SECRET` in `.env`.
- Alle Änderungen an `.env` bleiben lokal (Datei ist gitignored); es wird eine `.env.bak` angelegt.

### 2) Container-to-Host DNS korrekt (dev=prod)
- `docker-compose.yml` setzt für `web`:
  - `extra_hosts`: `app.localhost` und `id.localhost` → `host-gateway`, damit Container die öffentlichen TLS-Endpunkte erreichen.
  - `REQUESTS_CA_BUNDLE`/`KEYCLOAK_CA_BUNDLE` + Mount für `.tmp/caddy-root.crt`, damit TLS-Verifikation in der App funktioniert.

### 3) Fail-Fast vor E2E
- `scripts/wait_for_e2e_ready.py` prüft einmalig vor der Suite:
  - `WEB_BASE/health`
  - `KC_BASE/realms/<realm>/.well-known/openid-configuration`
  - `WEB_BASE/h5p/healthz`
- Timeout steuerbar via `E2E_READY_TIMEOUT_S` (Make setzt kurz, z. B. 20s).

### 4) E2E-Timeouts konfigurierbar
- In den H5P-E2E-Tests wird das bisherige harte `timeout_s=60` über `E2E_READY_TIMEOUT_S` überschreibbar gemacht.

## Make-Workflows (Soll)
- `make prod-sync-env`:
  - Aktualisiert `.env` prod-like inkl. CA/Supabase/Keycloak-Sync.
- `make test-e2e`:
  - Startet Services, sync’t `.env`, recreatet `web`, führt Fail-Fast-Ready-Check aus, dann `pytest -m e2e`.
- `make verify`:
  - Führt Unit/Integration + Supabase + Ollama + E2E durch.

## Risiken / offene Punkte
- CA-File-Mount: bind-mount eines einzelnen Files kann bei „replace-by-rename“ tricky sein; wir umgehen das praktisch durch `--force-recreate web` nach dem Sync.
- Keycloak-Startzeit: `sync_keycloak_env.py` muss ggf. retryen, bis Keycloak hinter Caddy erreichbar ist.
- TLS-Warnings in Host-Tests (requests verify=False) sind kosmetisch; optional später „CA auch für Tests verwenden“.

## Fortschritt
- 2026-01-11: Implementierung der Sync-Skripte, docker-compose Anpassungen, Fail-Fast-Ready-Check und Make-Targets; E2E-Lauf via `make test-e2e` verifiziert.
