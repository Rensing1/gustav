# Plan: H5P‑Integration + Visual‑Tasks (Editor, Player, Ergebnisse, Feedback)

Goal: (1) H5P als zusätzlichen `Task`‑Typ in GUSTAV integrieren (Editor/Player + auto‑scorable Ergebnisse), sodass Lehrkräfte interaktive Aufgaben erstellen können und Schüler diese lösen können; und (2) `Task.kind="visual"` als Upload‑Only‑Variante von Aufgaben ergänzen, deren Auswertung + Rückmeldung via Vision Language Model (VLM) in den bestehenden Abgabe‑/Worker‑Flow passt.

Kontext:
- Research‑Grundlage: `docs/research/H5P-Integration.md` sowie der (hier im Chat) ausgearbeitete Lumi‑Blueprint.
- Ist‑Zustand (relevant): Tasks sind in `public.unit_tasks` gespeichert; Abgaben in `public.learning_submissions` mit asynchronem Worker (Vision + Feedback/DSPy/Ollama). OpenAPI ist Quelle der Wahrheit: `api/openapi.yml`.

## Executive Summary (Stand 2026‑01‑08)
- Umgesetzt (fertig): Phase 0 + Phase 1 (H5P‑Service als eigener Compose‑Service inkl. Proxy/CSP, Storage, Auth‑Plumbing, Editor/Player, Library‑Import, E2E‑Smoke).
- Umgesetzt (weitgehend): Phase 2 (DB + Teaching‑API: `Task.kind` + `h5p`/`visual` Konfiguration inkl. Migration + OpenAPI + Tests; Teaching‑UI: H5P‑Editor ersetzt den normalen Aufgabeneditor für `Task.kind="h5p"`).
- Umgesetzt (weitgehend): Phase 3 (Learning‑Integration für H5P: eingebetteter Player + Score‑Ingest; Visual‑Tasks: upload‑only UI/Backend + `task_kind`‑Plumbing + **DSPy‑Image‑Pipeline**: Analyse + Feedback laufen direkt auf dem visuellen Input via `dspy.Image` (Modelwahl `AI_VISUAL_MODEL` → Fallback `AI_VISION_MODEL`)).
- Umgesetzt (weitgehend): UI‑Theming (Option B): token‑basiertes H5P‑Theme für Player + Editor (Dark/Light, CKEditor 5, DIV‑Embed für Player, Editor‑iframe Token‑Sync) → `docs/plan/2026-01-08-h5p-ui-theming.md` (Rest: Feinschliff).
- Nächste Meilensteine: Phase 4 (UX/Reporting) + Phase 5 (Hardening).
- Kurzcheck lokal: `docker compose up -d --build caddy web keycloak h5p` → `curl -k -i https://app.localhost/h5p/healthz` → optional `RUN_E2E=1 ... pytest -m e2e ...` (Details: Appendix A).

---

## Scope & Prinzipien
- KISS, Security‑first, DSGVO: Self‑hosting, keine 3rd‑party Requests im Default, klare Rollen-/Rechte‑Checks.
- Security model (PoC/MVP): **Trusted content** – H5P Libraries/Packages werden als ausführbarer Code betrachtet und nur von **Lehrkräften (`teacher`, inkl. Admin)** importiert/aktualisiert; Schüler konsumieren ausschließlich kuratierten Content.
- Contract‑First & TDD: Änderungen zuerst in `api/openapi.yml`, dann failing `pytest`, dann minimaler Code (Red‑Green‑Refactor).
- Clean Architecture: Fachlogik bleibt im Python‑Use‑Case‑Layer; H5P‑Service ist ein isolierter Adapter/Driver.
- Local = Prod: Docker Compose, Migrationen und ENV gelten in beiden Umgebungen identisch (keine Dev‑Sonderpfade).
- Begriffe gemäß `glossary.md` (Task/Aufgabe, Submission/Abgabe, Analysis/Analyse, Feedback/Rückmeldung).
- Task‑Kinds (MVP): `native` (bestehend), `h5p` (auto‑scorable; **ohne** zusätzlichen GUSTAV‑Aufgabentext im UI), `visual` (upload‑only; Auswertung + Feedback via VLM).

Non‑Goals (MVP):
- Vollständiges LRS (Learning Record Store) / detaillierte Event‑Analytics für *alle* xAPI Events.
- Content‑Type Governance/Whitelist auf Library‑Ebene (MVP fokussiert auf **auto‑scorable** H5P Tasks; Hardening/Policies folgen später).
- Mehrbenutzer‑Co‑Authoring in H5P oder komplexe Versions-/Fork‑Workflows.

---

## User Stories
### H5P (auto‑scorable)
- **Lehrkraft (Authoring)**: Als Lehrkraft möchte ich in einem Abschnitt eine H5P‑Aufgabe anlegen und in einem Editor den interaktiven Inhalt erstellen/importieren, damit Schüler eine interaktive Übung bearbeiten können.
- **Schüler (Playback)**: Als Schüler möchte ich eine H5P‑Aufgabe im Kurs öffnen und bearbeiten, damit ich direkt interaktiv üben kann.
- **Ergebnisse sichtbar**: Als Schüler/Lehrkraft möchte ich Ergebnisse (z. B. Score, Bearbeitungszeit, Abgabe‑Historie) wie bei normalen Aufgaben sehen, damit Fortschritt nachvollziehbar ist.
- **Feedback**: Als Schüler möchte ich direktes Feedback in der Aufgabe sehen (H5P‑Feedback), damit ich Fehler sofort korrigieren kann.

### Visual (upload‑only, VLM)
- **Visual Task (Upload‑Only)**: Als Lehrkraft möchte ich eine „visual“ Aufgabe anlegen, bei der Schüler ein Bild oder PDF als Lösung hochladen, damit auch Skizzen/Grafiken als Teil der Lösung möglich sind.
- **Visual Auswertung + Feedback**: Als Schüler möchte ich nach dem Upload Feedback + eine Kriterien‑Auswertung erhalten (wie bei normalen Aufgaben), damit ich nachvollziehen kann, was gut ist und was ich verbessern kann.

---

## BDD‑Szenarien (Given–When–Then)

### H5P (Teaching + Learning)
#### Teaching – H5P Task anlegen/konfigurieren
- Given ich bin Autor der Lerneinheit/Abschnitts, When ich eine Aufgabe mit `h5p`‑Konfiguration anlege, Then wird `Task.kind="h5p"` zurückgegeben und die Task‑Metadaten werden gespeichert.
- Given eine H5P‑Aufgabe existiert, When ich die H5P‑Content‑ID nachträglich setze/ändere, Then bleibt die Task erhalten und referenziert den neuen Content.
- Given ich bin nicht Autor, When ich H5P‑Task‑Konfiguration ändern möchte, Then 403.

#### Learning – H5P Task spielen
- Given ich bin eingeschriebener Schüler und der Abschnitt ist freigegeben, When ich eine H5P‑Task‑Seite öffne, Then sehe ich den H5P‑Player und kann interagieren.
- Given ich bin nicht eingeschrieben oder Abschnitt nicht freigegeben, When ich die Task öffne oder H5P‑Assets direkt abrufe, Then 404 (kein Existence Leak) oder 403 (je nach Governance‑Entscheid).

#### Learning – Ergebnis/Abgabe erzeugen (xAPI)
- Given ein Schüler **versucht** eine H5P‑Aufgabe und der Player emittiert ein xAPI Statement **mit Score** (typisch Verb `answered`, ggf. `completed`), When das Frontend dieses Statement an `POST /api/learning/.../submissions` sendet, Then entsteht eine neue `Submission` (idempotent via `Idempotency-Key=statement.id`) und wird als `completed` gespeichert (inkl. `score_raw/score_max`).
- Given dasselbe scored Statement wird erneut gesendet (Reload/Retry/Netzfehler), When `Idempotency-Key` identisch ist, Then wird die bestehende Abgabe wiederverwendet (keine Duplikate).
- Given `max_attempts` ist in der Task gesetzt, When ein weiteres scored Statement gesendet wird, Then wird es **trotzdem akzeptiert** (GUSTAV enforced `max_attempts` nicht für H5P; H5P kann eigene Limits haben).
- Given mindestens eine H5P‑Submission existiert, aber keine hat volle Punktzahl, Then gilt die Aufgabe als **bearbeitet**.
- Given mindestens eine H5P‑Submission hat `score_raw == score_max` (und `score_max > 0`), Then gilt die Aufgabe als **abgeschlossen** (volle Punktzahl, unabhängig von der Anzahl der Versuche).
- Given eine Aufgabe ist `Task.kind="h5p"`, When ich eine Submission als `kind=text|image|file` sende, Then 400 (`invalid_input`).

### Visual (Teaching + Learning)
#### Teaching – Visual Task anlegen/konfigurieren
- Given ich bin Autor der Lerneinheit/Abschnitts, When ich eine Aufgabe mit `visual`‑Konfiguration anlege, Then wird `Task.kind="visual"` zurückgegeben und die Task‑Metadaten werden gespeichert.
- Given ich bin nicht Autor, When ich die Visual‑Konfiguration ändern möchte, Then 403.

#### Learning – Visual Task lösen (Upload‑Only)
- Given ich bin eingeschriebener Schüler und der Abschnitt ist freigegeben, When ich eine Visual‑Task‑Seite öffne, Then sehe ich den Aufgabentext (`instruction_md`) und ein Upload‑Formular (nur Bild/PDF, genau eine Datei pro Abgabe).
- Given eine Aufgabe ist `Task.kind="visual"`, When ich eine Abgabe als `kind=text` sende, Then 400 (`invalid_input`).
- Given eine Aufgabe ist `Task.kind="visual"`, When ich eine Abgabe als `kind=image|file` sende, Then wird eine Submission erstellt, ein Worker‑Job gequeued und nach Verarbeitung existieren `analysis_json` + `feedback_md` (analog zu `native`).

#### Learning Worker – Visual Auswertung (VLM, Option A)
- Given ein Worker‑Job für eine Visual‑Submission, When der Job verarbeitet wird, Then wird die Datei als Bildinput an ein VLM übergeben:
  - `image/*` direkt,
  - `application/pdf` via PDF→PNG (render) → ggf. stitched PNG,
  und das Modell erzeugt Kriterien‑Analyse (`criteria.v2`) + Feedback in einem Call (kein reines OCR‑Zwischen‑Transkript).

### Security (cross‑cutting)
- Given eine Browser‑POST auf den Abgabe‑Endpoint ist cross‑site (Origin/Referer mismatch), Then 403 `csrf_violation`.
- Given ein Schüler versucht den H5P‑Editor zu nutzen, Then 403/404.

---

## Zielarchitektur (Empfehlung)

### Komponenten
- **Web‑App (FastAPI, SSR/HTMX)** bleibt der primäre Server für Pages, Kurs-/Freigabe‑Logik und Abgaben/Feedback.
- **Learning Worker** bleibt das zentrale Element für KI‑Feedback (DSPy/Ollama) für `native` und `visual` Tasks. `h5p` Tasks sind auto‑scorable und benötigen im MVP keinen Worker‑Job.
- **Neuer H5P‑Service (Node/Express)** als dedizierter Service mit Lumi‑Libraries:
  - `@lumieducation/h5p-server`, `@lumieducation/h5p-express`, `@lumieducation/h5p-webcomponents`
  - Storage (decision; implemented in Phase 0): *Filesystem (bind mount)* `./supabase/storage/h5p` → `/data/h5p` (`H5P_STORAGE_ROOT=/data/h5p`; single-host, no extra DB service, included in backups via `SUPABASE_STORAGE_ROOT`)
  - optional: `@lumieducation/h5p-svg-sanitizer`, `@lumieducation/h5p-clamav-scanner`, später `@lumieducation/h5p-redis-lock`
- **Reverse Proxy (Caddy)** routet `/h5p/*` auf den H5P‑Service (same‑origin unter `app.localhost`).

### Storage – Optionen & Entscheidung (Stand 2025‑12‑23)
Anforderungen:
- Prod bleibt single-host.
- Möglichst wenig separate Services/DB‑Instanzen.
- Große H5P‑Pakete sind ok (Storage verfügbar).
- Supabase‑kompatibel (Self‑hosted Compose).

Optionen (Kurzvergleich):

| Option | Wo liegen die H5P Daten? | Vorteile | Nachteile / Risiken | Fit |
| --- | --- | --- | --- | --- |
| A) Filesystem bind mount (gewählt) | Host‑FS: `./supabase/storage/h5p` → Container: `/data/h5p` | sehr simpel; keine neuen Services; große Files ok; Backup über vorhandenen Storage‑Backup‑Pfad | skaliert nicht über mehrere Hosts (später Migration nötig) | ✅ |
| B) Supabase Storage (Bucket/API) | über Supabase Storage (S3‑API) | perspektivisch multi-host‑fähig; klarer “object storage” Vertrag | Service‑Key/Token‑Handling + mehr IO‑Overhead; für PoC unnötige Komplexität | ⚠️ später |
| C) Externer Object Store (S3/MinIO extra) | eigener Storage‑Service | skalierbar | zusätzlicher Service; widerspricht “wenig Instanzen” | ❌ |
| D) Separate DB (Mongo/GridFS) | MongoDB o. ä. | passt zu manchen H5P‑Stacks | zusätzlicher DB‑Service + Operations/Backup; widerspricht Präferenz | ❌ |
| E) Postgres (bytea/json) | Supabase DB | keine extra Services | DB‑Bloat/Performance/Backup‑Kosten bei großen Paketen | ❌ |

Entscheidung:
- Wir speichern H5P Libraries/Content/Temp als Dateien unter `/data/h5p` (bind mount in `./supabase/storage/h5p`).
- Metadaten/Referenzen (z. B. `h5p_content_id` ↔ Task) bleiben in Postgres/Supabase.
- Falls wir später multi-host brauchen: Migration zu Option B (Supabase Storage Bucket) mit Adapter‑Wechsel im H5P‑Service.

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
- Teacher‑UI:
  - `Task.kind="h5p"`: SSR‑Page mit `<h5p-editor>` (Lumi Web Component) zum Erstellen/Bearbeiten; im GUSTAV‑UI wird **kein** zusätzlicher Aufgabentext über dem Player/Editor angezeigt. (DB‑Pflichtfeld `instruction_md` wird serverseitig mit einem Platzhalter befüllt, aber nicht gerendert.)
  - `Task.kind="visual"`: Task‑Form wie bei `native` (Aufgabentext wie gewohnt; Auswertung nutzt weiter `criteria`/`hints_md` intern); Abgaben sind upload‑only.
- Student‑UI:
  - `Task.kind="h5p"`: `<h5p-player>` (ohne zusätzlichen Aufgabentext).
  - `Task.kind="visual"`: Aufgabentext + Upload‑Form (nur Bild/PDF).
- Ergebnis‑Ingest: Seite hängt einen Listener an `xAPI` Events und POSTet ein scored Statement an unseren Learning‑Submission‑Endpoint.

---

## Datenmodell (Supabase/Postgres)

### `unit_tasks` (Teaching)
Wir ergänzen Tasks um H5P‑Konfiguration, ohne das bestehende Modell zu brechen.

Migration‑Entwurf (skizziert):
```sql
-- MVP: We only support auto-scorable H5P tasks. Score is derived from xAPI,
-- so we intentionally do not model multiple evaluation modes here.
alter table public.unit_tasks
  add column if not exists kind text not null default 'native',
  add column if not exists h5p_content_id text null,
  add column if not exists h5p_display_options jsonb not null default '{}'::jsonb;

alter table public.unit_tasks
  add constraint unit_tasks_kind_check
  check (kind in ('native','h5p','visual'));
```

Hinweis (RLS/Helper):
- `public.get_released_tasks_for_student(...)` und `public.get_task_metadata_for_student(...)` müssen `t.kind` mit ausgeben, damit Learning‑UI/Worker zwischen `native|h5p|visual` unterscheiden können.
- Für `Task.kind="h5p"` braucht die Learning‑UI zusätzlich `h5p_content_id` (für Player‑Rendering). Entweder liefern wir das über Helper (preferred) oder über einen separaten Task‑Details‑Fetch (aber ohne N+1).

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

### Task Schema: `kind` über Konfiguration (Teaching + Learning)
Konzept: `Task.kind` bleibt read‑only; Create/Update wählen den Typ über optionale Konfigurationsobjekte:
- `h5p` → `Task.kind="h5p"`
- `visual` → `Task.kind="visual"`
(gegenseitig ausschließend; beide gesetzt → 400)

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
        display_options:
          type: object
          nullable: true
          additionalProperties: true

    VisualTaskConfig:
      type: object
      additionalProperties: false
      description: >-
        Marker config for upload-only visual tasks. Empty object in MVP.

    Task:
      type: object
      # existing fields…
      properties:
        kind:
          type: string
          readOnly: true
          default: native
          description: Task type (native|h5p|visual)
        h5p:
          $ref: '#/components/schemas/H5PTaskConfig'
          nullable: true
        visual:
          $ref: '#/components/schemas/VisualTaskConfig'
          nullable: true

    TaskCreate:
      type: object
      properties:
        # existing fields…
        h5p:
          $ref: '#/components/schemas/H5PTaskConfig'
          nullable: true
        visual:
          $ref: '#/components/schemas/VisualTaskConfig'
          nullable: true

    TaskUpdate:
      type: object
      properties:
        # existing fields…
        h5p:
          $ref: '#/components/schemas/H5PTaskConfig'
          nullable: true
        visual:
          $ref: '#/components/schemas/VisualTaskConfig'
          nullable: true
```

### Learning Submissions: H5P xAPI ingest (scored statements)
Wir erweitern den bestehenden Abgabe‑Endpoint um einen neuen Body‑Zweig.
Wichtig: Wir persistieren im MVP nur den **Score** (raw/max); das xAPI Statement bleibt client‑seitig, und die Statement‑ID wird als `Idempotency-Key` verwendet.
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
                  required: [kind, score_raw, score_max]
                  properties:
                    kind: { type: string, enum: [h5p] }
                    score_raw: { type: integer, minimum: 0 }
                    score_max: { type: integer, minimum: 0 }
```

Und wir erweitern `LearningSubmission.kind` um `h5p` und ergänzen `score_raw/score_max` als optionale Felder.
Für `Task.kind="visual"` gibt es keinen neuen Submission‑Body: wir verwenden die bestehenden `image|file` Payloads, validieren aber serverseitig „upload‑only“ (kein `text`).

---

## Tests (pytest) – Red/Green/Refactor Plan

1) **Contract Tests (OpenAPI)**
- Update bestehender Tests (z. B. `backend/tests/test_teaching_tasks_kind_contract.py`) bleibt gültig bzgl. „`kind` nicht in Create/Update“.
- Neue Tests:
  - `Task`, `TaskCreate`, `TaskUpdate` enthalten optionale `h5p` **und** `visual` Objekte (mutually exclusive).
  - `POST /api/learning/.../submissions` akzeptiert den neuen `h5p` Body‑Zweig.
  - `LearningSubmission.kind` enum enthält `h5p`; `score_raw/score_max` Felder sind optional.

2) **DB‑Integration Tests**
- Migrationen werden in Test‑DB angewendet; Tests schreiben/lesen echte Tabellen.
- Szenarien: idempotent ingest (Idempotency‑Key), **keine** `max_attempts`‑Enforcement für H5P, Status „bearbeitet“/„abgeschlossen“ (volle Punktzahl).
- Visual‑Szenarien: `Task.kind="visual"` akzeptiert `image|file`, lehnt `text` ab (400); Worker erzeugt `analysis_json` + `feedback_md` (wie bei `native`).

3) **Worker/Adapter Tests**
- Worker wird für `kind='h5p'` im MVP nicht benötigt (auto‑scorable Tasks) und darf keine Vision/KI‑Calls auslösen.
- Visual: Worker nutzt VLM‑Pfad (Option A) und übergibt Bilddaten (PDF→PNG) an den Feedback‑Adapter; es wird kein reines OCR‑Zwischen‑Transkript erzeugt.

4) **SSR/UI Smoke (optional, wenn vorhanden)**
- Student‑Unit‑Page rendert bei `Task.kind=h5p` den `<h5p-player>` Platzhalter.

---

## Umsetzung in Iterationen (1–2 Wochen PoC → MVP)

### Phase 0 – Service & Proxy Smoke (1–2 Tage)
- Neuer Compose Service: `h5p` (Phase‑0 Skeleton).
- Caddy: `/h5p/*` → `h5p` upstream (Path‑Prefix wird entfernt).
- Route‑spezifische CSP für `/h5p/*` (bewusst permissiver für H5P Web Components/Content Types).
- Healthcheck `GET /h5p/healthz`.
- Filesystem Storage: bind mount `./supabase/storage/h5p` → `/data/h5p` + Readiness Probe in `GET /h5p/healthz`.
- Auth‑Plumbing `GET /h5p/auth/me` (Session‑Cookie wird an `web:/api/me` weitergereicht).
- E2E‑Smoke (opt‑in via `RUN_E2E=1`) für Proxy/Auth.
- Status/Verifikation: siehe Appendix A.

### Phase 1 – Lumi PoC (Editor/Player) + Storage (2–3 Tage)
- `h5p-service` wird ein “echtes” Node‑Projekt (Lockfile + `npm ci` im Dockerfile), damit Lumi‑Dependencies reproduzierbar sind.
- Lumi Library minimal lauffähig (Editor/Player) im `h5p` Service (nicht nur Platzhalter‑Routen).
- Storage‑Foundation ist vorhanden: bind mount `./supabase/storage/h5p` → `/data/h5p`; in Phase 1 wird Lumi so konfiguriert, dass `libraries/`, `content/`, `tmp/` dort liegen (inkl. Readiness Probe in `GET /h5p/healthz`).
- Keine separate DB‑Instanz: wenn die Lumi‑Libs persistente Metadaten benötigen, werden sie entweder file‑basiert abgelegt oder (falls zwingend) in Postgres/Supabase integriert – aber nicht in Mongo.
- Upload‑Größen: Limits werden in Proxy/Service (Caddy/Node) definiert, nicht in Supabase Storage Buckets.
- Minimal‑Persistenz: Content **create/save/load** ist wirklich lauffähig (nicht nur UI‑Smoke) und wird deterministisch über Import/Export nachgewiesen:
  - Create: Import eines kleinen Fixture‑`.h5p` Pakets (Teacher) erzeugt eine neue `content_id` und persistiert unter `/data/h5p`.
  - Load: Player rendert den importierten Content (Student/Teacher) ohne Default‑3rd‑party Requests.
  - Save (Proof‑Strategy): Export→Re‑Import (Teacher) und danach erneut Load (Student). So wird “Save” ohne Browser‑Automation testbar.
- AuthZ: Editor nur `teacher`; Player `student` + `teacher` (Preview) – jeweils “fail‑closed”.
- E2E: Login → (Teacher) importiert kleines Fixture‑`.h5p` → Player lädt (Student) → Export/Reload ok; keine 500/502 (Teacher‑Rolle wird im Test via Keycloak Admin API gesetzt).
- E2E‑Fixture: kleines, deterministisches `.h5p` Paket liegt im Repo (z. B. `backend/tests_e2e/fixtures/h5p/…`), damit Phase 1 ohne Internet/Hub verifizierbar bleibt.
- Security in Phase 1: Import/Export/Update sind “write routes” → nur Teacher (inkl. Admin) + Origin/Referer‑Checks (CSRF‑Guard) + Upload‑Size‑Limits.
- Status/Verifikation: siehe Appendix A.

### Phase 2 – Teaching UI (2–3 Tage)
- SSR‑Seite für H5P Editor in GUSTAV; speichern liefert `content_id`.
- Task‑Konfiguration speichert `unit_tasks.kind='h5p'` + `h5p_content_id`.
- Teaching‑UI erweitert Task‑Erstellung um `visual` (upload‑only) als zusätzlicher Task‑Typ: `unit_tasks.kind='visual'`.
- Contract‑First/TDD: `api/openapi.yml` + Supabase‑Migration + `pytest` grün für `unit_tasks` (inkl. `h5p`‑Objekt in Task Create/Update/Read).

### Phase 3 – Learning UI + Progress‑Ingest (2–3 Tage)
- Student‑Seite rendert Player (Web Component, eingebettet in die GUSTAV‑Seite).
- Progress/Score‑Persistenz (wichtig für Teacher‑Status + Live‑Matrix):
  - **Primärsignal: `finished`‑Report** des H5P‑Clients (`POST /h5p/finishedData`).
    - Hintergrund: Der H5P‑Service speichert “Fortsetzen” (User State) und “finished” zuverlässig serverseitig.
      In der Praxis kann es aber vorkommen, dass im Browser kein scored `xAPI`‑Event bei uns ankommt
      (z. B. wegen Embed‑Typ `iframe`/Timing/Listener‑Problemen).
    - Lösung: Beim `GET /h5p/player/model` wird die H5P‑`ajax.setFinished` URL um `course_id` + `task_id`
      ergänzt, damit der H5P‑Service beim `finished`‑Call den Kontext kennt.
      Der H5P‑Service persistiert dann serverseitig zusätzlich eine `learning_submissions(kind='h5p')`
      via `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions` (Cookie‑Forwarding + Same‑Origin‑Header),
      damit Teacher‑Status/Livesicht nicht von Frontend‑Events abhängt.
  - Optional: `xAPI`‑Listener im Browser kann weiterhin Status‑Text setzen, ist aber nicht die einzige Quelle der Wahrheit.
- Abgabe‑Historie zeigt Score/Status.
- Contract‑First/TDD: `api/openapi.yml` + Supabase‑Migration + `pytest` grün für `learning_submissions.kind='h5p'` und H5P Score‑Ingest (Idempotency, **kein** `max_attempts`‑Enforcement, „bearbeitet“/„abgeschlossen“).
- Visual‑Tasks: Student‑UI zeigt Upload‑Form (Bild/PDF) und Backend validiert upload‑only; Worker erstellt Kriterien‑Analyse + Feedback via VLM (Option A).

### Phase 4 – UX & Reporting (1–2 Tage)
- Student‑UI zeigt für H5P Tasks klar „bearbeitet“ (nicht volle Punktzahl) vs. „abgeschlossen“ (volle Punktzahl) + letzten Score.
- Teacher‑Übersicht zeigt pro Schüler/Task mind. den Status „bearbeitet“/„abgeschlossen“ + letzten Score.
- Live‑Unterrichts‑Matrix (Teacher): Für `Task.kind="h5p"` zeigen wir **keine** Score‑Badges, sondern ein klares 3‑Zustände‑Signal:
  - `—` = keine Bearbeitung (keine H5P‑Submission)
  - `•` = bearbeitet (mindestens eine H5P‑Submission, aber nie volle Punktzahl)
  - `✓` = abgeschlossen (mindestens eine H5P‑Submission mit `score_raw == score_max` und `score_max > 0` – unabhängig von späteren Versuchen)

### Phase 5 – Security Hardening (laufend, vor Pilot)
- CSP‑Tightening: von permissiver `/h5p`‑CSP → minimal nötige Direktiven (Player + Editor), ohne global CSP zu lockern.
- Library Governance (Trusted‑Content): install/update nur Teacher (inkl. Admin); Provenance/Version‑Pinning + Audit‑Log (wer hat welches Paket wann importiert/aktualisiert).
- Upload scanning: SVG sanitizer + ClamAV (wenn Uploads im Editor erlaubt).
- Logging/Audit: Content create/import/update/delete mit `sub` + timestamp, ohne PII.

---

## Abnahmekriterien (MVP)
- Lehrkraft kann eine H5P Multiple‑Choice Aufgabe erstellen, Task referenziert `h5p_content_id`.
- Schüler kann Task in einem freigegebenen Abschnitt öffnen und lösen.
- Ein H5P `finished`‑Report (Score/MaxScore) erzeugt genau **eine** Abgabe (idempotent), Score wird gespeichert und sichtbar (unabhängig davon, ob ein Browser‑`xAPI`‑Event zuverlässig ankommt).
- Lehrkraft sieht im Kurs die letzte Abgabe pro Schüler/Task (inkl. Score) und erkennt „bearbeitet“ vs. „abgeschlossen“ (volle Punktzahl).
- Visual: Lehrkraft kann eine Visual‑Aufgabe anlegen; Schüler kann ein Bild/PDF hochladen und erhält Kriterien‑Analyse + Feedback (wie bei `native`), aber erzeugt durch ein VLM (kein OCR‑Only).
- Keine externen Requests im Default (CSP blockt connect/src außerhalb `self`; Ausnahmen nur bewusst).

---

## Entscheidungen (Stand 2026‑01‑08)
1) **Storage**: Filesystem bind mount `./supabase/storage/h5p` → `/data/h5p` (siehe “Storage – Optionen & Entscheidung”).
2) **CSP**: PoC/MVP akzeptiert permissive CSP **nur** auf `/h5p/*` (Hardening folgt in Phase 5).
3) **Phase‑1 Proof für Save**: “Save” wird in Phase 1 deterministisch über Export→Re‑Import→Reload nachgewiesen (ohne Browser‑Automation).
4) **Security model**: Trusted‑Content – alle Lehrkräfte (`teacher`, inkl. Admin) dürfen H5P Packages/Libraries importieren; Schüler konsumieren nur kuratierten Content (Packages gelten als Code‑Supply‑Chain).
5) **Core Assets**: H5P core files werden aus `h5p-php-library` tag `1.27.0` vendored in `h5p-service/vendor/h5p/core`, damit `/h5p/core/*` im Browser zuverlässig funktioniert (ohne Runtime‑Downloads).
6) **Library Provisioning (MVP)**: Libraries werden initial per Upload installiert (`POST /h5p/libraries/import`), damit “content-only” Pakete importierbar sind (ohne Hub/Internet im Default‑Betrieb).
   - Praxis: Libraries können aus offiziellen H5P.org‑Exports stammen (Examples & downloads), die die Library‑Ordner bereits enthalten.
   - Hinweis: Der Default‑Endpoint `https://api.h5p.org/v1/content-types/` liefert aktuell (2025‑12‑23) `404`, daher ist Hub‑Sync in Phase 1 bewusst deaktiviert (`fetchingDisabled=1`).
7) **Libraries sind admin‑verwaltet (Betrieb)**: Welche Content Types installiert sind, entscheidet der Admin (bzw. eine dafür verantwortliche Lehrkraft). GUSTAV liefert in Phase 1 keine “install all libraries” Automatik; fehlende Libraries werden beim Import als `missing_libraries` zurückgemeldet und dann gezielt per Upload nachinstalliert.
8) **Auswertungs‑Semantik (MVP, auto‑scorable Tasks)**:
   - `bearbeitet`: Es existiert mindestens eine scored H5P‑Submission, aber keine mit voller Punktzahl.
   - `abgeschlossen = volle Punktzahl`: Es existiert mindestens eine Submission mit `score_raw == score_max` (und `score_max > 0`) – unabhängig davon, wie viele Versuche der Schüler brauchte.
   - “Fortsetzen können”: H5P Content User Data (User State) bleibt aktiviert, damit Schüler beim erneuten Aufruf ihre Eingabe wiedersehen und weiterarbeiten können.
9) **Scope (MVP)**: Wir nutzen H5P in GUSTAV ausschließlich für **auto‑scorable** Übungsaufgaben (Quiz‑Typen). KI‑Bewertung/„hybrid“ ist nicht Teil dieses MVP‑Plans.
10) **H5P Task‑UI**: Für `Task.kind="h5p"` gibt es keinen zusätzlichen GUSTAV‑Aufgabentext über dem Player/Editor. `instruction_md` bleibt aus DB‑Gründen Pflicht und wird serverseitig mit einem neutralen Platzhalter befüllt, aber im UI nicht gerendert.
11) **Neuer Task‑Typ `visual`**: `Task.kind="visual"` ist upload‑only (Submission `image|file`, genau eine Datei). Auswertung + Feedback laufen analog zu `native`, aber über ein Vision‑Language‑Model (VLM, Option A: ein Call; kein OCR‑Only‑Zwischenschritt).
   - Upload‑Limits bleiben wie bei bestehenden Datei-/Bild‑Abgaben (MVP: 10 MiB pro Submission).
   - Keine fachliche PDF‑Seitenbegrenzung im MVP (nur technische DoS‑Schranken wie im bestehenden PDF‑Renderer).
12) **DSPy Bild‑Input (VLM)**: Für VLM‑Calls verwenden wir `dspy.Image` als „image_url“‑Content‑Part. Wir übergeben Bilder als **data‑URI** (base64), um externe Fetches/URLs zu vermeiden (DSGVO/Security‑first).

## Offene Fragen
1) **CSP Hardening**: Welche minimalen Direktiven brauchen wir für Pilot/Hardening? (eval/inline/workers).
2) **Content‑Type Scope**: Welche auto‑scorbaren Content Types wollen wir in Phase 3 offiziell als „Tasks“ zulassen (z. B. MultiChoice/Blanks/DragText/DragQuestion)?
3) **Event‑Retention**: Speichern wir nur scored Statements (answered/completed) oder auch weitere xAPI Events? Wie lange? (DSGVO/Datensparsamkeit).

---

## Appendix A – Status & Verifikation (lokal)

### Phase 0 – Status (2025‑12‑24)
- ✅ `h5p` Service ist als eigener Compose‑Service vorhanden (Phase 0).
- ✅ Caddy routet `/h5p/*` auf `h5p:3000` (Path‑Prefix wird via `handle_path` entfernt).
- ✅ `GET /h5p/healthz` liefert `200` inkl. Storage‑Readiness (`storage.ok=true`).
- ✅ `GET /h5p/auth/me` liefert ohne Session `401` (fail‑closed).
- ✅ `GET /h5p/editor` und `GET /h5p/player` liefern ohne Session `401` (fail‑closed).
- ✅ E2E‑Smoke inkl. OIDC Login ist erfolgreich (siehe “Verifikation” unten).

### Phase 0 – Verifikation (lokal)
1) Infrastruktur starten:
   - `docker compose up -d --build caddy web keycloak h5p`
2) Smoke per curl (TLS‑verify aus):
   - `curl -k -i https://app.localhost/h5p/healthz` (erwartet `storage.ok=true`)
   - `curl -k -i https://app.localhost/h5p/auth/me`  (erwartet `401`)
   - `curl -k -i https://app.localhost/h5p/editor`   (erwartet `401`)
   - `curl -k -i https://app.localhost/h5p/player`   (erwartet `401`)
3) E2E (mit OIDC) inkl. TLS‑Trust für Python `requests`:
   - Caddy Root‑CA exportieren: `docker cp gustav-caddy:/data/caddy/pki/authorities/local/root.crt .tmp/caddy-root.crt`
   - Ausführen: `RUN_E2E=1 REQUESTS_CA_BUNDLE=.tmp/caddy-root.crt .venv/bin/pytest -q -m e2e backend/tests_e2e`

### Phase 1 – Status (2025‑12‑24)
- ✅ `h5p-service` ist ein echtes Node‑Projekt (`h5p-service/package.json`, `h5p-service/package-lock.json`)
  und wird via `npm ci` im Dockerfile gebaut.
- ✅ API‑Contract für `/h5p/*` ist in `api/openapi.yml` ergänzt (Health/Auth/Editor/Player/Libraries/Import/Export).
- ✅ Create/Save/Load ist E2E‑verifiziert über Import→Player→Export→Re‑Import→Player:
  - Test: `backend/tests_e2e/test_h5p_roundtrip_e2e.py` (opt‑in via `RUN_E2E=1`)
  - Fixture: `backend/tests_e2e/fixtures/h5p/minimal/…`
- ✅ Security: Import/Export/Write‑Actions sind Teacher‑only + CSRF Same‑Origin (Origin/Referer) + Upload‑Limit.
- ✅ Import‑Fehler sind “actionable”: Content‑only Pakete ohne `libraries/*` liefern `400 missing_libraries` + `detail`
  mit der Liste fehlender Libraries (E2E: `backend/tests_e2e/test_h5p_import_errors_e2e.py`).
- ✅ Browser‑UX (Player): H5P core assets sind provisioniert (`h5p-service/vendor/h5p/core`, aus `h5p-php-library` tag `1.27.0`)
  und werden über `/h5p/core/*` ausgeliefert (E2E: `backend/tests_e2e/test_h5p_assets_e2e.py`).
- ✅ Library Provisioning (Trusted‑Content): Lehrkräfte können Content‑Type Libraries installieren via
  `POST /h5p/libraries/import` (Upload `.h5p`) und installierte Libraries via `GET /h5p/libraries` prüfen.
- ✅ Library Provisioning ist E2E + in der Praxis verifiziert:
  - `POST /h5p/libraries/import` installiert Libraries auch aus **library‑only** Paketen (ohne `h5p.json`/`content/*`)
    sowie aus vollständigen Export‑Paketen mit eingebetteten Library‑Ordnern.
  - “content‑only” Pakete (z. B. Hub‑Downloads ohne eingebettete Libraries) liefern erwartungsgemäß `missing_libraries`
    und können nach Installation der fehlenden Libraries importiert werden.
- ✅ Browser‑UX (Editor): echte Editor‑UI (Lumi Web Components) ist verfügbar via `GET /h5p/editor` inkl. New/Load/Save.
  - Editor core assets sind provisioniert (`h5p-service/vendor/h5p/editor`) und werden same‑origin via
    `/h5p/editor-assets/*` ausgeliefert.
  - Webcomponents werden via `/h5p/webcomponents/*` ausgeliefert, inkl. `.js`‑Fallback für extensionless Imports.
  - Robustheit: Lumi’s ES2015 build enthält bare imports (`deepmerge`, `await-lock`).
    Zusätzlich zu Import‑Maps liefern wir daher zwei kleine browser‑kompatible Overrides aus
    (`h5p-service/vendor/webcomponents/overrides/{h5p-utils.js,dom-utils.js}`), die nur relative Imports nutzen.
    Ergebnis: Editor bleibt auch ohne Import‑Map‑Support funktionsfähig
    (E2E: `backend/tests_e2e/test_h5p_assets_e2e.py::test_h5p_editor_webcomponents_modules_are_resolvable`).
  - Editor‑Robustheit: `GET /h5p/editor` enthält ein sichtbares Status‑Element und eine Init‑Flagge
    (`window.__gustav_h5p_editor_init_ok`) für Debugging.
    Außerdem werden HTML‑Linebreaks bewusst beibehalten, damit `//` Kommentare im inline ES‑Module Script nicht den Rest
    des Scripts “wegkommentieren” (Fix für „Buttons reagieren nicht“ / „module load failed“;
    E2E: `backend/tests_e2e/test_h5p_assets_e2e.py::test_h5p_editor_webcomponents_modules_are_resolvable`).
  - Cache‑Robustheit (Editor): `/h5p/webcomponents/*` und `/h5p/webcomponents/vendor/*` werden mit `maxAge=0`
    ausgeliefert (always revalidate), damit nach Rebuild/Deploy keine stale JS‑Bundles den Editor “halb kaputt” machen.
  - Known UX pitfall fixed: Loading an existing content id from the initial `new` state requires forcing a re-render;
    die Phase‑1‑Page macht das via `setEditorContentId()` helper.

### Phase 1 – Verifikation (lokal): Content‑Type Libraries installieren (Beispiel: MultiChoice)
1) Beispiel‑Content herunterladen (oft **content‑only**, ohne eingebettete Libraries):
   - `curl -L -o .tmp/multiple-choice-713.h5p https://h5p.org/sites/default/files/h5p/exports/multiple-choice-713.h5p`
2) Library‑Paket beschaffen (admin‑verwaltet):
   - Erkennbar daran, dass im ZIP auf Root‑Ebene Ordner wie `H5P.MultiChoice-1.16/` enthalten sind
     (nicht nur `content/` + `h5p.json`).
3) Als Lehrkraft in der UI Libraries installieren:
   - `https://app.localhost/h5p/editor` → “Install library package (.h5p)”
   - Hinweis: `POST /h5p/libraries/import` ist Teacher‑only + Same‑Origin‑CSRF (Origin/Referer).
4) Installation prüfen:
   - UI: `https://app.localhost/h5p/libraries` (erwartet u. a. `H5P.MultiChoice-1.16`)
   - oder Dateisystem: `ls -1 supabase/storage/h5p/libraries | rg 'H5P\\.MultiChoice-1\\.16'`
5) Content importieren und Player öffnen:
   - Content‑Import: `https://app.localhost/h5p/editor` → “Import .h5p”
   - Player: `https://app.localhost/h5p/player?content_id=<id>`
6) Editor‑Smoke (New/Load/Save):
   - `https://app.localhost/h5p/editor` → Status sollte `Ready.` anzeigen; Klick auf Buttons muss den Status
     aktualisieren (wenn nicht: DevTools Console öffnen; dort sieht man i. d. R. das erste JS‑Load‑Problem).

### Phase 2 – Status (2026‑01‑05)
- ✅ DB‑Migration: `supabase/migrations/20260105190000_unit_tasks_kind_h5p_visual.sql` (Spalten `kind`, `h5p_content_id`, `h5p_display_options` + Check‑Constraint).
- ✅ OpenAPI (Contract‑First): `api/openapi.yml` ergänzt `H5PTaskConfig`/`VisualTaskConfig` und `TaskCreate/Update` akzeptieren `h5p|visual` (mutually exclusive).
- ✅ Teaching‑API (Backend): `POST/PATCH /api/teaching/.../tasks` setzt `Task.kind` indirekt über `h5p|visual` und liefert `Task.kind` + `task.h5p|task.visual` zurück.
- ✅ Tests: `backend/tests/test_teaching_tasks_h5p_visual_api.py` (DB‑Integration) + `backend/tests/test_teaching_tasks_service_unit.py` (Unit).
- ✅ Teaching‑UI (Teacher): Beim Anlegen einer Aufgabe kann `H5P` gewählt werden; die Detailseite rendert den eingebetteten `<h5p-editor>` und ersetzt damit den normalen Aufgabeneditor (kein iFrame, keine Extra‑Seite).
- ✅ UI‑Smoke‑Test: `backend/tests/test_teaching_entry_detail_ui.py::test_h5p_task_detail_embeds_h5p_editor_instead_of_markdown_editor`.

### Phase 3 – Status (2026‑01‑08)
- ✅ DB‑Migration: `supabase/migrations/20260108203000_learning_h5p_scoring_and_task_kind.sql` (H5P‑Scores in `learning_submissions`, Helper liefern `task.kind` + H5P‑Config).
- ✅ OpenAPI (Contract‑First): H5P‑Submission Body `kind=h5p` mit `score_raw/score_max`; `LearningSubmission` enthält `score_raw/score_max`; neuer Endpoint `GET /h5p/player/model`.
- ✅ H5P‑Service: `GET /h5p/player/model` liefert Player‑Model JSON; AuthZ für Schüler prüft, dass `content_id` im freigegebenen Kurs‑Scope liegt (fail‑closed).
- ✅ Learning‑Backend: H5P‑Submissions werden synchron als `completed` gespeichert (kein Worker‑Job); `max_attempts` wird für H5P nicht enforced.
- ✅ Student‑UI (embedded, no iframe): H5P‑Tasks werden im Kurs direkt gerendert, Listener erfasst xAPI Score und POSTet an Learning‑API.
- ✅ Teaching Live‑Matrix: H5P‑Tasks werden als `—`/`•`/`✓` angezeigt (keine Bearbeitung / bearbeitet / abgeschlossen=volle Punktzahl), basierend auf H5P‑Submissions.
- ✅ Student‑UI (Visual/Uploads): In der Abgabe‑Historie wird bei `kind=image|file` die hochgeladene Datei als Vorschau angezeigt (Bild inline, PDF als Link) statt eines verwirrenden „OCR placeholder …“‑Texts.
- ✅ Tests: `backend/tests/test_learning_h5p_scoring_api.py`, `backend/tests/test_openapi_h5p_player_model_contract.py` (+ Regression‑Fixes in Worker/Mapping Tests).
