# Plan: H5P‑Integration (Editor, Player, Ergebnisse, Feedback)

Goal: H5P als zusätzlichen `Task`‑Typ in GUSTAV integrieren, sodass Lehrkräfte interaktive Aufgaben erstellen können, Schüler diese lösen können, und Ergebnisse/Feedback (automatisch und/oder KI‑basiert) in den bestehenden Abgabe‑ und Auswertungsfluss passen.

Kontext:
- Research‑Grundlage: `docs/research/H5P-Integration.md` sowie der (hier im Chat) ausgearbeitete Lumi‑Blueprint.
- Ist‑Zustand (relevant): Tasks sind in `public.unit_tasks` gespeichert; Abgaben in `public.learning_submissions` mit asynchronem Worker (Vision + Feedback/DSPy/Ollama). OpenAPI ist Quelle der Wahrheit: `api/openapi.yml`.

---

## Scope & Prinzipien
- KISS, Security‑first, DSGVO: Self‑hosting, keine 3rd‑party Requests im Default, klare Rollen-/Rechte‑Checks.
- Contract‑First & TDD: Änderungen zuerst in `api/openapi.yml`, dann failing `pytest`, dann minimaler Code (Red‑Green‑Refactor).
- Clean Architecture: Fachlogik bleibt im Python‑Use‑Case‑Layer; H5P‑Service ist ein isolierter Adapter/Driver.
- Local = Prod: Docker Compose, Migrationen und ENV gelten in beiden Umgebungen identisch (keine Dev‑Sonderpfade).
- Begriffe gemäß `docs/glossary.md` (Task/Aufgabe, Submission/Abgabe, Analysis/Analyse, Feedback/Rückmeldung).

Non‑Goals (MVP):
- Vollständiges LRS (Learning Record Store) / detaillierte Event‑Analytics für *alle* xAPI Events.
- Content‑Type Governance/Whitelist (MVP erlaubt alle Content Types; Hardening/Policies folgen später).
- Mehrbenutzer‑Co‑Authoring in H5P oder komplexe Versions-/Fork‑Workflows.

---

## User Stories
1) **Lehrkraft (Authoring)**: Als Lehrkraft möchte ich in einem Abschnitt eine H5P‑Aufgabe anlegen und in einem Editor den interaktiven Inhalt erstellen/importieren, damit Schüler eine interaktive Übung bearbeiten können.
2) **Schüler (Playback)**: Als Schüler möchte ich eine H5P‑Aufgabe im Kurs öffnen und bearbeiten, damit ich direkt interaktiv üben kann.
3) **Ergebnisse sichtbar**: Als Schüler/Lehrkraft möchte ich Ergebnisse (z. B. Score, Bearbeitungszeit, Abgabe‑Historie) wie bei normalen Aufgaben sehen, damit Fortschritt nachvollziehbar ist.
4) **Feedback‑Varianten**: Als Schüler möchte ich Feedback bekommen – entweder automatisch (z. B. Multiple Choice) oder KI‑basiert (z. B. Essay), oder hybrid.

---

## BDD‑Szenarien (Given–When–Then)

### Teaching – H5P Task anlegen/konfigurieren
- Given ich bin Autor der Lerneinheit/Abschnitts, When ich eine Aufgabe mit `h5p`‑Konfiguration anlege, Then wird `Task.kind="h5p"` zurückgegeben und die Task‑Metadaten werden gespeichert.
- Given eine H5P‑Aufgabe existiert, When ich die H5P‑Content‑ID nachträglich setze/ändere, Then bleibt die Task erhalten und referenziert den neuen Content.
- Given ich bin nicht Autor, When ich H5P‑Task‑Konfiguration ändern möchte, Then 403.

### Learning – H5P Task spielen
- Given ich bin eingeschriebener Schüler und der Abschnitt ist freigegeben, When ich eine H5P‑Task‑Seite öffne, Then sehe ich den H5P‑Player und kann interagieren.
- Given ich bin nicht eingeschrieben oder Abschnitt nicht freigegeben, When ich die Task öffne oder H5P‑Assets direkt abrufe, Then 404 (kein Existence Leak) oder 403 (je nach Governance‑Entscheid).

### Learning – Ergebnis/Abgabe erzeugen (xAPI)
- Given ein Schüler beendet eine H5P‑Aufgabe und der Player emittiert ein xAPI `completed` Statement, When das Frontend dieses Statement an `POST /api/learning/.../submissions` sendet, Then entsteht eine neue `Submission` (idempotent via `Idempotency-Key=statement.id`).
- Given dieselbe Completion wird erneut gesendet (Reload/Retry/Netzfehler), When `Idempotency-Key` identisch ist, Then wird die bestehende Abgabe wiederverwendet (keine Duplikate).
- Given `max_attempts` ist erreicht, When ein weiteres Completion gesendet wird, Then 400 `max_attempts_exceeded`.

### Feedback‑Modi
- Given `evaluation_mode=auto`, When ein Completion mit Score eingeht, Then wird die Abgabe direkt als `completed` markiert und enthält Score‑Feedback ohne Worker‑Queue.
- Given `evaluation_mode=ai`, When ein Completion mit auswertbarer Freitext‑Antwort eingeht, Then wird eine Abgabe als `pending` angelegt und der Worker erzeugt `feedback_md` und `analysis_json`.
- Given `evaluation_mode=hybrid`, When Completion eingeht, Then wird Score gespeichert **und** der Worker wird für KI‑Feedback gestartet.

### Security
- Given eine Browser‑POST auf den Abgabe‑Endpoint ist cross‑site (Origin/Referer mismatch), Then 403 `csrf_violation`.
- Given ein Schüler versucht den H5P‑Editor zu nutzen, Then 403/404.

---

## Zielarchitektur (Empfehlung)

### Komponenten
- **Web‑App (FastAPI, SSR/HTMX)** bleibt der primäre Server für Pages, Kurs-/Freigabe‑Logik und Abgaben/Feedback.
- **Learning Worker** bleibt unverändert das zentrale Element für KI‑Feedback (DSPy/Ollama).
- **Neuer H5P‑Service (Node/Express)** als dedizierter Service mit Lumi‑Libraries:
  - `@lumieducation/h5p-server`, `@lumieducation/h5p-express`, `@lumieducation/h5p-webcomponents`
  - Storage: initial *Filesystem + MongoDB* (oder Mongo+S3/MinIO, siehe Open Questions)
  - optional: `@lumieducation/h5p-svg-sanitizer`, `@lumieducation/h5p-clamav-scanner`, später `@lumieducation/h5p-redis-lock`
- **Reverse Proxy (Caddy)** routet `/h5p/*` auf den H5P‑Service (same‑origin unter `app.localhost`).

### AuthN/AuthZ (entscheidungsreif, aber verifizierungsbedürftig)
Wir vermeiden neue Tokens im Browser und nutzen das bestehende Cookie‑Session‑Modell:
- AuthN im H5P‑Service: `gustav_session` Cookie auslesen, dann **intern** gegen GUSTAV validieren:
  - Option B1 (empfohlen): `GET http://gustav-alpha2:8000/api/me` mit Cookie weiterreichen; Ergebnis cachen (z. B. 30s).
  - Option B2: direktes Lesen aus der Session‑DB (höhere Kopplung an DB‑Schema; nur falls B1 zu langsam).
- AuthZ im H5P‑Service:
  - Editor‑Routen: nur `teacher` (und zusätzlich “authorOnly” optional: nur Unit‑Autor).
  - Player/Content‑Routen: `student` oder `teacher` (Preview).
  - Content‑Zugriff: H5P‑Service prüft via Postgres‑Lookup/Helper, ob Content‑ID zu einer `Task` gehört, die für den Nutzer sichtbar ist (mindestens ein Kurs mit Freigabe + Membership).

Hinweis: Das ist bewusst „fail‑closed“ – ohne nachweisbare Berechtigung liefert der H5P‑Service keinen Content aus.

### UI‑Integration
- Teacher‑UI: SSR‑Page mit `<h5p-editor>` (Lumi Web Component) zum Erstellen/Bearbeiten; Task‑Metadaten (instruction/criteria/hints) bleiben in GUSTAV.
- Student‑UI: SSR‑TaskCard rendert statt Text/Upload‑Form den `<h5p-player>`.
- Ergebnis‑Ingest: Seite hängt einen Listener an `xAPI` Events und POSTet das Completion an unseren Learning‑Submission‑Endpoint.

---

## Datenmodell (Supabase/Postgres)

### `unit_tasks` (Teaching)
Wir ergänzen Tasks um H5P‑Konfiguration, ohne das bestehende Modell zu brechen.

Migration‑Entwurf (skizziert):
```sql
alter table public.unit_tasks
  add column if not exists kind text not null default 'native',
  add column if not exists h5p_content_id text null,
  add column if not exists h5p_evaluation_mode text null,
  add column if not exists h5p_display_options jsonb not null default '{}'::jsonb;

alter table public.unit_tasks
  add constraint unit_tasks_kind_check
  check (kind in ('native','h5p'));

alter table public.unit_tasks
  add constraint unit_tasks_h5p_evaluation_mode_check
  check (h5p_evaluation_mode is null or h5p_evaluation_mode in ('auto','ai','hybrid'));
```

### `learning_submissions` (Learning)
Wir integrieren H5P‑Ergebnisse als „normale“ Abgaben, damit Historie/Versuche/Teacher‑Matrix wiederverwendet werden können.

Migration‑Entwurf (skizziert):
```sql
alter table public.learning_submissions
  drop constraint if exists learning_submissions_kind_check;

alter table public.learning_submissions
  add constraint learning_submissions_kind_check
  check (kind in ('text','image','file','h5p'));

alter table public.learning_submissions
  add column if not exists score_raw integer null,
  add column if not exists score_max integer null;

alter table public.learning_submissions
  add constraint learning_submissions_score_check
  check (
    (score_raw is null and score_max is null)
    or (score_raw is not null and score_max is not null and score_raw >= 0 and score_max >= 0 and score_raw <= score_max)
  );
```

Persistenz der kompletten xAPI Statements (optional, MVP‑neutral):
- in `learning_submissions.internal_metadata->'h5p'` (internal only), oder
- in neuer Tabelle `learning_h5p_xapi_events` (nur falls Analytics‑Scope im MVP).

---

## API Contract (OpenAPI – Auszug, Contract‑First)

### Task Schema: H5P‑Konfiguration (Teaching + Learning)
Konzept: `Task.kind` bleibt read‑only; Create/Update steuern H5P über ein optionales `h5p` Objekt.

```yaml
components:
  schemas:
    H5PTaskConfig:
      type: object
      additionalProperties: false
      properties:
        content_id:
          type: string
          nullable: true
          description: H5P content id in H5P service storage (may be null for drafts)
        evaluation_mode:
          type: string
          enum: [auto, ai, hybrid]
          nullable: true
        display_options:
          type: object
          nullable: true
          additionalProperties: true

    Task:
      type: object
      # existing fields…
      properties:
        kind:
          type: string
          readOnly: true
          default: native
          description: Task type (native|h5p)
        h5p:
          $ref: '#/components/schemas/H5PTaskConfig'
          nullable: true

    TaskCreate:
      type: object
      properties:
        # existing fields…
        h5p:
          $ref: '#/components/schemas/H5PTaskConfig'
          nullable: true

    TaskUpdate:
      type: object
      properties:
        # existing fields…
        h5p:
          $ref: '#/components/schemas/H5PTaskConfig'
          nullable: true
```

### Learning Submissions: H5P Completion ingest
Wir erweitern den bestehenden Abgabe‑Endpoint um einen neuen Body‑Zweig:
```yaml
paths:
  /api/learning/courses/{course_id}/tasks/{task_id}/submissions:
    post:
      # existing…
      requestBody:
        required: true
        content:
          application/json:
            schema:
              oneOf:
                # existing text/image/file…
                - type: object
                  required: [kind, content_id, statement]
                  properties:
                    kind: { type: string, enum: [h5p] }
                    content_id: { type: string, minLength: 1 }
                    statement:
                      type: object
                      description: Full xAPI statement (JSON)
                      additionalProperties: true
```

Und wir erweitern `LearningSubmission.kind` um `h5p` und ergänzen `score_raw/score_max` als optionale Felder.

---

## Tests (pytest) – Red/Green/Refactor Plan

1) **Contract Tests (OpenAPI)**
- Update bestehender Tests (z. B. `backend/tests/test_teaching_tasks_kind_contract.py`) bleibt gültig bzgl. „`kind` nicht in Create/Update“.
- Neue Tests:
  - `Task`, `TaskCreate`, `TaskUpdate` enthalten optionales `h5p` Objekt.
  - `POST /api/learning/.../submissions` akzeptiert den neuen `h5p` Body‑Zweig.
  - `LearningSubmission.kind` enum enthält `h5p`; `score_raw/score_max` Felder sind optional.

2) **DB‑Integration Tests**
- Migrationen werden in Test‑DB angewendet; Tests schreiben/lesen echte Tabellen.
- Szenarien: idempotent completion, max_attempts, auto vs ai/hybrid Status.

3) **Worker/Adapter Tests**
- Worker behandelt `kind='h5p'` wie „text passthrough“ (kein Vision‑Call).
- AI‑Flow (ai/hybrid): Worker erzeugt `analysis_json` (criteria.v2) und `feedback_md`.

4) **SSR/UI Smoke (optional, wenn vorhanden)**
- Student‑Unit‑Page rendert bei `Task.kind=h5p` den `<h5p-player>` Platzhalter.

---

## Umsetzung in Iterationen (1–2 Wochen PoC → MVP)

### Phase 0 – Service & Proxy Smoke (1–2 Tage)
- Neuer Compose Service: `h5p` (Phase‑0 Skeleton).
- Caddy: `/h5p/*` → `h5p` upstream (Path‑Prefix wird entfernt).
- Route‑spezifische CSP für `/h5p/*` (bewusst permissiver für “alle Content Types”).
- Healthcheck `GET /h5p/healthz`.
- Auth‑Plumbing `GET /h5p/auth/me` (Session‑Cookie wird an `web:/api/me` weitergereicht).
- E2E‑Smoke (opt‑in via `RUN_E2E=1`) für Proxy/Auth.

Status (2025‑12‑22):
- ✅ `h5p` Service ist als eigener Compose‑Service vorhanden (Phase 0).
- ✅ Caddy routet `/h5p/*` auf `h5p:3000` (Path‑Prefix wird via `handle_path` entfernt).
- ✅ `GET /h5p/healthz` liefert `200` (Proxy + Service “liveness” verifiziert).
- ✅ `GET /h5p/auth/me` liefert ohne Session `401` (fail‑closed).
- ✅ `GET /h5p/editor` und `GET /h5p/player` liefern ohne Session `401` (fail‑closed).
- ✅ E2E‑Smoke inkl. OIDC Login ist erfolgreich (siehe “Verifikation” unten).

Verifikation (lokal):
1) Infrastruktur starten:
   - `docker compose up -d --build caddy web keycloak h5p`
2) Smoke per curl (TLS‑verify aus):
   - `curl -k -i https://app.localhost/h5p/healthz`
   - `curl -k -i https://app.localhost/h5p/auth/me`  (erwartet `401`)
   - `curl -k -i https://app.localhost/h5p/editor`   (erwartet `401`)
   - `curl -k -i https://app.localhost/h5p/player`   (erwartet `401`)
3) E2E (mit OIDC) inkl. TLS‑Trust für Python `requests`:
   - Caddy Root‑CA exportieren: `docker cp gustav-caddy:/data/caddy/pki/authorities/local/root.crt .tmp/caddy-root.crt`
   - Ausführen: `RUN_E2E=1 REQUESTS_CA_BUNDLE=.tmp/caddy-root.crt .venv/bin/pytest -q -m e2e backend/tests_e2e`

### Phase 1 – Lumi PoC (Editor/Player) + Storage (2–3 Tage)
- Lumi Library minimal lauffähig (Editor/Player) im `h5p` Service (nicht nur Platzhalter‑Routen).
- Storage‑Entscheidung (Supabase‑kompatibel): wo liegen Content‑Binaries/Assets, wie wird lokal=prod umgesetzt?
- Minimal‑Persistenz: Content erstellen/speichern/laden; Assets lokal ausliefern (keine externen Requests notwendig).
- AuthZ: Editor nur `teacher`; Player `student` + `teacher` (Preview) – jeweils “fail‑closed”.
- E2E: Login → Editor‑Page lädt (teacher), Player‑Page lädt (student), keine 500/502.

### Phase 2 – Teaching UI (2–3 Tage)
- SSR‑Seite für H5P Editor in GUSTAV; speichern liefert `content_id`.
- Task‑Konfiguration speichert `unit_tasks.kind='h5p'` + `h5p_content_id`.

### Phase 3 – Learning UI + xAPI ingest (2–3 Tage)
- Student‑Seite rendert Player; Listener POSTet Completion an Learning‑API.
- Abgabe‑Historie zeigt Score/Status.

### Phase 4 – Feedback‑Modi (2–3 Tage)
- `evaluation_mode=auto`: sofortige Abgabe‑Finalisierung (ohne Worker).
- `evaluation_mode=ai/hybrid`: Worker‑Queue + KI‑Feedback; hybrid speichert Score zusätzlich.

### Phase 5 – Security Hardening (laufend, vor Pilot)
- CSP‑Tightening: von permissiver `/h5p`‑CSP → minimal nötige Direktiven (Player + Editor), ohne global CSP zu lockern.
- Library Governance: install/update nur Admin/Trusted Teachers; initiale Whitelist.
- Upload scanning: SVG sanitizer + ClamAV (wenn Uploads im Editor erlaubt).
- Logging/Audit: Content create/import/update/delete mit `sub` + timestamp, ohne PII.

---

## Abnahmekriterien (MVP)
- Lehrkraft kann eine H5P Multiple‑Choice Aufgabe erstellen, Task referenziert `h5p_content_id`.
- Schüler kann Task in einem freigegebenen Abschnitt öffnen und lösen.
- Completion erzeugt genau **eine** Abgabe (idempotent), Score wird gespeichert und sichtbar.
- Lehrkraft sieht im Kurs die letzte Abgabe pro Schüler/Task (inkl. Score; bei ai/hybrid zusätzlich Feedback/Auswertung).
- Keine externen Requests im Default (CSP blockt connect/src außerhalb `self`; Ausnahmen nur bewusst).

---

## Open Questions / Entscheidungen
1) **Storage**: FS‑Volume vs MinIO (S3) vs Supabase S3‑Compat (lokal=prod‑Tauglichkeit prüfen).
2) **CSP**: PoC/MVP akzeptiert permissive `/h5p`‑CSP; welche minimalen Direktiven brauchen wir für Pilot/Hardening? (eval/inline/workers).
3) **AI‑Scope**: Welche H5P Content Types werden für `evaluation_mode=ai` initial erlaubt (Essay/ShortAnswer)?
4) **Event‑Retention**: Speichern wir nur Completion oder auch answered‑Events? Wie lange? (DSGVO/Datensparsamkeit).
5) **Versuchszählung**: Semantik von `max_attempts` bei H5P (nur „completed“ zählt vs. auch Retry‑UI).
