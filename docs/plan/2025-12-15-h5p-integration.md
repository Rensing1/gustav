# Plan: H5P‑Integration (Editor, Player, Ergebnisse, Feedback)

Goal: H5P als zusätzlichen `Task`‑Typ in GUSTAV integrieren, sodass Lehrkräfte interaktive Aufgaben erstellen können, Schüler diese lösen können, und Ergebnisse/Feedback (automatisch und/oder KI‑basiert) in den bestehenden Abgabe‑ und Auswertungsfluss passen.

Kontext:
- Research‑Grundlage: `docs/research/H5P-Integration.md` sowie der (hier im Chat) ausgearbeitete Lumi‑Blueprint.
- Ist‑Zustand (relevant): Tasks sind in `public.unit_tasks` gespeichert; Abgaben in `public.learning_submissions` mit asynchronem Worker (Vision + Feedback/DSPy/Ollama). OpenAPI ist Quelle der Wahrheit: `api/openapi.yml`.

---

## Scope & Prinzipien
- KISS, Security‑first, DSGVO: Self‑hosting, keine 3rd‑party Requests im Default, klare Rollen-/Rechte‑Checks.
- Security model (PoC/MVP): **Trusted content** – H5P Libraries/Packages werden als ausführbarer Code betrachtet und nur von **Lehrkräften (`teacher`, inkl. Admin)** importiert/aktualisiert; Schüler konsumieren ausschließlich kuratierten Content.
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
- Filesystem Storage: bind mount `./supabase/storage/h5p` → `/data/h5p` + Readiness Probe in `GET /h5p/healthz`.
- Auth‑Plumbing `GET /h5p/auth/me` (Session‑Cookie wird an `web:/api/me` weitergereicht).
- E2E‑Smoke (opt‑in via `RUN_E2E=1`) für Proxy/Auth.

Status (2025‑12‑23):
- ✅ `h5p` Service ist als eigener Compose‑Service vorhanden (Phase 0).
- ✅ Caddy routet `/h5p/*` auf `h5p:3000` (Path‑Prefix wird via `handle_path` entfernt).
- ✅ `GET /h5p/healthz` liefert `200` inkl. Storage‑Readiness (`storage.ok=true`).
- ✅ `GET /h5p/auth/me` liefert ohne Session `401` (fail‑closed).
- ✅ `GET /h5p/editor` und `GET /h5p/player` liefern ohne Session `401` (fail‑closed).
- ✅ E2E‑Smoke inkl. OIDC Login ist erfolgreich (siehe “Verifikation” unten).

Verifikation (lokal):
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

Status (2025‑12‑23):
- ✅ `h5p-service` ist ein echtes Node‑Projekt (`h5p-service/package.json`, `h5p-service/package-lock.json`) und wird via `npm ci` im Dockerfile gebaut.
- ✅ API‑Contract für `/h5p/*` ist in `api/openapi.yml` ergänzt (Health/Auth/Editor/Player/Libraries/Import/Export).
- ✅ Create/Save/Load ist E2E‑verifiziert über Import→Player→Export→Re‑Import→Player:
  - Test: `backend/tests_e2e/test_h5p_roundtrip_e2e.py` (opt‑in via `RUN_E2E=1`)
  - Fixture: `backend/tests_e2e/fixtures/h5p/minimal/…`
- ✅ Security: Import/Export/Write‑Actions sind Teacher‑only + CSRF Same‑Origin (Origin/Referer) + Upload‑Limit.
- ✅ Import‑Fehler sind “actionable”: Content‑only Pakete ohne `libraries/*` liefern `400 missing_libraries` + `detail` mit der Liste fehlender Libraries (E2E: `backend/tests_e2e/test_h5p_import_errors_e2e.py`).
- ✅ Browser‑UX (Player): H5P core assets sind provisioniert (`h5p-service/vendor/h5p/core`, aus `h5p-php-library` tag `1.27.0`) und werden über `/h5p/core/*` ausgeliefert (E2E: `backend/tests_e2e/test_h5p_assets_e2e.py`).
- ✅ Library Provisioning (Trusted‑Content): Lehrkräfte können Content‑Type Libraries installieren via `POST /h5p/libraries/import` (Upload `.h5p`), und installierte Libraries via `GET /h5p/libraries` prüfen.
- ✅ Library Provisioning ist in der Praxis verifiziert: Ein offizieller H5P.org‑Export (z. B. Multiple Choice) enthält Libraries **inkl.** Assets wie Fonts; Upload via `/h5p/libraries/import` installiert die enthaltenen Libraries. Danach lassen sich “content‑only” Pakete ohne `missing_libraries` importieren.
- ⏳ Browser‑UX (Editor): echte Editor‑UI (Lumi Web Components) + H5P editor core assets (`h5p-service/vendor/h5p/editor`) sauber provisionieren.

Verifikation (lokal): Content‑Type Libraries installieren (Beispiel: MultiChoice)
1) Beispiel‑`.h5p` (enthält Libraries) herunterladen:
   - `curl -L -o .tmp/multiple-choice-713.h5p https://h5p.org/sites/default/files/h5p/exports/multiple-choice-713.h5p`
2) Als Lehrkraft in der UI Libraries installieren:
   - `https://app.localhost/h5p/editor` → “Install library package (.h5p)”
   - Hinweis: `POST /h5p/libraries/import` ist Teacher‑only + Same‑Origin‑CSRF (Origin/Referer).
3) Installation prüfen:
   - UI: `https://app.localhost/h5p/libraries` (erwartet u. a. `H5P.MultiChoice-1.16`)
   - oder Dateisystem: `ls -1 supabase/storage/h5p/libraries | rg 'H5P\\.MultiChoice-1\\.16'`
4) Content importieren und Player öffnen:
   - Content‑Import: `https://app.localhost/h5p/editor` → “Import .h5p”
   - Player: `https://app.localhost/h5p/player?content_id=<id>`

### Phase 2 – Teaching UI (2–3 Tage)
- SSR‑Seite für H5P Editor in GUSTAV; speichern liefert `content_id`.
- Task‑Konfiguration speichert `unit_tasks.kind='h5p'` + `h5p_content_id`.
- Contract‑First/TDD: `api/openapi.yml` + Supabase‑Migration + `pytest` grün für `unit_tasks` (inkl. `h5p`‑Objekt in Task Create/Update/Read).

### Phase 3 – Learning UI + xAPI ingest (2–3 Tage)
- Student‑Seite rendert Player; Listener POSTet Completion an Learning‑API.
- Abgabe‑Historie zeigt Score/Status.
- Contract‑First/TDD: `api/openapi.yml` + Supabase‑Migration + `pytest` grün für `learning_submissions.kind='h5p'` und H5P Completion ingest (Idempotency, max_attempts, auto/ai/hybrid).

### Phase 4 – Feedback‑Modi (2–3 Tage)
- `evaluation_mode=auto`: sofortige Abgabe‑Finalisierung (ohne Worker).
- `evaluation_mode=ai/hybrid`: Worker‑Queue + KI‑Feedback; hybrid speichert Score zusätzlich.

### Phase 5 – Security Hardening (laufend, vor Pilot)
- CSP‑Tightening: von permissiver `/h5p`‑CSP → minimal nötige Direktiven (Player + Editor), ohne global CSP zu lockern.
- Library Governance (Trusted‑Content): install/update nur Teacher (inkl. Admin); Provenance/Version‑Pinning + Audit‑Log (wer hat welches Paket wann importiert/aktualisiert).
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

## Entscheidungen (Stand 2025‑12‑23)
1) **Storage**: Filesystem bind mount `./supabase/storage/h5p` → `/data/h5p` (siehe “Storage – Optionen & Entscheidung”).
2) **CSP**: PoC/MVP akzeptiert permissive CSP **nur** auf `/h5p/*` (Hardening folgt in Phase 5).
3) **Phase‑1 Proof für Save**: “Save” wird in Phase 1 deterministisch über Export→Re‑Import→Reload nachgewiesen (ohne Browser‑Automation).
4) **Security model**: Trusted‑Content – alle Lehrkräfte (`teacher`, inkl. Admin) dürfen H5P Packages/Libraries importieren; Schüler konsumieren nur kuratierten Content (Packages gelten als Code‑Supply‑Chain).
5) **Core Assets**: H5P core files werden aus `h5p-php-library` tag `1.27.0` vendored in `h5p-service/vendor/h5p/core`, damit `/h5p/core/*` im Browser zuverlässig funktioniert (ohne Runtime‑Downloads).
6) **Library Provisioning (MVP)**: Libraries werden initial per Upload installiert (`POST /h5p/libraries/import`), damit “content-only” Pakete importierbar sind (ohne Hub/Internet im Default‑Betrieb).
   - Praxis: Libraries können aus offiziellen H5P.org‑Exports stammen (Examples & downloads), die die Library‑Ordner bereits enthalten.
   - Hinweis: Der Default‑Endpoint `https://api.h5p.org/v1/content-types/` liefert aktuell (2025‑12‑23) `404`, daher ist Hub‑Sync in Phase 1 bewusst deaktiviert (`fetchingDisabled=1`).
7) **Libraries sind admin‑verwaltet (Betrieb)**: Welche Content Types installiert sind, entscheidet der Admin (bzw. eine dafür verantwortliche Lehrkraft). GUSTAV liefert in Phase 1 keine “install all libraries” Automatik; fehlende Libraries werden beim Import als `missing_libraries` zurückgemeldet und dann gezielt per Upload nachinstalliert.

## Offene Fragen
1) **CSP Hardening**: Welche minimalen Direktiven brauchen wir für Pilot/Hardening? (eval/inline/workers).
2) **AI‑Scope**: Welche H5P Content Types werden für `evaluation_mode=ai` initial erlaubt (Essay/ShortAnswer)?
3) **Event‑Retention**: Speichern wir nur Completion oder auch answered‑Events? Wie lange? (DSGVO/Datensparsamkeit).
4) **Versuchszählung**: Semantik von `max_attempts` bei H5P (nur „completed“ zählt vs. auch Retry‑UI).
