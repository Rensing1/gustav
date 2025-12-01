# GUSTAV – KI‑gestützte Lernplattform für Schulen

GUSTAV (**G**USTAV **u**nterstützt **S**chüler **t**adellos **a**ls **V**ertretungslehrer) ist eine KI-gestützte Lernplattform, die ich für den Einsatz in meinem eigenen Unterricht an einer weiterführenden Schule einsetze. Damit verfolge ich konkret zwei Ziele:
1. Schüler erhalten für ihre Aufgaben zeitnahes pädagogisches Feedback.
2. Lehrer erhalten einen schnellen Überblick über den Lernstand einer Klasse.
Weitere Funktionalitäten (z. B. Karteikarten, Datenvisualisierung) sind geplant, aber die Umsetzung ist neben den anderen unterrichtsbezogenen Aufgaben recht zeitintensiv. Über Unterstützung bin ich daher recht dankbar!

--- 

## Schnellstart (lokale Demo)
**Voraussetzungen**
- aktuelle Linux-Distribution
- Docker & Docker Compose
- Supabase
- Ports `80` und `443` sind frei (für `https://app.localhost`)

**Demo in wenigen Schritten starten**
```bash
git clone https://github.com/Rensing1/gustav.git gustav
cd gustav

cp .env.example .env
# Für eine lokale Demo reichen die Default-Werte.
# Für eine echte Schul-Installation siehe docs/runbooks/deploy_new_system.md

supabase init
supabase start
docker compose up -d --build
```

Dann im Browser öffnen:
- App: `https://app.localhost`
- (Keycloak-Login ist im Demo-Setup vorkonfiguriert; Details siehe `docs/runbooks/deploy_new_system.md`.)
Für eine produktionsnahe Installation auf einem Schulserver nutze bitte das Runbook:
- `docs/runbooks/deploy_new_system.md`

---

## Projektstruktur (Überblick)

Ein kurzer Blick in die wichtigsten Verzeichnisse:

- `api/` – OpenAPI-Vertrag (API-Definition)
- `backend/web/` – FastAPI-App, serverseitig gerenderte UI, HTMX-Komponenten
- `backend/learning-worker/` – Hintergrundprozesse für automatische Auswertung & KI-Feedback
- `supabase/` – Datenbank- und Storage-Konfiguration (Migrationen, RLS, Policies)
- `docs/` – Architektur, Runbooks, wissenschaftliche Hintergründe und Implementierungspläne

Weitere Ordner (z. B. `keycloak/`, `reverse-proxy/`) enthalten die Infrastruktur rund um Identity und TLS.

---

## Tests & Qualität

GUSTAV wird entwickelt nach dem Prinzip „Contract‑First“ und setzt stark auf automatisierte Tests:

- Unit- und Integrationstests:
  - `make test`
  - oder `.venv/bin/pytest -q`
  - `make test-supabase`
  - `make test-ollama && make test-ollama-vision`
- API-Verhalten wird gegen den OpenAPI-Vertrag in `api/openapi.yml` geprüft.
- Für neue Features sind Tests und Dokumentation Teil der Definition of Done.

Mehr zur Architektur und zu Clean‑Code‑Prinzipien findest du in:

- `docs/ARCHITECTURE.md`
- `docs/bounded_contexts.md`

---

## Wichtige Dokumente

Nutze die README als Wegweiser. Details stehen hier:

- **Architektur & Domäne**
  - Gesamtarchitektur: `docs/ARCHITECTURE.md`
  - Bounded Contexts: `docs/bounded_contexts.md`
  - Glossar der Fachbegriffe: `docs/glossary.md`

- **Deployment & Betrieb**
  - Neues System (z. B. Schulserver): `docs/runbooks/deploy_new_system.md`
  - Preflight-Checks vor dem Rollout: `docs/runbooks/preflight_checklist.md`

- **Datenbank & Storage**
  - Datenbank-Schema: `docs/database_schema.md`
  - Storage & Uploads (Materialien, Abgaben): `docs/references/storage_and_gateway.md`

- **KI & Wissenschaft**
  - Wissenschaftliche Hintergründe und Experimente: `docs/science/`

- **Planung & Roadmap**
  - Implementierungspläne: `docs/plan/`
  - Roadmap: `docs/ROADMAP.md`
  - Änderungsverlauf: `docs/CHANGELOG.md`
  - Lizenz: `docs/LICENCE.md` und `LICENCE.md`

---

## Healthcheck & Status

- Healthcheck-Endpunkt: `GET /health` → `{ "status": "healthy" }`
- Für einen vollständigen Systemcheck (inkl. Supabase, Keycloak, RLS) siehe:
  - `docs/runbooks/preflight_checklist.md`
