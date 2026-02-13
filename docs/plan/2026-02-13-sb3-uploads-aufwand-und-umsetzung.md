# Plan: Scratch-Integration in GUSTAV (Embed + SB3 + automatische Auswertung) (2026-02-13)

Status: vorgeschlagen (aktualisiert)

## Ziel
- Das Zielbild ist ein Hybrid-Flow:
  - Embedded Scratch-Player/Editor in der Lernansicht.
  - Abgabe als `.sb3`-Snapshot in GUSTAV.
  - Automatische Auswertung und Feedback analog zum bestehenden Learning-Mechanismus (`analysis_json` + `feedback_md`).
- Die Bewertung darf nicht von volatilen Frontend-Events aus einem Fremd-Embed abhaengen. Source-of-Truth ist die in GUSTAV gespeicherte Submission.

## Produktentscheidung (fix fuer diesen Plan)
1. Scratch wird als eigener Task-Typ (`Task.kind=scratch`) eingefuehrt.
2. Schueler bearbeiten Aufgaben in einem eingebetteten Scratch-Player/Editor.
3. Zur Bewertung wird immer ein `.sb3` eingereicht (Upload/Finalize/Submission in GUSTAV).
4. Die Auswertung laeuft asynchron im bestehenden Learning-Workerflow (kein eigener Parallel-Stack fuer Feedback).
5. Visual bleibt upload-only und unveraendert; kein semantischer Mix zwischen `visual` und `scratch`.

## Kurzfazit Aufwand
- Phase A (Contract + Task-Typ + Player-Embed): P50 4-6 PT, P80 7-9 PT
- Phase B (Editor-Embed + SB3-Abgabe aus dem Editor): P50 6-10 PT, P80 11-15 PT
- Phase C (SB3-Validierung + Security Hardening): P50 3-5 PT, P80 6-8 PT
- Phase D (Scratch-Analyseadapter + Feedback-Synthese): P50 15-24 PT, P80 25-40 PT
- Gesamt: P50 28-45 PT, P80 49-72 PT
- Zeitachse bei 1 Entwickler:
  - P50: 6-9 Wochen
  - P80: 10-14 Wochen

Haupttreiber:
- Nicht das Embed an sich, sondern die sichere, reproduzierbare, didaktisch belastbare Auswertung.

Annahmen fuer die Schaetzung:
- Reuse des bestehenden Learning-Submission- und Worker-Stacks (kein zweiter Pipeline-Stack).
- Kein neues separates Laufzeitsystem fuer Bewertungen ausser kontrollierter Scratch-Analyseadapter.
- Kein Produkt-Scope fuer kollaboratives Live-Editing oder persistente Scratch-Cloud-Daten.

Risikoaufschlaege (separat):
- Rechtliche/Datenschutz-Pruefung fuer externe Embed-Abhaengigkeiten: +2 bis +5 PT.
- Falls statt Embed auf selbst gehosteten Scratch-Editor umgeschwenkt wird: +8 bis +20 PT.

## Ist-Zustand (Codebasis)
- Upload-Policy im Learning-Kontext ist auf Bild/PDF begrenzt:
  - `backend/storage/learning_policy.py`
  - `ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png"}`
  - `ALLOWED_FILE_MIME = {"application/pdf"}`
- Submission-Validierung akzeptiert nur `kind=text|image|file|h5p` und bei `file` nur PDF:
  - `backend/web/routes/learning.py`
  - `api/openapi.yml`
- Task-Arten sind derzeit `native|h5p|visual`; kein Scratch-Typ:
  - `api/openapi.yml`
  - `docs/ARCHITECTURE.md`
- Der bestehende Worker erzeugt `analysis_json` + `feedback_md` fuer Text/Bild/PDF:
  - `backend/learning/workers/process_learning_submission_jobs.py`
  - `backend/learning/adapters/local_vision.py`
  - `backend/learning/adapters/local_feedback.py`

## Zielarchitektur (Hybrid)
1. Authoring-Ebene (Teaching):
- Lehrkraft erstellt `Task.kind=scratch`.
- Optionales Starterprojekt (blank oder `.sb3` template) und Rubrik/Checks werden konfiguriert.

2. Learning-Ebene (Student):
- Scratch-Task wird im eingebetteten Player/Editor bearbeitet.
- Beim Abgeben wird ein `.sb3`-Snapshot ueber den vorhandenen Upload-Intent/Finalize/Submission-Flow gespeichert.

3. Analyse-Ebene (Worker):
- Neuer SB3-Branch: ZIP/`project.json` validieren, Projekt parsebar machen, Features extrahieren.
- Ergebnis wird wie bei anderen Submissions auf vorhandene Felder gemappt:
  - `analysis_json` (strukturiert, versioniert)
  - `feedback_md` (formatives Feedback)

4. Teaching-Live/Detail:
- Neueste Scratch-Submission erscheint in denselben Teaching-Endpunkten wie andere Aufgaben.
- Keine Sonderlogik fuer Feedback-Speicherung ausser task-spezifischer Darstellung.

## User Stories
1. Als Schueler moechte ich Scratch direkt in GUSTAV im eingebetteten Editor bearbeiten, damit ich die Plattform nicht verlassen muss.
2. Als Schueler moechte ich meine Scratch-Loesung als `.sb3` abgeben koennen, damit sie gespeichert und bewertet wird.
3. Als Lehrkraft moechte ich Scratch-Aufgaben mit Starterprojekt und Bewertungsregeln anlegen, damit Aufgaben reproduzierbar auswertbar sind.
4. Als Lehrkraft moechte ich automatisches Feedback fuer Scratch-Abgaben in derselben Qualitaet wie bei anderen Aufgaben, damit ich entlastet werde.

## BDD-Szenarien (Given-When-Then)
1. Scratch-Task renderbar:
   Given ein freigeschalteter `Task.kind=scratch`
   When ein eingeschriebener Schueler die Task-Seite aufruft
   Then sieht er den eingebetteten Scratch-Player/Editor mit gueltiger Session-Konfiguration.

2. Editor zu Submission:
   Given ein Schueler arbeitet im eingebetteten Editor
   When er "Abgeben" klickt
   Then wird ein `.sb3`-Snapshot hochgeladen und als Learning-Submission persistiert.

3. Happy Path Upload Intent:
   Given ein Scratch-Task ist sichtbar
   When der Schueler einen Upload-Intent fuer `.sb3` anfragt
   Then antwortet die API `200` mit SB3 in `accepted_mime_types`.

4. Security Invalid Archive:
   Given eine Datei mit `.sb3`-Endung ohne gueltige ZIP-Signatur
   When Finalize/Submission validiert
   Then antwortet die API `400` mit `detail=invalid_sb3_archive`.

5. Security Missing project.json:
   Given ein valides ZIP ohne `project.json`
   When Finalize/Submission validiert
   Then antwortet die API `400` mit `detail=missing_project_json`.

6. Security Not authorized:
   Given ein nicht berechtigter Nutzer
   When er Scratch-Session oder Upload-Intent anfragt
   Then antwortet die API fail-closed mit `401/403/404` gemaess bestehendem Contract.

7. Analyse abgeschlossen:
   Given eine gueltige Scratch-Submission
   When der Worker den Job verarbeitet
   Then stehen `analysis_json` und `feedback_md` im bestehenden Submission-Datensatz.

8. Teaching Detail:
   Given eine bereits analysierte Scratch-Submission
   When Lehrkraft die Latest-Detail-API aufruft
   Then sieht sie Bewertung und Feedback im bestehenden Detailmodell.

9. Regression Visual:
   Given `Task.kind=visual`
   When ein Schueler Text statt Upload sendet
   Then bleibt die bisherige upload-only-Regel unveraendert aktiv.

## Contract-First: API-Aenderungen (OpenAPI zuerst)
- Datei: `api/openapi.yml`

1. Schema-Erweiterungen (governance-konform):
- `Task.kind` enum: `native|h5p|visual|scratch`.
- Neues Schema `ScratchTaskConfig`:
  - `additionalProperties: false`
  - Felder (MVP):
    - `starter_source` enum: `blank|material_sb3`
    - `starter_material_id` uuid nullable
  - Validierung:
    - `starter_source=material_sb3` erfordert `starter_material_id`.
    - `starter_source=blank` erfordert `starter_material_id=null`.
- `Task`, `TaskCreate`, `TaskUpdate` erhalten optionales Feld `scratch`.
- Mutually exclusive analog zu bestehenden Task-Typen:
  - genau eines von `h5p|visual|scratch` oder keines (native), sonst `400 invalid_task_kind_config`.
- Neue Detailcodes bei Task-Create/-Update:
  - `invalid_scratch_config`
  - `invalid_task_kind_config` (bestehend, aber mit Scratch-Fall ergaenzt)

2. Learning Scratch Session Endpoint:
- Neuer Endpoint:
  - `GET /api/learning/courses/{course_id}/tasks/{task_id}/scratch/session`
  - `operationId: getLearningScratchSession`
  - `x-permissions.requiredRole: student`
  - `x-security-notes`:
    - Same-origin fuer browserinitiierte Requests
    - fail-closed fuer Mitgliedschaft/Freigabe/Task-Kind (404)
- Response-Vertrag:
  - `200` mit `Cache-Control: private, no-store`
  - `400` detail: `invalid_uuid | invalid_task_id | invalid_task_kind`
  - `401` unauthenticated
  - `404` not found / not released / not member / not scratch-task

3. Learning Upload + Submission (SB3):
- `StudentUploadIntentRequest.mime_type` erweitert:
  - `application/x.scratch.sb3`
  - `application/octet-stream` nur als tolerierter Browser-Fallback mit serverseitiger Inhaltspruefung.
- `POST /api/learning/courses/{course_id}/tasks/{task_id}/upload-intents`:
  - `accepted_mime_types` enthaelt SB3-Typ.
  - `400` detail bleibt kompatibel (`mime_not_allowed`), plus Submission-seitige harte Dateipruefung.
- `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions`:
  - `kind=file` fuer SB3 erlauben.
  - `400` detailcodes erweitern:
    - `invalid_sb3_archive`
    - `missing_project_json`
    - `invalid_scratch_submission_kind` (wenn Task-Kind scratch, aber unpassender Body)
  - `202` fuer asynchrone Scratch-Analyse (kein synchroner Score-Shortcut wie H5P).

4. Teaching Endpunkte:
- Bestehende Task-Create/-Update-Endpunkte behalten ihr Pattern:
  - `x-permissions.requiredRole: teacher`
  - `authorOnly: true`
  - `x-security-notes` mit CSRF same-origin
- Teaching-Material-Upload/Finalize um SB3 erweitern inkl. identischer Security-Error-Semantik.

5. Contract-Governance-Checkliste (verpflichtend):
- Jede neue/angepasste Operation dokumentiert:
  - `x-permissions`
  - `x-security-notes`
  - `Cache-Control: private, no-store` auf Success/Error Antworten
  - explizite `400` detailcodes mit Beispielen

## Datenbankschema / Migration (Entwurf)
Datei: `supabase/migrations/<timestamp>_scratch_embed_sb3_pipeline.sql`

1. `unit_tasks`:
- Entweder neue Scratch-Spalten oder ein `scratch_config jsonb` (bevorzugt fuer KISS und Erweiterbarkeit).
- Konsistenz-Constraint:
  - `kind='scratch'` => `scratch_config` muss gesetzt/gueltig sein.
  - `kind!='scratch'` => `scratch_config` muss `NULL` sein.

2. Bewertungsregeln pro Scratch-Task:
- Tabelle `public.unit_task_scratch_specs`:
  - `task_id uuid primary key references public.unit_tasks(id) on delete cascade`
  - `version int not null default 1`
  - `checks_json jsonb not null`
  - `time_limit_ms int not null default 5000`
  - `memory_limit_mb int not null default 128`
  - `created_at timestamptz not null default now()`
  - `updated_at timestamptz not null default now()`

3. `learning_submissions`:
- Keine zwingenden neuen Spalten fuer MVP (SB3 kann ueber vorhandenes `kind=file` + `mime_type` laufen).

4. RLS:
- Lesen der Scratch-Specs fuer Schueler nur indirekt ueber sichere Use-Cases.
- Schreiben der Specs nur Lehrkraft/Owner/Admin.

## TDD-Plan (Red-Green-Refactor)
1. Red: OpenAPI Contract-Tests
- Task-Kind `scratch` + Request/Response-Modelle.
- Neuer Scratch-Session-Endpoint.
- SB3 in Upload-Intent/Submissions.
- Governance-Assertions:
  - `x-permissions` vorhanden und korrekt.
  - `x-security-notes` vorhanden.
  - `Cache-Control: private, no-store` auf dokumentierten 2xx/4xx/5xx Antworten.
  - neue `400.detail` Codes per Example/Enum abgesichert.

2. Red: API-Verhaltenstests Learning
- Scratch-Session nur fuer berechtigte Schueler.
- Upload/Submission Happy Path fuer `.sb3`.
- Invalid ZIP / Missing `project.json`.

3. Red: API-Verhaltenstests Teaching
- Scratch-Task anlegen/aktualisieren.
- Material-Upload `.sb3`.

4. Green: minimale Implementierung
- Task-Kind und Session-Endpoint.
- SB3 MIME + Inhaltsvalidierung.
- Submission-Queue-Eintrag fuer Scratch.

5. Red/Green: Worker-Integration
- Neuer Scratch-Analyseadapter:
  - parse, feature extraction, scoring, mapping nach `analysis_json`.
- Feedback-Synthese ueber bestehenden Mechanismus (`feedback_md`).

6. Refactor
- Gemeinsames Modul fuer SB3-Validierung:
  - `backend/storage/sb3_validation.py`
- Keine duplizierte Logik zwischen Learning/Teaching/Worker.

## Implementierungsplan in Schritten
1. Schritt 1: Contract + fehlschlagende Tests
- OpenAPI fuer `Task.kind=scratch`, Session, SB3 erweitern.
- Contract- und API-Tests rot machen.
- Governance-Drift verhindern:
  - maschinenlesbare Permissions und Security-Notes im Vertrag von Anfang an erzwingen.

2. Schritt 2: Scratch-Task + Embedded Player/Editor
- SSR/JS Integrationspfad fuer Scratch.
- Session-Endpoint und Rechtepruefungen.

3. Schritt 3: SB3-Abgabe aus Embedded Flow
- Upload-Intent/Finalize/Submission fuer SB3 verdrahten.
- Storage-Key, Hash und Dateigroesse wie bei bestehenden Uploads absichern.

4. Schritt 4: SB3 Security Hardening
- ZIP Signatur, `project.json`, harte Limits (entries, ratio, unpacked bytes).
- Fail-closed Fehlercodes und Telemetrie.

5. Schritt 5: Analyse + Feedback
- Scratch-Analyzer in Worker einhaengen.
- Ergebnisse in bestehende Submission-Felder schreiben.
- Teaching-Live/Latest-Detail Darstellung validieren.

6. Schritt 6: Doku + Rollout
- `docs/CHANGELOG.md`
- `docs/references/learning.md` und `docs/references/learning_ai.md` aktualisieren.
- Optional wissenschaftliche Doku fuer Bewertungslogik unter `docs/science/`.
- API-Governance-Pruefung im PR:
  - Contract (OpenAPI) und Runtime-Responses auf Header/Status/Detailcode-Deckung gegenchecken.

## Risiken und Gegenmassnahmen
1. Embed-/Token-Abhaengigkeit von externen Scratch-Endpoints:
- Massnahme: Bewertung nie von externen Runtime-Events ableiten; `.sb3` bleibt Source-of-Truth.

2. MIME unzuverlaessig:
- Massnahme: Endung + Inhaltspruefung (ZIP + `project.json`) statt nur Browser-MIME.

3. ZIP-Bomb/Path Traversal:
- Massnahme: sichere ZIP-Inspektion ohne ungefiltertes Extrahieren, harte Ressourcenlimits.

4. Nicht reproduzierbare Bewertung:
- Massnahme: deterministische Checks in `unit_task_scratch_specs`, feste Runtime-Limits, versionierte Analyse.

5. Scope-Explosion im Editor:
- Massnahme: MVP klar begrenzen (core editor/player + submit), erweiterte Features spaeter.

## Akzeptanzkriterien (DoD)
- Scratch-Aufgaben sind als eigener Task-Typ anlegbar und fuer Schueler eingebettet nutzbar.
- Schueler koennen `.sb3` aus dem Embedded-Flow abgeben.
- Ungueltige SB3-Dateien werden fail-closed mit klaren Detailcodes abgewiesen.
- Scratch-Abgaben laufen durch den bestehenden asynchronen Analyse/Feedback-Mechanismus.
- Teaching kann Scratch-Ergebnisse ueber bestehende Detail-Endpunkte einsehen.
- OpenAPI, Migrationen, Tests und Implementierung sind konsistent (Contract-first, lokal=prod).

## Quellen (Recherche)
- GUSTAV-Codebasis:
  - `backend/storage/learning_policy.py`
  - `backend/web/routes/learning.py`
  - `api/openapi.yml`
  - `backend/learning/workers/process_learning_submission_jobs.py`
- Scratch Embed (offizieller Webclient-Code):
  - https://github.com/scratchfoundation/scratch-www/blob/develop/src/lib/social.js
  - https://github.com/scratchfoundation/scratch-www/blob/develop/src/views/preview/embed-view.jsx
  - https://github.com/scratchfoundation/scratch-www/blob/develop/src/lib/storage.js
- Scratch VM / Parser:
  - https://github.com/scratchfoundation/scratch-vm/blob/develop/src/virtual-machine.js
  - https://unpkg.com/scratch-parser@6.0.0/lib/unzip.js
  - https://unpkg.com/scratch-parser@6.0.0/lib/unpack.js
- Sicherheit:
  - https://developer.mozilla.org/en-US/docs/Web/API/Blob/type
  - https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
  - https://www.iana.org/assignments/media-types/media-types.xhtml
