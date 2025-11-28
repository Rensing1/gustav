# GUSTAV – KI‑gestützte Lernplattform für Schulen

GUSTAV ist eine KI‑gestützte Lernplattform für Schulen. Lehrkräfte erstellen Lerneinheiten inkl. Material und Aufgaben, Schüler bearbeiten diese im Browser und bekommen automatisches, formatives Feedback. Das Projekt ist offen entwickelt – du kannst den Code lesen, verstehen und selbst mitentwickeln.

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

Wir entwickeln nach dem Prinzip „Contract‑First“ und setzen stark auf automatisierte Tests:

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

## Mitmachen / Contributing

Aktuell bearbeite ich das Projekt alleine. Über Unterstützung freue ich mich gerne! 

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

---

## Warum dieses Projekt spannend für dich ist

- Du arbeitest an einem echten Produkt, das im Unterricht eingesetzt wird.
- Du lernst moderne Webentwicklung mit Python, FastAPI, Supabase und HTMX – mit Fokus auf Sicherheit und Datenschutz.
- Du siehst, wie KI verantwortungsvoll im Unterrichtskontext eingesetzt werden kann (Ollama, DSPy, lokale Modelle).
- Du kannst eigene Ideen für Lerninhalte, UI oder Auswertungen einbringen und direkt im Code umsetzen.
