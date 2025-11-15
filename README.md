# GUSTAV alpha‑2 – Moderne Lernplattform

KI‑gestützte Lernplattform mit FastAPI und HTMX. Server‑seitiges Rendern (SSR) mit eigenen Python‑Komponenten.

## Schnellstart

- Voraussetzungen: Docker & Docker Compose, Ports `80/443` frei
- Start: `docker compose build && docker compose up`
- Öffnen (Reverse Proxy aktiv): `https://app.localhost`
- Entwicklung: Live‑Reload für `backend/web` ist aktiv
- Nützlich: `docker compose up -d`, `docker compose logs -f`, `docker compose down`

## Projektstruktur (Kurz)

```
gustav-alpha2/
├── api/                 # OpenAPI-Vertrag
├── backend/web/         # FastAPI, SSR, Komponenten, Static
├── docs/                # Architektur, Pläne, Leitfäden
├── docker-compose.yml
└── Dockerfile
```

## Tests

- Ausführen: `.venv/bin/pytest -q`

## Storage (Supabase)

- Private Buckets: `materials` (Teaching) und `submissions` (Learning) werden per SQL‑Migration provisioniert (privat, nur signierte URLs).
- Zentrale Konfiguration (ENV):
- `SUPABASE_URL` und `SUPABASE_SERVICE_ROLE_KEY` (nur Backend, niemals im Browser)
- `SUPABASE_PUBLIC_URL` (Browser-Facing Host, z. B. `https://app.localhost`, wird für signierte URLs/Proxy-Checks verwendet)
  - `SUPABASE_STORAGE_BUCKET` (Default `materials`)
  - `LEARNING_STORAGE_BUCKET` (Default `submissions`; Legacy-Setups dürfen weiterhin `LEARNING_SUBMISSIONS_BUCKET` setzen – der Wert wird als Fallback gelesen)
  - `MATERIALS_MAX_UPLOAD_BYTES` (Default 20971520 = 20 MiB)
  - `LEARNING_MAX_UPLOAD_BYTES` (Default 10485760 = 10 MiB)
  - Optional (nur für gezielte lokale E2E): `AUTO_CREATE_STORAGE_BUCKETS=true` erlaubt temporär Auto‑Provisioning. In regulären Setups immer `false`; der Startschutz (Prod‑Guard) verhindert unsichere Prod‑Konfigurationen.

- Hinweis: Falls signierte URLs im lokalen Umfeld interne Hosts enthalten, kann `SUPABASE_REWRITE_SIGNED_URL_HOST=true` gesetzt werden. Nur in Dev/Test nutzen; in Prod/Stage bleibt der Wert strikt `false`.

Schlüssel (storage_key) – Konventionen:
- Teaching: `materials/{unit_id}/{section_id}/{material_id}/{uuid}.{ext}`
- Learning: `submissions/{course_id}/{task_id}/{student_sub}/{epoch_ms}-{uuid}.{ext}`

Siehe auch: `docs/references/storage_and_gateway.md` und Plan `docs/plan/storage-bucket-unification.md`.

## Lokale KI (Ollama/DSPy)

- Standard ist `AI_BACKEND=local` (prod‑tauglich). Für reine CI kann `stub` verwendet werden; Prod/Stage starten nicht mit `stub`.
- Echte Rückmeldungen (DSPy/Ollama) erhältst du mit `AI_BACKEND=local`
  sowie korrekt gesetzten `AI_FEEDBACK_MODEL` und `OLLAMA_BASE_URL`. Bleibt
  das Flag auf `stub`, liefert der Worker deterministische Platzhalter. Prod/Stage verweigern seit 2025‑11 den Start mit `stub` (Fail‑fast).
- Default‑Modelle:
  - Vision: `AI_VISION_MODEL=qwen2.5vl:3b`
  - Feedback: `AI_FEEDBACK_MODEL=gpt-oss:latest`
  Passe sie nur an, wenn du die Modelle lokal bereits gepullt hast.
- Für lokale Inferenz (nur dev/staging):
  - Compose stellt `ollama` bereit (interner Port 11434). Env in `learning-worker` bereits verdrahtet (`OLLAMA_BASE_URL=http://ollama:11434`).
  - Modelle ziehen (die IDs wählst du selbst, z. B. `AI_FEEDBACK_MODEL=<modell>`):
    - `docker compose exec ollama ollama pull ${AI_VISION_MODEL}`
    - `docker compose exec ollama ollama pull ${AI_FEEDBACK_MODEL}`
  - Worker auf „local“ umschalten (nur wenn Modelle vorhanden):
    - In `.env`: `AI_BACKEND=local`
    - Neustart: `docker compose up -d --build`
  - Sicherheit: Keine Cloud‑Egress. Logs enthalten keine PII; nur IDs/Fehlercodes/Timings.

### Ollama‑Integrationstests (optional)

- Standard: aus. Aktiviere explizit, nur gegen lokale Hosts.
- Vorbereitung (Modelle ziehen – verwende die in `.env` definierten Modell-IDs):
  - `docker compose exec ollama ollama pull ${AI_FEEDBACK_MODEL}`
  - `docker compose exec ollama ollama pull ${AI_VISION_MODEL}` (für Vision)
- Komfort‑Shortcuts (empfohlen):
  - Nur Konnektivität/Feedback: `make test-ollama`
  - Mit Vision‑Pfad: `make test-ollama-vision`
    - Beide Targets setzen `RUN_OLLAMA_E2E=1` und `OLLAMA_BASE_URL=http://localhost:11434` automatisch.
- Alternativ manuell:
  - `export RUN_OLLAMA_E2E=1`
  - Optional Vision: `export RUN_OLLAMA_VISION_E2E=1`
  - Host setzen: `export OLLAMA_BASE_URL=http://localhost:11434`
  - Feedback‑Konnektivität: `pytest -q -m ollama_integration`
  - Vision‑Pfad: `pytest -q -m ollama_integration -k vision`
- Sicherheit: Tests akzeptieren nur `localhost`, `127.0.0.1` oder `ollama` als Host. Bei fehlenden Modellen/Verbindung wird mit Anleitung geskippt.

### GPU (optional) Hinweise
- Standardmäßig verwendet `docker-compose` das CPU-kompatible Image `ollama/ollama:latest`, damit alle Hosts starten.
- Für AMD‑GPU/ROCm setze `OLLAMA_IMAGE=ollama/ollama:rocm` (oder einen passenden Tag) und stelle sicher, dass `/dev/kfd` und `/dev/dri` gemountet werden können.
- Gruppen: `video`, `render` werden weiterhin hinzugefügt; stelle sicher, dass der Host‑User GPU‑Zugriff hat.
- Optionale Env‑Tuning:
  - `HIP_VISIBLE_DEVICES=all` (Default) oder z. B. `0`
  - `HSA_OVERRIDE_GFX_VERSION` nur setzen, wenn dein Stack es erfordert (sonst leer lassen)

## Contributing

- Arbeitsweise: Contract‑First, TDD (Red‑Green‑Refactor)
- Bitte Hinweise in `docs/ARCHITECTURE.md` und `docs/plan/README.md` beachten
- Branch‑Strategie: `development` (aktiv), PRs gegen `development`
- Repo-Hygiene: `.gitignore` schließt u. a. `*.bak`/`.env` aus; bitte keine Secrets commiten.

## Healthcheck

- `GET /health` → `{ "status": "healthy" }`

## Dokumentation

- Architektur: `docs/ARCHITECTURE.md`
- Glossar: `docs/glossary.md`
- Bounded Contexts: `docs/bounded_contexts.md`
- UI/UX: `docs/UI-UX-Leitfaden.md`
- Datenbank: `docs/database_schema.md`
- Lizenz: `docs/LICENCE.md`

## Identity & Sessions (Kurzüberblick)

- IdP: Keycloak (OIDC Authorization Code Flow mit PKCE)
- Session‑Cookie: `gustav_session` (HttpOnly, Secure, SameSite=lax)
- Umgebungsvariablen:
  - `GUSTAV_ENV`: steuert nur wenige nicht‑sicherheitskritische Aspekte (z. B. CSP‑Lockerung in dev); Cookies sind stets Secure+SameSite=lax.
  - `SESSIONS_BACKEND`: `memory` (Default) oder `db` (Postgres/Supabase)
  - `DATABASE_URL` (oder `SUPABASE_DB_URL`): DSN für DB-gestützte Sessions
- `WEB_BASE`: Browser‑sichtbare Basis‑URL der App (z. B. `https://app.localhost`)
- `REDIRECT_URI`: Muss auf `/auth/callback` der App zeigen (z. B. `https://app.localhost/auth/callback`);
  wird zur Berechnung des App‑Basis‑URLs genutzt (Logout‑Redirect)
- `KC_BASE_URL` (bevorzugt) bzw. `KC_BASE` (Legacy): Öffentliche Basis‑URL von Keycloak. Für Proxys `KC_PUBLIC_BASE_URL` setzen.

### Directory (Users API) — Admin‑Client

- Für `/api/users/search` und `/api/users/list` nutzt GUSTAV einen vertraulichen Admin‑Client (Client‑Credentials) gegen Keycloak:
  - `KC_ADMIN_REALM` (Default `master`)
  - `KC_ADMIN_CLIENT_ID` (z. B. `gustav-admin-cli`)
  - `KC_ADMIN_CLIENT_SECRET` (nicht commiten; nur Server‑Side!)
- Der Client benötigt minimale `realm-management` Rollen (z. B. `view-users`, `query-users`).
- Legacy‑Fallback (nur dev): `KC_ADMIN_USERNAME`/`KC_ADMIN_PASSWORD` (Password‑Grant) ist weiterhin möglich, in Produktion aber zu vermeiden.

### E2E-Hosts, TLS und Cookies

- Cookies sind hostgebunden. Für eine stabile E2E-Anmeldung müssen Web‑Host und Cookie‑Host übereinstimmen.
- Standard‑Setup (Reverse‑Proxy `Caddyfile`, TLS intern):
- App: `https://app.localhost`
- Keycloak: `https://id.localhost`
- E2E-Tests leiten `WEB_BASE` automatisch aus `REDIRECT_URI` ab (wenn `WEB_BASE` nicht gesetzt ist) und nutzen `KC_BASE` bzw. `KC_PUBLIC_BASE_URL`.
- Empfehlung: Setze vor E2E‑Läufen explizit
- `export WEB_BASE=https://app.localhost`
- `export KC_PUBLIC_BASE_URL=https://id.localhost`

### Lokales TLS vertrauen (Caddy)

- Der Reverse Proxy terminiert TLS lokal (Port 443). Browser können beim ersten Start warnen.
- Importiere die lokale Caddy‑Root‑CA ins Betriebssystem‑Trust‑Store, damit TLS‑Prüfung in Browsern und Tools (requests/curl) funktioniert.
  - Alternativ für CLI/Tests: `export REQUESTS_CA_BUNDLE=.tmp/caddy-root.crt` bzw. `export CURL_CA_BUNDLE=.tmp/caddy-root.crt`.
- Services im Compose‑Netz sprechen intern unverschlüsselt (z. B. `http://keycloak:8080` für `KC_BASE_URL` in Containern).

## Sicherheits‑Defaults (dev = prod)

- TLS/HSTS: Immer aktiv über den Caddy‑Proxy (HSTS max‑age=31536000; includeSubDomains)
- CSRF: Strikt für alle Schreib‑Routen (Origin/Referer müssen server‑gleich sein)
- Cookies: Immer `Secure` + `SameSite=lax` + `HttpOnly` (host‑only, kein `Domain=`)
- Caching: Private/no‑store auf sensitiven Antworten; `Vary: Origin`
- Diagnostik: Keine clientseitigen Diagnose‑Header; optionale Server‑Logs via Flags


## Persistenz (Keycloak‑Accounts)

- Keycloak nutzt nun denselben PostgreSQL‑Stack wie die App: Compose stellt dafür
  den Service `keycloak-db` (PostgreSQL 16) bereit.
- Konfiguration über `.env`:
  - `KC_DB=postgres`
  - `KC_DB_URL=jdbc:postgresql://keycloak-db:5432/keycloak`
  - `KC_DB_USERNAME`, `KC_DB_PASSWORD` (Dev‑Defaults `keycloak`/`keycloak`)
  - `KC_DB_URL_PROPERTIES=sslmode=disable` (für Prod auf `sslmode=require`/TLS anpassen)
- Der Erststart importiert den Realm `gustav`, danach verwaltet Keycloak alle Daten
  direkt in PostgreSQL. Neustarts sowie Rebuilds erhalten Benutzer und Konfiguration.
- `depends_on.condition=service_healthy` sorgt dafür, dass Keycloak erst nach
  erfolgreichem `pg_isready` gegen den Datenbankdienst hochfährt.
- Produktion: Binde `KC_DB_URL` an eine gemanagte Postgres‑Instanz (TLS, Backups, Secret‑Store).
