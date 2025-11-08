# Plan: KI-Integration (Vision/Handwriting Analysis + Feedback) — Lernen

Aktualisierung (Stand: 2025-11-05)
- Vision (produktiv, lokal über Ollama): Minimaler Local‑Adapter implementiert und im Worker verdrahtet. Der Worker verarbeitet `pending`/`extracted` Submissions, ruft Vision → Feedback auf und markiert bei Erfolg `completed`; Transient/Permanent‑Fehler werden korrekt klassifiziert und behandelt.
- PDF→Bilder→Persistenz: Rendering/Preprocess vorhanden; Seiten werden persistiert und Status `extracted` gesetzt. Supabase‑Adapter unterstützt `put_object(...)`.
- Tests: Adapter‑ und Worker‑Pfad mit lokalen (gefakten) Ollama/DSPy‑Clients abgedeckt; End‑to‑End‑Pfad für Text und Bild grün (lokal/CI mit Stubs).
- Terminologie: durchgängig „Vision“ (nicht „OCR“).

Nächste Schritte (Iteration unmittelbar als Nächstes)
- SSR/HTMX: Task‑Verlauf um Thumbnails und extrahierten Text erweitern; Polling bei `completed` beenden; zielgerichtete UI‑Tests ergänzen.
- Produktions‑Härtung Vision/Feedback: Timeouts/Backoff final justieren; Logging minimieren; Healthchecks (Ollama) dokumentieren; Modell‑Pull in Runbook verankern.
- Queue/Worker Ops: Metriken/Counter (bereits vorhanden) sichtbarer machen; einfache Alert‑Schwellen definieren.


Ziel: Zwei KI-Funktionen sauber, testgetrieben und DSGVO‑konform integrieren:
1) Vision/Handwriting Analysis: Extrahiert nutzbaren Text aus handschriftlichen Einreichungen, Diagrammen und gescannten PDFs (image/file) und schreibt ihn als Markdown in `text_body` (kanonische Textquelle für die Bewertung).
2) Feedback: Generiert formatives Feedback zu jeder Submission (text/image/file) auf Basis der Aufgaben‑Kriterien (`criteria`).

Leitplanken: KISS, Security first, FOSS, Clean Architecture, Contract‑First (OpenAPI), Test‑First (TDD, Red‑Green‑Refactor), Glossar‑Konsistenz (`docs/glossary.md`).

Begriffe (Glossar-konsistent): Submission, Task, Criteria, Vision (Handschrift/Diagramme/OCR), Analysis, Feedback, `student_sub` (OIDC sub, ohne PII).

---

## Scope & Nicht‑Ziele

In Scope (Iteration 1, asynchron, lokal):
- Vision/Handwriting Analysis (Bild: JPEG/PNG; Datei: PDF) inkl. OCR, Diagramm-/Form-Erkennung und Layout-Hinweisen mit lokalem Backend (Ollama/DSPy) — keine Cloud.
- Feedback-Generierung über denselben lokalen Stack (Stub zunächst, später DSPy/Ollama), deterministisch testbar.
- `text_body` ist die kanonische Quelle (Markdown) für alle Arten von Submissions: Schülertext oder Vision‑Extrakt.
- Asynchroner Verarbeitungs-Flow: HTTP-Endpunkt speichert Submission mit `analysis_status=pending`, Worker verarbeitet Vision‑Analyse + Feedback und markiert Submission als `completed` oder `failed`.

Nicht in Scope (Iteration 1):
- Externe KI-Dienste, Cloud-APIs oder Datentransfer außerhalb der lokalen Infrastruktur.
- Fortgeschrittene Rubrics/Mehrsprachigkeit, komplexe Metriken.

---

## User Stories (validiert)
- Als Schüler reiche ich Bild/PDF ein; das System extrahiert verwertbaren Text (Markdown) aus Vision/Handschrift/Diagrammen und speichert ihn so, als hätte ich Text eingetippt, damit Feedback einheitlich möglich ist.
- Als Schüler reiche ich Text ein; das System analysiert nach Kriterien und gibt mir formative Rückmeldung.
- Als Schüler sehe ich pro Abgabe Status, verwendeten Text (getippt oder Vision‑Extrakt) und Feedback zur Selbstreflexion.
- Als Lehrer will ich, dass Vision‑Analyse/Feedback lokal (Ollama/DSPy), DSGVO‑konform, mit Zeitlimits und minimalen Logs laufen.

---

## BDD‑Szenarien (Given‑When‑Then)

Happy Path
1) Text‑Submission läuft standardmäßig asynchron durch Feedback-Worker
- Given: Aufgabe ist freigegeben, Schüler ist Mitglied, `max_attempts` erlaubt neuen Versuch
- When: POST Submissions mit `{ kind: 'text', text_body: '...' }`
- Then: 202, `analysis_status='pending'`, `text_body`=übergebener Text, Worker-Job existiert
- And: Wenn der Worker erfolgreich abschließt, `analysis_status`→`completed`, `feedback` gesetzt, `attempt_nr` korrekt

2) Bild‑Submission (JPEG/PNG) mit asynchroner Vision‑Analyse (OCR/Diagramme)
- Given: Gültige Metadaten (`mime_type`, `size_bytes` ≤ 10 MiB, `sha256`), Abschnitt freigegeben
- When: POST Submissions mit `{ kind: 'image', storage_key, mime_type, size_bytes, sha256 }`
- Then: 202, `analysis_status='pending'`, `text_body` leer, `analysis_json` leer, Worker-Job existiert
- And: Wenn der Worker erfolgreich abschließt, `analysis_status`→`completed`, `text_body`=Vision‑Extrakt (Markdown) oder Schülertext, `analysis_json` (criteria.v2) gesetzt, `feedback` gesetzt

3) PDF‑Submission mit asynchroner Vision‑Analyse
- Given: Gültige Metadaten (`mime_type='application/pdf'`, ≤ 10 MiB)
- When: POST Submissions mit `{ kind: 'file', ... }`
- Then: 202, `analysis_status='pending'`, Worker-Job geplant
- And: Nach Worker-Lauf wie oben `completed` mit Vision‑Extrakt (Text) und Feedback

4) (Optional, später) Opportunistischer Fast‑Path
- Hinweis: Für eine spätere Iteration denkbar. In Iteration 1 bewusst deaktiviert.
- Der Contract listet 201 lediglich informativ; Standard bleibt 202/pending für alle Submission‑Typen.

Edge Cases
5) Maximalversuche
- Given: `max_attempts = 2`, Schüler hat 2 Abgaben
- When: POST dritte Abgabe
- Then: 400, `detail: max_attempts_exceeded`

6) Idempotency
- Given: Wiederholung mit gleichem `Idempotency-Key`
- When: POST erneut
- Then: Response entspricht der bereits existierenden Submission (202 pending oder 201 completed), keine Duplikate

7) Größe/MIME invalid
- Given: Datei > 10 MiB oder `mime_type` nicht erlaubt
- When: POST
- Then: 400, `detail: invalid_image_payload | invalid_file_payload`

Fehlerfälle
8) Nicht Mitglied
- Given: Schüler ist nicht Mitglied
- When: POST Submission
- Then: 403

9) Abschnitt/Task nicht freigegeben
- Given: Mitglied, aber Task nicht sichtbar
- When: POST Submission
- Then: 404

10) Worker markiert Vision‑Analyse‑Fehler
- Given: Vision‑Adapter wirft dauerhaften Fehler (nach Retries)
- When: Worker verarbeitet Submission
- Then: Submission `analysis_status='failed'`, `error_code='vision_failed'`, `vision_last_error` befüllt, `text_body` bleibt leer

11) Worker markiert Feedback‑Fehler
- Given: Feedback-Adapter schlägt fehl
- When: Worker verarbeitet Submission
- Then: Submission `analysis_status='failed'`, `error_code='feedback_failed'`, Audit-Log geschrieben

12) Retry bis Erfolg
- Given: Vision‑Adapter ist beim ersten Versuch nicht erreichbar
- When: Worker führt den Job aus, erster Versuch scheitert (transient)
- Then: Job wird erneut eingeplant; beim zweiten Versuch gelingt die Vision‑Analyse → Submission `analysis_status='completed'`

---

## Update 2025‑11‑01 — Worker Umsetzung (Felix & Lehrteam)

- **User Story (Worker)**  
  Als Betreiber möchte ich, dass der `learning-worker` jede Pending‑Submission zuverlässig verarbeitet: Job leasen, Vision-/Feedback‑Adapter ausführen, Submission auf `completed` oder `failed` setzen und den Job entweder ack’n oder mit Backoff erneut freischalten.

- **Worker-BDD-Vertiefung**  
  - Happy Path: Pending Submission → Vision liefert Markdown → Feedback erzeugt Analyse → Submission `completed`, `text_body`, `analysis_json` und `feedback_md` gesetzt, Job ge-acked.  
  - Vision-Fehler: Adapter scheitert dreimal → Submission `failed`, `error_code=vision_failed`, `vision_last_error` ausgefüllt.  
  - Feedback-Fehler: Vision erfolgreich, Feedback scheitert → Submission `failed`, `error_code=feedback_failed`, Vision-Felder bleiben bestehen.  
  - Transient Fehler: erster Versuch schlägt fehl → `retry_count` + `visible_at` werden angepasst, nächster Worker-Lauf schließt den Job erfolgreich ab.  
  - Leasing-Sicherheit: Jobs besitzen `lease_key` und `leased_until`; nach Timeout erscheinen sie erneut in der Queue (at-least-once).

- **API/OpenAPI Ergänzungen**  
  - `LearningSubmission.error_code` akzeptiert `vision_failed`, `feedback_failed`, `vision_retrying`.  
  - `analysis_json` verweist auf `AnalysisJsonCriteriaV1` mit `schema`, `score`, `criteria_results[].explanation_md`.  
  - `POST /api/learning/.../submissions`: Beschreibung hebt 202 + Worker-Queue hervor; 201 bleibt optionaler Fast-Path (derzeit deaktiviert).

- **Migration-/Schema-Notizen**  
  - Spalten in `learning_submissions` heißen zukünftig `vision_attempts`, `vision_last_error`, `vision_last_attempt_at` (ersetzen `ocr_*`).  
  - Queue-Tabelle `learning_submission_jobs` mit Leasing-Feldern (`lease_key`, `leased_until`, `retry_count`, `visible_at`); Status `queued`/`leased`/`failed`, erfolgreiche Jobs werden gelöscht. Legacy-Tabellen (`learning_submission_ocr_jobs`) werden bei Migration automatisch umbenannt und alle Constraints angepasst.  
  - Grants bleiben bei `gustav_limited`; Statuswechsel `pending → completed|failed` laufen über SECURITY-DEFINER-Funktionen für den Worker.

---

## Architektur & Adapter

Prinzip: Clean Architecture. Use Cases kennen keine Web‑ oder Modell‑Details. KI wird über Ports injiziert.

Ports (Domain‑nah):
- `SubmissionStoragePort` (Presign, Verify, optional Download-Stream für lokalen Vision‑Dienst)
- `LearningSubmissionQueuePort` (enqueue, lease_one, ack_success, nack_retry)
- `VisionAdapterProtocol` (`extract(submission) -> VisionResult`), wobei `VisionResult.text_md` den Markdown‑Extrakt für `text_body` liefert
- `FeedbackAdapterProtocol` (`analyze(criteria, text_body_md) -> FeedbackResult`), wobei `FeedbackResult.feedback_md` und `FeedbackResult.analysis_json` (criteria.v2) enthält
- Hilfs‑Abstraktion `TextSource.get_text(submission) -> str` (liefert Schüler‑Markdown oder ruft Vision‑Extraktion auf)

Flow:
1. HTTP-Layer validiert Request, ruft Use Case `IngestLearningSubmission`.
2. Use Case führt Autorisierungs-Checks aus, verifiziert Upload, persistiert Submission mit `analysis_status='pending'` und legt den Job über `LearningSubmissionQueuePort` an (Enqueue muss erfolgreich sein; andernfalls 500/501).
3. Worker `process_learning_submission_jobs` leased Jobs, bezieht Text über `TextSource` (direkter Schülertext oder Vision‑Extraktion), ruft immer den Feedback‑Adapter auf, aktualisiert Submission (`analysis_status='completed'`, `text_body`, `analysis_json`, `feedback_md`) und ack’t den Job (löscht ihn) oder markiert `failed`.
4. Fehlerbehandlung: Retries (max. 3, exponential backoff). Bei dauerhaften Fehlern setzt Worker `error_code` (`vision_failed`, `feedback_failed`) und persistiert `vision_last_error`.

Fast-Path (später):
- Nice-to-have für eine spätere Iteration. In Iteration 1 nicht umgesetzt. Standard bleibt 202/pending für alle Submission-Typen; 201 ist derzeit nur vertraglich als optional dokumentiert, aber technisch nicht aktiviert.

Implementierungen:
- `StubVisionAdapter` und `StubFeedbackAdapter` für Tests/Entwicklung (deterministisch, schnell).
- `LocalVisionAdapter` (Ollama Vision über DSPy) und `LocalFeedbackAdapter` (Ollama Textmodell) für Produktion; beide laufen auf demselben Server (keine Cloud).
- Queue-Port bildet auf eine PostgreSQL‑gestützte Tabelle (`learning_submission_jobs`) ab.

Konfiguration (.env):
- `AI_FEEDBACK_MODEL` legt das Text-/Feedback‑Modell fest (z. B. `ollama:qwen2.5-instruct:7b`).
- `AI_VISION_MODEL` bestimmt das Vision‑/Handwriting‑Modell (z. B. `ollama:qwen2.5-vl:7b`); Worker lädt das Modell erst bei Job‑Bearbeitung.
- Standardwerte zeigen auf Stub-Modelle (`stub-feedback`, `stub-vision`), damit Tests und lokale Entwicklung deterministisch bleiben.
- Konfigurationswechsel erfolgen über `.env` und werden vom Dependency-Injection-Layer beim Bootstrapping gelesen.

Security/Privacy:
- KI läuft lokal via Ollama; Kommunikation passiert ausschließlich über Unix-Socket/localhost.
- Timeouts (z. B. 30s Vision, 15s Feedback) und Ressourcen‑Limits verhindern Hänger; Job wird andernfalls als `failed` protokolliert.
- Minimale Logs: keine Rohbilder/Texte in Logfiles, nur Hash/IDs/Timing. Audit-Log speichert Fehlercodes ohne personenbezogene Daten.
- RLS unverändert (Insert-Guard; kein Datenleck über Fehlermeldungen/IDs).

---

## API Contract‑Änderungen (OpenAPI Entwurf)

Aktueller Contract deckt Submissions bereits ab. Anpassungen:
  - `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions`: Beschreibung + Responses ergänzen (`202` als Standard für alle Submission‑Typen; `201` bleibt optionaler Fast‑Path‑Hinweis, derzeit nicht verwendet).
- Schema `LearningSubmission.analysis_status`: erlaubte Werte `pending`, `completed`, `failed`.
- Schema `LearningSubmission.error_code`: optional, Werte `vision_failed`, `feedback_failed`, `vision_retrying` (für Monitoring).
- `GET /api/learning/submissions/{id}` dokumentiert Polling auf dem gleichen Statusmodell (kein neues Flag nötig).

Beispiel‑Snippet:
```yaml
components:
  schemas:
    AnalysisJsonCriteriaV1:
      type: object
      additionalProperties: false
      properties:
        schema:
          type: string
          enum: ["criteria.v1"]
        score:
          type: integer
          minimum: 0
          maximum: 5
        criteria_results:
          type: array
          items:
            type: object
            additionalProperties: false
            properties:
              criterion:
                type: string
              explanation_md:
                type: string
              score:
                type: integer
                minimum: 0
                maximum: 10
    LearningSubmission:
      properties:
        analysis_status:
          type: string
          enum: [pending, completed, failed]
          description: Pending bedeutet Vision/Feedback läuft im Hintergrund.
        error_code:
          type: string
          nullable: true
          description: One of: vision_failed, feedback_failed, vision_retrying.
        text_body:
          type: string
          nullable: true
          description: Markdown-Text (Schülertext oder Vision‑Extrakt); bei pending/failed kann leer sein.
        analysis_json:
          allOf:
            - $ref: "#/components/schemas/AnalysisJsonCriteriaV1"
          nullable: true
          description: Ergebnis der kriterien‑orientierten Auswertung (normalisiert auf criteria.v2; v1 weiterhin akzeptiert).
paths:
  /api/learning/courses/{course_id}/tasks/{task_id}/submissions:
    post:
      responses:
        '202':
          description: Submission angenommen, Analyse läuft asynchron (alle Submission-Typen).
        '201':
          description: Submission analysiert (Fast-Path); nur wenn Feedback sofort erstellt werden konnte.
      x-gustav-notes:
        - Standard-Response ist 202; 201 ist opportunistisch und darf nicht garantiert werden.
```

Hinweis: Der tatsächliche OpenAPI‑Vertrag enthält auch `AnalysisJsonCriteriaV2` und modelliert `analysis_json` als oneOf(v1, v2). Der Worker normalisiert intern auf v2.

---

## Datenbank‑Änderungen (SQL‑Migration Entwurf)

Problem: Bisherige Constraints verhindern gefülltes `text_body` für Bilder und es fehlen Felder für Pending-/Failed‑States sowie eine robuste Job‑Queue (Lease/Ack statt doppeltem Finalstatus).

Migration (Skizze):
```sql
set search_path = public, pg_temp;

-- 1) Constraints für image/file anpassen (text_body optional, aber Metadaten verpflichtend)
alter table public.learning_submissions drop constraint if exists learning_submissions_image_kind;
alter table public.learning_submissions add constraint learning_submissions_image_kind
  check (
    kind <> 'image' or (
      storage_key is not null and
      mime_type in ('image/jpeg','image/png') and
      size_bytes between 1 and 10485760 and
      sha256 ~ '^[0-9a-f]{64}$'
    )
  );

alter table public.learning_submissions drop constraint if exists learning_submissions_file_kind;
alter table public.learning_submissions add constraint learning_submissions_file_kind
  check (
    kind <> 'file' or (
      storage_key is not null and
      mime_type = 'application/pdf' and
      size_bytes between 1 and 10485760 and
      sha256 ~ '^[0-9a-f]{64}$'
    )
  );

-- 2) Analyse-Status auf pending/completed/failed einschränken
alter table public.learning_submissions drop constraint if exists learning_submissions_analysis_status_check;
alter table public.learning_submissions add constraint learning_submissions_analysis_status_check
  check (analysis_status in ('pending','completed','failed'));

-- 3) Vision‑Analyse Metadaten für Worker‑Retries
alter table public.learning_submissions
  add column if not exists vision_attempts integer not null default 0,
  add column if not exists vision_last_error text,
  add column if not exists vision_last_attempt_at timestamptz;

-- 4) Job-Queue für Worker (FIFO, lokal)
-- KISS: Jobs sind transient; Erfolg → Ack (Delete). Kein 'completed' Status auf Job‑Ebene.
create table if not exists public.learning_submission_jobs (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references public.learning_submissions(id) on delete cascade,
  status text not null default 'queued' check (status in ('queued','leased','failed')),
  retry_count integer not null default 0,
  visible_at timestamptz not null default now(),
  lease_key uuid,
  leased_until timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists learning_submission_jobs_visible_idx
  on public.learning_submission_jobs (status, visible_at);
```

Leasing & Acks:
- Lease: atomare Aktualisierung auf `leased` mit `lease_key` und `leased_until` (z. B. 30s) via `for update skip locked`.
- Ack Success: löscht den Job; Ack Retry: setzt `status='queued'`, erhöht `retry_count`, verschiebt `visible_at` (Exponential Backoff).

RLS/Grants: Insert/Select bleiben; Worker‑Updates an Submission erfolgen über `SECURITY DEFINER`‑Funktionen, die nur Pending→Completed/Failed erlauben.

---

## Teststrategie (TDD)

Kontext: `pytest` gegen echte Test‑DB; externe Abhängigkeiten (Vision/Feedback) werden gemockt.

Tests (erste rote Tests):
1) `test_post_text_submission_returns_pending_and_enqueues_job`
   - Erwartet 202, `analysis_status='pending'`, Queue enthält Job mit Submission-ID.
2) `test_post_text_submission_fast_path_returns_completed_feedback`
   - Simuliert konfigurierte Fast-Path-Kapazität, erwartet 201 und `analysis_status='completed'`.
3) `test_post_image_submission_returns_pending_and_enqueues_job`
   - Erwartet 202, `analysis_status='pending'`, Queue enthält Job mit Submission-ID.
4) `test_worker_processes_pending_submission_to_completed`
   - Worker holt Job, Vision-/Feedback‑Adapter (gemockt) liefern Ergebnis → Submission `analysis_status='completed'`, `text_body` (Markdown) / `analysis_json` (criteria.v2) / `feedback_md` gesetzt.
5) `test_worker_marks_submission_failed_after_retry_limit`
   - Vision‑Adapter wirft Fehler, Worker versucht dreimal, danach `analysis_status='failed'`, `error_code='vision_failed'`, `vision_last_error` gesetzt.
6) `test_invalid_mime_or_size_rejected`
   - 400, dokumentierte Fehlerdetails.
7) `test_max_attempts_enforced`
   - 400, `detail='max_attempts_exceeded'`.
8) `test_idempotent_submission_returns_existing_row`
   - Wiederholter POST (gleiches Idempotency-Key) liefert die vorhandene Submission (Status unverändert).
9) `test_analysis_json_scores_within_ranges`
   - Validiert: `analysis_json.score` ∈ [0,5] und alle `criteria_results[].score` ∈ [0,10].

Muster: Red → minimale Implementierung → Green → Refactor (Ports klar trennen, Worker entkoppeln).

---

## Schrittweiser Umbau (Implementierungsskizze)

Iteration 1 (asynchron, lokal):
1) OpenAPI-Beschreibung aktualisieren (202 als Standard; 201 nur optional dokumentiert), Pending-Status, Fehlercodes.
2) Migration fahren (Constraints, Status-Enum, Vision-Metadaten, Job-Tabelle).
3) Use Case `IngestLearningSubmission` implementieren (Ports injizieren, Pending persistieren, Job enqueuen).
4) Worker-Service `process_learning_submission_jobs` erstellen (Stub-Adapter, Lease/Ack, Retry-Strategie, Completed/Failed-Updates).
5) Repository-Schicht anpassen (Pending-Insert, striktes Enqueue ohne „best-effort“, Status-Updates, Queue-Operationen, Audit-Logging).
6) Tests grün machen (API + Worker + Repo) mit Stub-Adaptern und echter Test-DB.

Iteration 1b (vorgezogen – jetzt umsetzen):
7) Lokale Ollama/DSPy-Adapter produktiv schalten (umschaltbar via `AI_BACKEND=stub|local`, Default weiterhin `stub`), Ressourcen‑Limits und Timeouts dokumentieren.
8) Monitoring & Observability (Metriken `analysis_jobs_inflight`, `ai_worker_retry_total`/`vision_worker_retry_total`, strukturierte Logs) beibehalten; keine Änderung am Contract notwendig.

---

## Deployment (docker-compose) – Worker-Dienst

Architektur: Der Worker läuft als separater Dienst neben `web`. Er nutzt die gleiche Codebasis, aber einen anderen Entry-Point und kann unabhängig skaliert werden.

docker-compose (Beispiel):

```yaml
  learning-worker:
    build: .
    container_name: gustav-learning-worker
    command: ["python", "-m", "backend.learning.workers.process_learning_submission_jobs"]
    volumes:
      - ./backend/learning:/app/backend/learning:z
      - ./backend/__init__.py:/app/backend/__init__.py:z
    env_file:
      - .env
    environment:
      - LOG_LEVEL=${WORKER_LOG_LEVEL:-info}
      # Default to the application login DSN; override with a dedicated
      # worker login via LEARNING_DATABASE_URL in production deployments.
      - LEARNING_DATABASE_URL=${LEARNING_DATABASE_URL:-postgresql://${APP_DB_USER:-gustav_app}:${APP_DB_PASSWORD:-CHANGE_ME_DEV}@supabase_db_gustav-alpha2:5432/postgres}
      - LEARNING_VISION_ADAPTER=${LEARNING_VISION_ADAPTER:-backend.learning.adapters.stub_vision}
      - LEARNING_FEEDBACK_ADAPTER=${LEARNING_FEEDBACK_ADAPTER:-backend.learning.adapters.stub_feedback}
      - WORKER_MAX_RETRIES=${WORKER_MAX_RETRIES:-3}
      - WORKER_BACKOFF_SECONDS=${WORKER_BACKOFF_SECONDS:-10}
      - WORKER_LEASE_SECONDS=${WORKER_LEASE_SECONDS:-45}
      - WORKER_POLL_INTERVAL=${WORKER_POLL_INTERVAL:-0.5}
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import sys; from backend.learning.workers.health import LearningWorkerHealthService; status = LearningWorkerHealthService()._probe_sync().status; sys.exit(0 if status == 'healthy' else 1)",
        ]
      interval: 30s
      timeout: 5s
      retries: 3
    networks:
      - gustav-alpha2-network
      - supabase_network_gustav-alpha2
```

Hinweise:
- Entry-Point: `backend.learning.workers.process_learning_submission_jobs` pollt die Queue `public.learning_submission_jobs`, leased Jobs, führt Vision/Feedback aus und schreibt Status zurück.
- Skalierung: Horizontal via `docker compose up --scale learning-worker=N`, vertikal über `WORKER_POLL_INTERVAL`/`WORKER_MAX_RETRIES`.
- Netzwerk/Secrets: In PROD optional dedizierter DB-User `gustav_worker` (DSN via `LEARNING_DATABASE_URL`, Passwort out-of-band setzen). Standard-Default nutzt den App‑Login (IN ROLE `gustav_limited`). Service‑Role bleibt exklusiv im Web/API‑Layer.
- Observability: Jeder Worker schreibt strukturierte Logs; Metriken wie `ai_worker_retry_total` für Alerting.

---

## Security & DSGVO
- Lokale Inferenz (Ollama) auf dedizierter Maschine/Container; kein Transport zu Drittanbietern.
- Minimal-Logging: keine Rohbilder/ganzen Texte im Log; nur Hash, Submission-ID, Laufzeit, Statuswechsel.
- Worker läuft unter Service-Account mit minimalen Rechten; Updates erfolgen über `SECURITY DEFINER`-Function (nur Pending→Completed/Failed).
- Timeouts, Ressourcen-Limits (10 MiB, MIME-Whitelist, CPU/GPU-Limits) verhindern Missbrauch und DoS.
- RLS bleibt Dreh- und Angelpunkt (Insert-Guard, `app.current_sub`), Worker authentifiziert sich über Service Key.
- CSRF-Check wie im Contract dokumentiert (same-origin Pflicht bei POST); Idempotency-Key Pflicht für wiederholte Requests.
 - Sanitizing: `text_body` wird serverseitig vor dem Rendern HTML‑saniert (XSS‑Schutz).

---

## Observability
- Strukturierte Statuswechsel (`pending` → `completed|failed`) mit `error_code` (`vision_failed`, `feedback_failed`, `vision_retrying`).
- Metriken: `analysis_jobs_inflight`, `ai_worker_duration_seconds`, `ai_worker_retry_total`, `ai_worker_failed_total`.
- Logs: Jeder Jobwechsel (enqueue, lease, success, retry, fail) als strukturierter Eintrag ohne Rohdaten.
- Alerts: `ai_worker_failed_total` und `analysis_jobs_inflight` > Threshold.

---

## Risiken & Gegenmaßnahmen
- Worker-Stau: Monitoring + Auto-Scaling (mehr Worker-Instanzen) oder Priorisierung.
- Ressourcen (GPU/CPU): Fallback auf Stub/leichteres Modell; Feature-Flag `AI_BACKEND`.
- Konsistenz: Pending→Completed-Updates ausschließlich über Repository-Funktionen mit Transaktionen; Jobs sind transient (Ack löscht Job).
- Fehlerhafte Modelle: Retries + `failed`-Status mit Audit-Log; Operator kann Submission erneut triggern.

---

## Statusupdate (aktueller Stand)

- Entscheidung: Vollständig asynchron für alle Submission‑Typen (text/image/file). Kein Feature‑Flag, kein Fast‑Path in Iteration 1.
- API: POST Submissions gibt `202` zurück und liefert `analysis_status='pending'`; `analysis_json`/`feedback` sind bei pending leer. Health-Route `/internal/health/learning-worker` ist im Contract verankert.
- Repository/Worker: Queue `learning_submission_jobs` wird strikt benutzt; der Worker leased Jobs, setzt vor Updates `app.current_sub` und räumt verwaiste Jobs auf. Vision-/Feedback‑Adapter werfen differenzierte Exceptions (`VisionTransientError`, `VisionPermanentError`, `FeedbackTransientError`, `FeedbackPermanentError`). Retry-Pfad setzt `error_code='vision_retrying'` bzw. `feedback_retrying`, Backoff basiert auf `WORKER_BACKOFF_SECONDS`, finale Fehler markieren Submission + Job mit `*_failed`.
- Monitoring: Worker emittiert strukturierte Warn-/Fehler-Logs und Metriken (`analysis_jobs_inflight`, `ai_worker_processed_total`, `ai_worker_retry_total`, `ai_worker_failed_total`). Telemetrie wird in pytest verifiziert.
- DSN/Harness‑Härtung: Die DSN‑Auflösung des Learning‑Repos respektiert `RLS_TEST_DSN`/`LEARNING_DATABASE_URL`/`DATABASE_URL`. Der Worker authentifiziert sich als `gustav_worker` und besitzt nur EXECUTE/DML-Grants auf Queue und Security-Helfer.
- Contract/OpenAPI: `analysis_status`=`pending|completed|failed`, `error_code` umfasst `vision_retrying`, `vision_failed`, `feedback_retrying`, `feedback_failed`. Neuer Pfad `/internal/health/learning-worker` liefert `LearningWorkerHealth`.
- Migrationen (angewendet via `supabase migration up`):
  - `20251103124000_learning_worker_role.sql` erstellt `gustav_worker` und hinterlegt minimale Queue-Grants.
  - `20251103124548_learning_worker_retry.sql`, `20251103131517_learning_worker_retry_patch.sql`, `20251103131552_learning_worker_json_param.sql` liefern Retry-Spalten und die Security-Definer-Helfer (`learning_worker_update_*`, `learning_worker_mark_retry`).
  - `20251103135028_learning_worker_health_probe.sql` erstellt bei Bedarf `gustav_web`/`gustav_operator` (NOLOGIN) und definiert `learning_worker_health_probe()`.
- Tests: Worker-Suite (`backend/tests/test_learning_worker_jobs.py`) deckt Pending→Completed, Vision-/Feedback-Retry, Retry-Limit/Failed, Metrik-Emission und strukturierte Logs ab. Health-Endpunkt-Tests (`backend/tests/test_learning_worker_health_endpoint.py`) prüfen Auth, 200/503-Payloads. Security-Tests (`backend/tests/test_learning_worker_security.py`) verifizieren die Security-Definer-Funktionen inkl. Pending-Guards und Retry-Helfer.
- UI/SSR: Weiterhin pending → Anzeige „Analyse läuft“. Text-Fallback nutzt `text_body`, das jetzt Vision-Extrakte enthalten kann.

---

## Repriorisierung: KI-Integration (Ollama/DSPy) jetzt

Motivation: Die asynchrone Architektur (Queue, Worker, Security‑Definer, Tests) steht stabil. Wir ziehen deshalb die produktive Anbindung der lokalen Modelle vor, behalten aber Stub als Default bei, um Determinismus in Tests sicherzustellen.

Leitplanken (unverändert): KISS, Security first (keine Cloud), Contract‑First (kein API‑Change nötig), TDD (Tests vor Implementierung), Clean Architecture (Adapter über Ports).

Ziele (Iteration 1b → jetzt):
- „Local“‑Adapter für Vision und Feedback implementieren (Ollama/DSPy), austauschbar zu Stubs über Env‑Schalter.
- Timeouts/Fehlerklassifikation sauber integrieren (Transient/Permanent) und an bestehenden Retry‑Flow anbinden.
- Keine PII in Logs; nur IDs/Timing/Fehlercodes.

### Criteria‑Schema v2 (Analyse‑Payload)

Motivation:
- `criteria.v2` erweitert `criteria.v1` um Flexibilität pro Kriterium:
  - `criterion` bleibt der Schlüssel (Pflichtfeld).
  - `max_score` erlaubt pro Kriterium unterschiedliche Skalen (Default 10).
  - `score` wird relativ zu `max_score` bewertet (0..max_score).
  - `explanation_md` bleibt die objektive Begründung (Markdown).
- API‑Vertrag unterstützt bereits `criteria.v2` (siehe `api/openapi.yml`). Kein Contract‑Change nötig; nur Erzeugung/Verarbeitung.

Entwurf (Adapter/Worker/UI):
- Feedback‑Adapter (local + später cloud) liefert standardmäßig `criteria.v2`.
- Worker speichert `analysis_json` unverändert; UI rendert v1 und v2 gleichwertig (Backward Compatibility).
- Stub‑Adapter liefert ab jetzt `criteria.v2` (vereinheitlicht mit lokalen Adaptern).
- Vision‑Adapter nutzt für Nicht‑Text die MIME‑Allowlist (JPEG/PNG/PDF); für `kind='text'` entfällt die MIME‑Prüfung (Pass‑through). Falls der Queue‑Payload keine MIME enthält, wird `submission.mime_type` verwendet.

Beispieleintrag (v2):
```
{
  "schema": "criteria.v2",
  "score": 3,
  "criteria_results": [
    {"criterion": "Inhalt", "score": 7, "max_score": 10, "explanation_md": "…"},
    {"criterion": "Struktur", "score": 6, "max_score": 10, "explanation_md": "…"}
  ]
}
```

BDD‑Szenarien (ergänzt für v2):
- Given `AI_BACKEND=local` and `dspy` importierbar, When Feedback läuft, Then `analysis_json.schema == 'criteria.v2'` und jeder Eintrag hat `criterion`, optional `max_score` (Default 10), `score ∈ [0, max_score]`.
- Given `AI_BACKEND=local` and `dspy` nicht importierbar, When Feedback läuft (Ollama), Then analog `criteria.v2`.
- Given vorhandene Alt‑Daten mit `criteria.v1`, When UI rendert, Then Darstellung bleibt korrekt (Abwärtskompatibilität; keine Fehlermeldung).

Tests (TDD):
- Unit: `backend/tests/learning_adapters/test_local_feedback.py` anpassen/ergänzen: Erwartet `schema='criteria.v2'`, prüft `criterion`, `score`, `max_score` Default.
- Unit (DSPy‑Bevorzugung): `backend/tests/learning_adapters/test_local_feedback_dspy.py` bleibt gültig, erweitert um `schema='criteria.v2'`.
- Integration: Worker‑Pfad akzeptiert v1 und v2 (oneOf). Neuer Testfall prüft, dass lokale Adapter v2 schreiben und UI/SSR sauber rendert.

Migration:
- Keine Schema‑Änderungen erforderlich (JSON‑Payload bleibt in `analysis_json`).

Schema‑Kanonisierung (v2 als Standard):
- Worker normalisiert eingehende Analyse‑Payloads auf `criteria.v2`.
- Falls Adapter noch `criteria.v1` liefern (z. B. Stub), konvertiert der Worker v1→v2 vor Persistierung.
- Zielbild: Alle Adapter (inkl. Stub) liefern nativ `criteria.v2`, Konverter bleibt als Safety‑Net erhalten.

Adapter‑APIs (Ports bleiben gleich):
- `VisionAdapterProtocol.extract(submission) -> VisionResult` mit `text_md: str`, `meta: dict`.
- `FeedbackAdapterProtocol.analyze(criteria, text_body_md) -> FeedbackResult` mit `feedback_md: str`, `analysis_json: json` (Schema `criteria.v2`).
- Fehlerklassen: `VisionTransientError`, `VisionPermanentError`, `FeedbackTransientError`, `FeedbackPermanentError`.

Organisatorische Struktur:
- Protokolle und Result‑Typen werden nach `backend/learning/adapters/ports.py` extrahiert, um den Worker von Port‑Verträgen zu entkoppeln.

Konfiguration/Feature‑Flag:
- Primär werden die bestehenden Adapter‑Schalter verwendet:
  - `LEARNING_VISION_ADAPTER` (Default: `backend.learning.adapters.stub_vision`)
  - `LEARNING_FEEDBACK_ADAPTER` (Default: `backend.learning.adapters.stub_feedback`)
- Optionaler Alias: `AI_BACKEND=stub|local` mappt auf obige Pfade:
  - `stub` ⇒ `LEARNING_VISION_ADAPTER=backend.learning.adapters.stub_vision`, `LEARNING_FEEDBACK_ADAPTER=backend.learning.adapters.stub_feedback`
  - `local` ⇒ `LEARNING_VISION_ADAPTER=backend.learning.adapters.local_vision`, `LEARNING_FEEDBACK_ADAPTER=backend.learning.adapters.local_feedback`
- Modelle: `AI_VISION_MODEL`, `AI_FEEDBACK_MODEL`.
- Timeouts: `AI_TIMEOUT_VISION` (z. B. 30s), `AI_TIMEOUT_FEEDBACK` (z. B. 15s).
- `OLLAMA_BASE_URL` muss auf eine lokale/Service‑Netz‑Adresse zeigen (z. B. `http://ollama:11434`); keine externen Endpunkte.
 - Keine weiteren Feature‑Flags einführen (KISS): DSPy wird automatisch genutzt, wenn `import dspy` erfolgreich ist; andernfalls greift der Adapter auf Ollama zurück.

Zentrale Konfiguration (KISS):
- Eine schlanke Funktion `load_ai_config()` kapselt das Parsen/Validieren der relevanten Env‑Variablen und liefert ein `dataclass`‑Objekt.
- Schlüssel: `AI_BACKEND`, `LEARNING_VISION_ADAPTER`, `LEARNING_FEEDBACK_ADAPTER`, `AI_VISION_MODEL`, `AI_FEEDBACK_MODEL`, `AI_TIMEOUT_VISION`, `AI_TIMEOUT_FEEDBACK`, `OLLAMA_BASE_URL`.
- Defaults: `AI_BACKEND=stub`, Timeouts 30s/15s, lokale `OLLAMA_BASE_URL`.
- Validierung: `AI_BACKEND ∈ {stub, local}`, Timeouts >0 und ≤300, URL muss `localhost`/Service‑Netz sein. Bei Invalidität → Start‑Fehler (fail fast).

BDD‑Szenarien (KI‑Integration):
1) Given `AI_BACKEND=local` und gültiges JPEG; When Worker verarbeitet pending Submission; Then `text_body` enthält Vision‑Extrakt (Markdown), `feedback_md`/`analysis_json` gesetzt, Status `completed`.
2) Given `AI_BACKEND=local` und Vision‑Timeout; When Worker verarbeitet Submission; Then Retry bis Limit, final `failed` mit `error_code='vision_failed'` (PII‑freie Fehlermeldung).
3) Given `AI_BACKEND=local` und Feedback‑Transient‑Error; When erster Lauf scheitert, zweiter Lauf erfolgreich; Then final `completed`, Retry‑Zähler erhöht, strukturierte Logs vorhanden.
4) Given `AI_BACKEND=stub`; When Worker verarbeitet; Then es gibt keine Aufrufe an Ollama/DSPy, Verhalten entspricht den bestehenden Stub‑Tests (Determinismus).
5) Given `AI_BACKEND=local` und gültiges PDF; When Worker verarbeitet pending Submission; Then `text_body` enthält OCR‑Extrakt (Markdown), `feedback_md`/`analysis_json` gesetzt, Status `completed`.
6) Given `AI_BACKEND=local` und `dspy` ist importierbar; When Feedback läuft; Then wird der DSPy‑Pfad verwendet (kein Ollama‑Aufruf), Ergebnis `criteria.v2`.
7) Given `AI_BACKEND=local` und `dspy` ist nicht importierbar; When Feedback läuft; Then wird der Ollama‑Pfad verwendet, Ergebnis `criteria.v2`.

Retry/Backoff‑Spezifikation:
- Strategie: Exponentieller Backoff mit Jitter (±20%).
- Basis: 1 s; Faktor: 2; Max‑Retries: Vision 3, Feedback 2.
- Fehlercodes: Transient → `*_retrying` während der Retries; Permanent/Retry‑Limit → `*_failed`.
- Idempotenz: Lease‑Erneuerung verhindert Doppelverarbeitung; beim Lease‑Timeout wird der Job erneut sichtbar (ein Worker verarbeitet zur Zeit).

Privacy‑Logging (BDD):
- Given erfolgreiche Verarbeitung, When Logs gesammelt werden, Then enthalten die Zeilen nur `submission_id`, `job_id`, `error_code`, Zeiten – keine Textauszüge oder Byte‑Signaturen.
- Given Adapter‑Timeout/Exception, When Logs gesammelt werden, Then erscheinen nur Fehlercodes/Timing/IDs; `text_body`/Rohbytes fehlen ausdrücklich.
- Given Retries, When konsolidierte Logs betrachtet werden, Then sind pro Versuch genau eine Start/End‑Zeile vorhanden, ohne PII‑Leakage.

Testentwurf (vor Implementierung):
- Unit (Adapter‑Fassade, gemockte Libs):
  - Vision/local: mappt DSPy/Ollama‑Antwort → `text_md`; Timeout wirft `VisionTransientError`; ungültiger MIME → bewusster `VisionPermanentError`.
  - Feedback/local: erzeugt `feedback_md` und `analysis_json` mit `schema: criteria.v2`, Wertebereiche geprüft; Timeout → `FeedbackTransientError`.
- Integration (Worker + DI):
  - `AI_BACKEND` bestimmt Adapterwahl; bei `local` werden Ollama/DSPy‑Clients gemockt, Pfad setzt Felder gemäß Port‑Verträgen.
  - Logs enthalten keine PII (Snapshot‑Test von Log‑Zeilen auf IDs/Fehlercodes).
 - Privacy‑Logging: Sicherstellen, dass weder `text_body` noch Bild/PDF‑Inhalte in Logs auftauchen (Regex‑Negativ‑Assertion auf Beispieltexte/Byte‑Signaturen).

Implementierung (minimal, nur Test‑Grün):
- `backend/learning/adapters/local_vision.py`: DSPy‑Kontext wenn verfügbar, sonst direkter Ollama‑Client; akzeptiert JPEG/PNG/PDF; Timeout; Fehlerklassifikation; Rückgabe Markdown.
- `backend/learning/adapters/local_feedback.py`: DSPy‑Modul oder Ollama‑Prompt; konstruiert minimal gültiges `analysis_json` (Schema `criteria.v2`), `feedback_md` aus zwei Abschnitten.
- DI‑Schicht respektiert `AI_BACKEND`; Default `stub`, „local“ nur bei expliziter Env.

Status (2025‑11‑04):
- Implementiert: Lokale Adapter (Vision/Feedback) mit Minimal‑Logik, Kriterien v2 einheitlich.
  - Dateien: `backend/learning/adapters/local_vision.py`, `backend/learning/adapters/local_feedback.py`.
- Neu: Vision‑Streaming + Eingangsvalidierung (lokales Storage‑Root)
  - Verifiziert `storage_key` sicher (kein Path‑Escape), prüft `size_bytes` und `sha256` bei Nicht‑Text‑Abgaben, liest Bytes und exponiert `bytes_read` in `raw_metadata`.
  - Tests: `backend/tests/learning_adapters/test_local_vision_streaming.py` (happy path, size/hash/missing‑file Permanent‑Error, Text‑Bypass).
  - Fehlerklassifikation: `size_mismatch`, `hash_mismatch`, `missing_file`, `path_error` ⇒ Permanent; leere LLM‑Antwort ⇒ Transient.
- Neu: DSPy‑Programme als konkrete Einstiegspunkte; Adapter‑Präferenz differenziert
  - Dateien: `backend/learning/adapters/dspy/feedback_program.py`, `backend/learning/adapters/dspy/vision_program.py`.
  - Verhalten Feedback: `local_feedback` bevorzugt DSPy (`analyze_feedback()`), fällt bei fehlendem Import auf Ollama zurück; Ausgabe ist deterministisches `criteria.v2`.
  - Verhalten Vision: `local_vision` bevorzugt Ollama (DSPy‑Pfad derzeit nicht aktiv im Adapter), damit E2E stabil (Vision=Ollama, Feedback=DSPy).
- Stub vereinheitlicht auf v2: `backend/learning/adapters/stub_feedback.py` liefert `criteria.v2` (mit `max_score`).
- Zentrale Konfiguration: `backend/learning/config.py` mit `load_ai_config()` (Backends, Adapterpfade, Timeouts, lokale URL‑Validierung).
- Worker nutzt zentrale Konfiguration für DI: `process_learning_submission_jobs.main()` lädt Adapterpfade aus `load_ai_config()`.
- Worker holt nun zusätzliche Submission‑Felder (`mime_type`, `size_bytes`, `storage_key`, `sha256`) für Vision; `local_vision` nutzt Fallback von `submission.mime_type`.
- Vision bei Text: Kein MIME‑Zwang für `kind='text'`, dadurch E2E‑Textpfad stabil.
- Learning‑API Speicher‑Verifikation: nicht‑strikt im Dev‑Modus (keine 400, Rückgabe „skipped“), um lokale Tests ohne echte Dateien zu ermöglichen.
- Compose/Ops: Ollama‑Service Healthcheck robuster (Start‑Periode/Retry), Standard ohne GPU lauffähig; ROCm‑Profil optional (siehe Ops‑Notizen unten).
- Tests grün:
  - Adapter + DI: `backend/tests/learning_adapters/test_local_vision.py`, `backend/tests/learning_adapters/test_local_feedback.py`, `backend/tests/learning_adapters/test_local_feedback_dspy.py`, `backend/tests/test_learning_worker_di_switch.py`.
  - Streaming/Validierung: `backend/tests/learning_adapters/test_local_vision_streaming.py`.
  - E2E (lokale Adapter, gemockt): `backend/tests/test_learning_worker_e2e_local.py` (Text mit DSPy, Image mit Ollama) — beide Completed und `criteria.v2`.
  - Privacy‑Logging: `backend/tests/test_learning_worker_privacy_logs.py` stellt sicher, dass Logs keine Textauszüge enthalten.

Nächste Schritte:
- E2E‑Retry‑Pfad erweitern (Transient‑Errors, Lease‑Expiry, kein Duplicate‑Work).
- Privacy‑Logging‑Negative further (Fehlerpfade), Snapshot‑Filter für IDs/Fehlercodes/Timings.
- Optional UI: `max_score` aus v2 anzeigen (ohne Breaking Changes).

## Lückenanalyse (Stand heute) – Essenzielle fehlende Schritte bis MVP

- DSPy Programme produktiv machen
  - Feedback: Prompt + Normalisierung umgesetzt; nächste Iteration ersetzt LM‑Shim durch echte DSPy‑LM‑Verkabelung (bleibt monkeypatchbar) und erweitert Fehlermapping.
  - Vision: konkreter OCR/Extraktions‑Prompt (Bild/PDF/Text) noch offen; leere/garbled Antwort → Transient, Tests ergänzen.

- Vision: echte Dateiverarbeitung
  - `backend/learning/adapters/local_vision.py`: Datei aus Storage streamen (signed URL/Service‑Key), MIME/Size hart prüfen, SHA‑256 verifizieren; PDFs unterstützen; leere/whitespace‑Antworten als Transient.

- Feedback: robustes v2‑Ergebnis
  - `backend/learning/adapters/local_feedback.py`: DSPy‑Pfad mit realem Programmlauf; Ollama‑Fallback behalten; Normalisierung unsauberer Model‑Outputs ins `criteria.v2`‑Schema (criterion, max_score, score, explanation_md; score‑Ranges durchsetzen).

- Konfiguration/Dependencies
  - Worker‑Image: `dspy` und Python‑`ollama` installieren; Modelle/Timeouts finalisieren; zentrale Defaults in `backend/learning/config.py` abstimmen.

- Ops/Compose
  - Compose‑Service für Ollama mit ROCm (`ollama/ollama:rocm`), Devices/Groups mappen; `OLLAMA_BASE_URL=http://ollama:11434`.
  - Modelle laden: `docker compose exec ollama ollama pull ${AI_VISION_MODEL}` und `${AI_FEEDBACK_MODEL}`.
  - Worker mit `AI_BACKEND=local` betreiben; Health/Logs prüfen.

- Sicherheit/Privacy
  - Keine PII in Logs (auch Fehlerpfade); Error‑Redaction bereits vorhanden, Negativ‑Checks erweitern.
  - RLS bleibt wirksam: Storage‑Zugriff nur über serverseitige Funktionen oder kurzlebige signed URLs.
  - Größen‑/Typgrenzen, Antivirus/Content‑Scan‑Hook (falls vorgesehen), Backoff/Retry‑Limits finalisieren.

- Tests (TDD/E2E)
  - Unit: DSPy‑Programme mit Fake‑LM; Parser‑Robustheit (fehlende Felder, falsche Typen, Score‑Range).
  - Worker‑E2E: pending→completed für Text/Bild/PDF mit DSPy vorhanden und ohne DSPy (Fallback); Retry‑Szenarien (Transient → Requeue → Completed/Failed); Lease‑Expiry ohne Doppelarbeit.
  - Privacy‑Logging: Negative Assertions auf Success/Transient/Permanent‑Pfaden.

## Konkreter Umsetzungsplan (TDD‑first, MVP)

1) Vision‑Streaming + Eingangsvalidierung — erledigt (heute)
   - BDD: Given gültiger JPEG/PNG/PDF (mit korrekter `mime_type`/`size_bytes`/`sha256`), When Vision läuft, Then `text_md` nicht leer; invalides MIME/Größe → Permanent‑Error; leere Antwort → Transient.
   - Tests: `backend/tests/learning_adapters/test_local_vision_streaming.py` (neu) mit gemocktem Storage/Bytes.
   - Code: `backend/learning/adapters/local_vision.py` Bytes‑Stream + SHA‑256 + Limits; `raw_metadata.bytes_read` für Observability.

2) Feedback‑DSPy Programm (criteria.v2) — umgesetzt (heute, Prompt + Parser/Normalisierung)
   - BDD: Given Text + Kriterien, When DSPy läuft, Then v2‑Report mit `criterion`, `max_score`, `score∈[0,max]`, `explanation_md` (enthält Kriteriums‑Namen). Leere Kriterienliste → Gesamtscore=0, leeres Array.
   - Tests:
     - `backend/tests/learning_adapters/test_feedback_program_dspy.py` — Präferenz DSPy vor Ollama, Schema v2, leere Kriterien.
     - `backend/tests/learning_adapters/test_feedback_program_dspy_parser.py` — Parser akzeptiert Feldvarianten (`criteria|criteria_results`, `name|criterion`, `max|max_score`, `explanation|explanation_md`), klammert Scores in gültige Bereiche, füllt fehlende Kriterien und fällt bei kaputtem JSON deterministisch zurück.
     - `backend/tests/learning_adapters/test_feedback_program_dspy_prompt.py` — echter Prompt (Privacy‑Hinweis, Output‑Schema `criteria.v2`, Kriterienliste), LM‑Shim `_lm_call` wird aufgerufen; fehlerhafte Antworten werden normalisiert.
   - Code: `backend/learning/adapters/dspy/feedback_program.py` — `_build_prompt` (privacy‑aware, schema‑guided), `_lm_call` (monkeypatchbar), `_run_model` nutzt Prompt+Timeout; `_parse_to_v2` mit robuster Normalisierung; deterministische Fallbacks.

3) Vision‑DSPy Programm — umgesetzt (heute, minimal)
   - BDD: Given Submission (image/pdf) + Job‑Payload, When DSPy importierbar, Then liefert Programm Markdown‑Extrakt/Übersicht; Meta markiert `backend='dspy'`, `adapter='local_vision'`, `program='dspy_vision'`; MIME fällt auf Submission zurück, wenn im Job nicht gesetzt.
   - Tests: `backend/tests/learning_adapters/test_vision_program_dspy.py` (neu) prüft ImportError ohne DSPy, Markdown‑Form, Fallback von MIME und Meta‑Felder (inkl. `program`).
   - Code: `backend/learning/adapters/dspy/vision_program.py` — deterministische Minimal‑Implementierung; Adapter klassifiziert leere Modellantworten als transient.

4) E2E‑Retries und Lease‑Expiry
   - BDD: Given Transient‑Fehler in Vision/Feedback, When Worker läuft, Then Job wird mit Exponential‑Backoff requeued bis Max‑Retries; danach `*_failed`.
   - Tests: `backend/tests/test_learning_worker_retries.py` (neu) mit gemockten Adaptern.

4) Privacy‑Negative‑Tests
   - BDD: Given Success/Transient/Permanent, When Logs gescannt werden, Then keine Auszüge aus `text_md`/Rohbytes vorhanden.
   - Tests: `backend/tests/test_learning_worker_privacy_logs.py` (erweitern).

5) Ops/Compose Härtung
   - Compose: `ollama/ollama:rocm` + Devices/Groups; Env‑Vorgaben (`AI_*`, `OLLAMA_BASE_URL`) konsolidieren.
   - Docs: `docs/runbooks/learning_worker.md` Update (Model Pull, Troubleshooting, ROCm‑Hinweise).

Definition of Done (MVP KI)
- End‑to‑End pending→completed für Text/Bild/PDF mit `AI_BACKEND=local`, deterministisch mit Mocks getestet.
- `analysis_json.schema == 'criteria.v2'`, Score‑Ranges validiert; UI zeigt v2 konsistent an.
- Privacy‑Negative‑Tests grün; Logs PII‑frei.
- Ops: Compose + Runbook ermöglichen lokalen Betrieb ohne weitere manuelle Schritte als Model Pulls.

Ops‑Notizen (parallel, no‑regrets):
- Compose: `AI_BACKEND`, Modell‑Env‑Vars, `OLLAMA_BASE_URL` ergänzen; Ressourcenlimits/Timeouts dokumentieren.
- Health: bestehender Worker‑Health bleibt maßgeblich; „Model readiness“ nur intern loggen, kein externes Fail‑Kriterium.
 - Modelle vorbereiten (dev/staging): Beispiel
   - `docker exec gustav-ollama ollama pull ${AI_VISION_MODEL}`
 - `docker exec gustav-ollama ollama pull ${AI_FEEDBACK_MODEL}`
  - Hinweis: Nur in lokalen Netzen verwenden; keine Cloud‑Egress.
  - Sicherheit: Ollama nur an `localhost`/Service‑Netz binden; Telemetrie/Auto‑Updates deaktivieren.

Konkrete Schritte (Compose & Ops — Stand jetzt):
 - Compose enthält Service `ollama` (Image `ollama/ollama:latest` für CPU‑only; optional GPU: `ollama/ollama:rocm` mit Geräte‑/Gruppen‑Mapping), interner Port 11434, Volume `ollama_models` für Persistenz.
- `learning-worker` exportiert bereits:
  - `AI_BACKEND` (`stub`|`local`, Default `stub`)
  - `OLLAMA_BASE_URL` (Default `http://ollama:11434`)
  - `AI_VISION_MODEL` (Default `llama3.2-vision`), `AI_FEEDBACK_MODEL` (Default `llama3.1`)
  - `AI_TIMEOUT_VISION`/`AI_TIMEOUT_FEEDBACK` (Default `30`)
- Modelle ziehen (einmalig pro Umgebung):
  - `docker compose exec ollama ollama pull ${AI_VISION_MODEL}`
  - `docker compose exec ollama ollama pull ${AI_FEEDBACK_MODEL}`
  - Sicherheit: Service nur intern erreichbar halten (keine Public‑Ports), Telemetrie deaktivieren.
- Lokale KI aktivieren:
  - `.env` → `AI_BACKEND=local`
  - `docker compose up -d --build`
- Rückbau auf Stub (deterministische Tests/CI):
  - `.env` → `AI_BACKEND=stub`
  - `docker compose up -d`

Risiken & Gegenmaßnahmen (KI‑spezifisch):
- „Leere“ Modellantworten → behandeln wie Transient‑Error mit Retry (bis Limit), Logs ohne PII.
- Performance‑Outlier → harte Timeouts, Backoff; Hinweis im Runbook.
- Modelldrift → Default weiter `stub` in CI; „local“ nur in dev/staging manuell aktivieren.

## Observability (Iteration 1 Follow-up)

Ziele (KISS & Security first):
- Lehrkräfte und Operatoren erkennen Staus oder Fehlkonfigurationen ohne Zugriff auf personenbezogene Daten.
- Alerts schlagen nur an, wenn Handlungsbedarf besteht (keine Alert-Fatigue).
- Alle Dashboards und Logs anonymisieren Submission-Daten (nur IDs, keine Schülernamen).

Metriken & Grenzwerte:
- `analysis_jobs_inflight`: Warnung ab >10 Jobs für länger als 5 Minuten, Critical ab >25 Jobs (Hinweis auf Worker-Stau).
- `ai_worker_failed_total`: Delta >0 innerhalb 15 Minuten → Warnung; Delta >3 → Critical (erfordert Untersuchung).
- `ai_worker_retry_total`: Anteil Retries >30 % der Jobs innerhalb 15 Minuten → Warnung (Vision-/Feedback-Dienst prüfen).
- `learning_worker_health_probe_duration_seconds` (Histogramm): 95. Perzentil >1 s → Warnung, >3 s → Critical.

Alerting-Skizze (Prometheus + Alertmanager):
- Regel `LearningWorkerBacklogWarning`: `analysis_jobs_inflight > 10` für 5 Minuten → Slack-Kanal `#gustav-ops`.
- Regel `LearningWorkerFailuresCritical`: `increase(ai_worker_failed_total[15m]) > 3` → Pager für Bereitschaft.
- Regel `LearningWorkerRetriesWarning`: `increase(ai_worker_retry_total[15m]) > increase(ai_worker_processed_total[15m]) * 0.3` → Hinweis auf adapterseitige Probleme.
- Regel `LearningWorkerProbeSlow`: `histogram_quantile(0.95, rate(learning_worker_health_probe_duration_seconds_bucket[5m])) > 1` → Slack-Info; Critical-Schwelle bei >3 s.

Dashboard (Grafana-Board „Learning Worker“):
- Panel „Queue Size“ (graph): `analysis_jobs_inflight` + Annotationen bei Deployments.
- Panel „Job Outcomes“ (stacked bar): `increase(ai_worker_processed_total[1h])`, `ai_worker_retry_total`, `ai_worker_failed_total`.
- Panel „Health Probe Dauer“ (heatmap oder single stat) für `learning_worker_health_probe_duration_seconds`.
- Panel „Adapter Logs“ (Loki-Query: `{service="learning-worker"} |= "vision_retrying" OR |= "feedback_retrying"`), rote Hervorhebung bei Fehlercodes.
- Drilldown-Link zur Runbook-Sektion „Fehlerbehebung“.

Log-Standards:
- Strukturierte Logs enthalten `submission_id`, `job_id`, `error_code`, niemals `text_body` oder Vision-Ausgaben.
- Für DSGVO-Konformität: Logs werden nach 30 Tagen rotiert, Zugriff nur für Rolle `gustav_operator`.

Instrumentierung:
- Worker meldet Metriken via Prometheus-Python-Client, Exporter läuft im gleichen Container, Port 9464 (nur lokal/binnen Netz erreichbar).

---

## DSPy-Integration (konkret) — Architektur, TDD, Ops

Motivation:
- Wir wollen die Prompt‑Logik strukturiert und testbar kapseln. DSPy orchestriert die Programme, Ollama liefert die Inferenz. Keine zusätzlichen Feature‑Flags: DSPy wird automatisch genutzt, wenn `import dspy` klappt, andernfalls nutzen die Adapter den direkten Ollama‑Client.

Ziele (Iteration 1b — vorgezogen):
- Feedback: DSPy‑Programm erzeugt `criteria.v2` mit Feldern `criterion`, `max_score`, `score`, `explanation_md` und einem Gesamtscore `0..5`.
- Vision: DSPy‑Programm extrahiert Markdown‑Text aus JPEG/PNG/PDF (KISS: erste(n) Seite(n) zusammenfassen, keine komplexe Layout‑Rekonstruktion in I1).
- Adapter bleiben die einzige Schnittstelle für den Worker (Clean Architecture). Ports unverändert (`VisionAdapterProtocol`, `FeedbackAdapterProtocol`).
- Privacy: Keine PII im Log, deterministische Tests via Mocks; Timeouts strikt.

High‑Level‑Design:
- `backend/learning/adapters/dspy/feedback_program.py`
  - `build(lm) -> FeedbackProgram` konfiguriert ein kleines DSPy‑Programm (z. B. Chain‑of‑Thought + strukturierte Ausgabe) für Kriterienauswertung.
  - Erwartet `lm` als DSPy‑LM, das gegen Ollama spricht.
- `backend/learning/adapters/dspy/vision_program.py`
  - `build(lm) -> VisionProgram` extrahiert (zusammenfasst) Markdown‑Text aus Bild/PDF.
- LM‑Konfiguration (gemeinsam):
  - `dspy.settings.configure(lm=OllamaLM(base_url=OLLAMA_BASE_URL, model=<AI_*_MODEL>), trace=False)`
  - Falls DSPy keine native Ollama‑LM bereitstellt, implementieren wir einen dünnen LM‑Adapter, der intern `ollama.Client.generate` nutzt (keine neuen Env‑Variablen nötig).
- Adapter‑Verdrahtung:
  - `local_feedback.py`: bei erfolgreichem `import dspy` → DSPy‑Programm verwenden; andernfalls bisheriger Ollama‑Pfad.
  - `local_vision.py`: analog für Vision.
- Keine Änderung an Worker‑DI: `AI_BACKEND=local` schaltet lokale Adapter; diese wählen automatisch DSPy, wenn verfügbar.

TDD‑Szenarien (ergänzend):
- Feedback (DSPy‑Pfad):
  - Given `dspy` importierbar, When `LocalFeedbackAdapter.analyze()` läuft, Then kein direkter `ollama.Client.generate`‑Aufruf erfolgt und das Ergebnis erfüllt `criteria.v2`.
  - Timeout/Fehler im DSPy‑Programm → `FeedbackTransientError` (Retry auf Worker‑Ebene).
- Vision (DSPy‑Pfad):
  - Given `dspy` importierbar und MIME `image/jpeg`, When `LocalVisionAdapter.extract()`, Then Markdown‑Text zurück, Metadaten enthalten `backend='dspy+ollama'`.
  - Leere Modellantwort → transienter Fehler (Retry), ungültiger MIME → permanenter Fehler.
- Worker E2E (gemockte Clients):
  - Given `AI_BACKEND=local` und `dspy` importierbar, When pending Submission verarbeitet wird, Then Status → `completed`, Felder `text_body`, `feedback_md`, `analysis_json.schema='criteria.v2'` gesetzt und Logs PII‑frei.

Implementierungsschritte:
1) DSPy‑Programme anlegen: `backend/learning/adapters/dspy/{feedback_program.py,vision_program.py}` mit minimalen Prompts, klaren Zeitlimits.
2) LM‑Adapter (nur falls nötig): dünne Klasse `OllamaLM` für DSPy, die `ollama.Client` nutzt; Respektiert `OLLAMA_BASE_URL`, `AI_*_MODEL`, Timeouts.
3) Adapter verdrahten: `local_feedback.py` und `local_vision.py` nutzen die Programme, wenn `import dspy` gelingt (keine neuen Env‑Flags).
4) Tests ergänzen/erweitern:
   - Neue Unit‑Tests für Vision‑DSPy‑Pfad (analog zu `test_local_feedback_dspy.py`).
   - E2E‑Tests Worker mit `AI_BACKEND=local` + DSPy‑Mocks (pending → completed, Retry‑Pfad bei transienten Fehlern).
5) Doku & Ops: README/Runbook vermerken, dass DSPy automatisch genutzt wird; keine Cloud‑Egress; Modelle per `docker compose exec ollama ollama pull` bereitstellen.

Abgrenzungen/Kompatibilität:
- Stubs bleiben Default (`AI_BACKEND=stub`) und liefern `criteria.v2`; damit sind UI/Tests durchgehend v2‑fähig.
- OpenAPI bereits kompatibel (oneOf v1/v2). UI rendert beide Varianten.

Risiken & Gegenmaßnahmen:
- GPU‑VRAM‑Engpässe: Modellgrößen/Quantisierung dokumentieren; Timeouts und Backoff im Worker; ROCm‑Hinweise im Runbook.
- Modelldrift: Tests mocken DSPy/Ollama; produktive Modelle werden in Ops‑Notes festgehalten.
- PII‑Leaks: Negative Log‑Assertions in Tests; strukturierte Logs nur mit IDs, Fehlercodes, Timings.

### Präzisiertes Design

- Verzeichnisstruktur:
  - `backend/learning/adapters/dspy/`
    - `__init__.py`
    - `lm.py` (optional) — dünner Adapter `OllamaLM` nur falls DSPy keine native Ollama‑LM bietet
    - `feedback_program.py` — definiert `FeedbackProgram`
    - `vision_program.py` — definiert `VisionProgram`

- Ports (unverändert, aus `backend/learning/adapters/ports.py`):
  - `VisionAdapterProtocol.extract(submission: dict, job_payload: dict) -> VisionResult`
  - `FeedbackAdapterProtocol.analyze(text_md: str, criteria: Sequence[str]) -> FeedbackResult`

- DSPy‑LM‑Konfiguration (Pseudocode):
  - `from dspy import settings`
  - `settings.configure(lm=OllamaLM(base_url=env("OLLAMA_BASE_URL"), model=model_name), trace=False)`
  - Vision nutzt `AI_VISION_MODEL`, Feedback `AI_FEEDBACK_MODEL`; Timeout via LM‑Option oder Aufrufer (30s Default)

- Programme (Skizze):
  - FeedbackProgram
    - Input: `text_md: str`, `criteria: list[str]`
    - Output: `feedback_md: str`, `criteria_results: list[{criterion, max_score, score, explanation_md}]`, `score: int (0..5)`, `schema: 'criteria.v2'`
    - Prompt‑Leitplanken: kurz, deutsch, keine personenbezogenen Daten, max. 250 Worte
  - VisionProgram
    - Input: `mime_type: str`, `content_ref: dict` (in I1: nur Metadaten, kein echter Bytes‑Zugriff)
    - Output: `text_md: str` (knappe Markdown‑Zusammenfassung); leere/whitespace → transienter Fehler

- Fehler‑Taxonomie (Mapping):
  - DSPy Timeout, Netzwerkfehler (Ollama) → `VisionTransientError`/`FeedbackTransientError`
  - Unsupported MIME → `VisionPermanentError`
  - Strukturfehler in Ausgabe (fehlende Pflichtfelder) → Transient (einmal retry), danach Worker markiert `failed`

### TDD‑Checkliste (präzise Dateien & Fälle)

- Unit‑Tests (DSPy‑Pfad):
  - `backend/tests/learning_adapters/test_local_feedback_dspy.py`
    - „nutzt DSPy, nicht Ollama“ (monkeypatch: fake `dspy`, sentinel Aufrufzählung für `ollama.Client`)
    - Ergebnisvalidierung: `schema='criteria.v2'`, Wertebereiche (0..5, 0..10), pro Kriterium Felder vorhanden
    - Timeout/Exception im DSPy‑Programm → `FeedbackTransientError`
  - `backend/tests/learning_adapters/test_local_vision_dspy.py` (neu)
    - JPEG/PNG/PDF Happy Path → Markdown nicht leer; `raw_metadata.backend='dspy+ollama'`
    - Leere Antwort → `VisionTransientError`
    - Invalid MIME → `VisionPermanentError`

- Worker‑Integration (gemockte Clients):
  - `backend/tests/test_learning_worker_e2e_local.py`
    - `AI_BACKEND=local`, `dspy` importierbar
    - Text‑Submission: pending → completed, `analysis_json.schema='criteria.v2'`
    - Image‑Submission: pending → completed, `text_body` aus Vision, Feedback gesetzt
    - Transient Fehler → Retry, dann success; Log‑Negativ‑Assertion (keine PII)

- Performance/Resilienz (Unit‑nahe):
  - Zeitbudget‑Asserts via künstlichen Sleeps vermeiden; stattdessen Timeout‑Exceptions simulieren

### Definition of Done (DSPy‑Schritt)

- Alle oben genannten Unit‑ und E2E‑Tests grün (lokal mit gemockten Clients/DB).
- `local_feedback.py`/`local_vision.py` wählen DSPy automatisch, wenn importierbar.
- Stubs bleiben Default (`AI_BACKEND=stub`) und brechen keine bestehenden Tests.
- Doku: README + Runbook Abschnitt „Lokale KI (Ollama/DSPy)“ enthält Hinweis „DSPy auto‑detect“.
- Security/Privacy: Negative Log‑Assertions vorhanden, keine PII in Logs.

### Ops/ROCm (präzisiert)

- Compose: `ollama/ollama:rocm`, Geräte `/dev/kfd`, `/dev/dri`, Gruppen `video`, `render`.
- Modelle: `docker compose exec ollama ollama pull ${AI_VISION_MODEL}` und `${AI_FEEDBACK_MODEL}`.
- Tuning: optional `HIP_VISIBLE_DEVICES`, `HSA_OVERRIDE_GFX_VERSION` (leer lassen, wenn nicht nötig).
- Monitoring: Worker‑Health bleibt Quelle der Wahrheit; kein externes „Model Ready“ Gate.

### Nachgelagerte Schritte

- Stubs → `criteria.v2` anheben (wenn UI/Tests bereit), um einheitliche Darstellung sicherzustellen.
- Worker‑Retry‑E2E weiter ausbauen (Lease‑Expiry, Duplicate‑Work‑Schutz).
- UI klein: Anzeige `max_score` aus v2 optional ergänzen (ohne Breaking Changes).
- Health-Endpunkt ruft `learning_worker_health_probe()` und liefert zusätzlich `metrics_url` (localhost) zur leichteren Einbindung ins Monitoring.

Offene Punkte (Observability):
- Alertmanager-Receivers mit Felix abstimmen.
- Dashboard-JSON im Repo ablegen (`docs/observability/learning-worker.json`).
- End-to-End-Test für Prometheus-Endpoint vorbereiten (Smoke-Test, nicht-blockierend).

Nächste Schritte (Operations & UX):
- Compose-Service finalisieren (`learning-worker` inkl. Env-Variablen, Ressourcenlimits, Restart-Policy, Prometheus-Port).
- Healthchecks dokumentieren (HTTP `/internal/health/learning-worker` + DB-Probe) und automatisierten Smoke-Test ergänzen.
- Manuelle End-to-End-Prüfung planen: Submission → Pending → Completed/Failed → UI-Anzeige der Retry-/Fehlerzustände.

---

## Detailplan: Worker-Retry & Failure Handling

Ziel: Retry-Mechanismen deterministisch, nachvollziehbar und RLS-konform ausgestalten, damit Lernende und Lehrkräfte stabile Statusmeldungen bekommen.

- **Konfigurierbare Parameter**
  - `WORKER_MAX_RETRIES` (Default 3) begrenzt zusätzliche Versuche nach dem initialen Run. Effektive maximale Versuche = `WORKER_MAX_RETRIES + 1`.
  - `WORKER_BACKOFF_SECONDS` (Default 10) liefert die Basis für Exponential Backoff: `delay = WORKER_BACKOFF_SECONDS * (2 ** retry_count)`.
  - `WORKER_LEASE_SECONDS` (Default 30) legt die Lease-Dauer fest; Timeout führt zu automatischem Retry.

- **Job-Lifecycle**
  1. `_lease_next_job` wählt ältesten `queued`-Job (`visible_at <= now()`) via `FOR UPDATE SKIP LOCKED`, setzt `status='leased'`, `lease_key`, `leased_until = now() + WORKER_LEASE_SECONDS`.
  2. `_process_job` lädt Submission im selben TX-Kontext; falls Submission nicht mehr `pending`, löscht `_ack_success` den Job (idempotent).
  3. Vision-Phase nur bei `kind in ('image','file')`:
     - Erfolg: `vision_attempts += 1`, `vision_last_attempt_at = now()`, `vision_last_error = NULL`.
     - Transienter Fehler (`VisionTransientError`): `vision_attempts += 1`, `vision_last_attempt_at = now()`, `vision_last_error` kurze, PII-freie Meldung, `error_code='vision_retrying'`.
     - Permanenter Fehler (`VisionPermanentError`): direkt `_mark_failed('vision_failed', last_error)`.
  4. Feedback-Phase läuft immer:
     - Erfolg: `feedback_last_attempt_at = now()`, `feedback_last_error = NULL`.
     - Transienter Fehler (`FeedbackTransientError`): Retry analog Vision (ohne `error_code`-Wechsel, da Feedback-Fehler erst beim finalen Fail sichtbar wird).
     - Permanenter Fehler: `_mark_failed('feedback_failed', last_error)`.
  5. Erfolgspfad: `_update_submission_completed` setzt `analysis_status='completed'`, `text_body`, `analysis_json`, `feedback_md`, löscht `error_code`.
  6. Retrypfad: `_nack_retry` setzt `status='queued'`, `retry_count += 1`, `visible_at = now() + delay`, `lease_key=NULL`, `leased_until=NULL`.
  7. Finales Fail (Retry-Limit erreicht oder permanenter Fehler): `_update_submission_failed` setzt `analysis_status='failed'`, `error_code`, `vision_last_error`/`feedback_last_error`, Job `status='failed'`, `leased_until=NULL`.

- **Observability & Logging**
  - Metriken: `analysis_jobs_inflight` (gauge), `ai_worker_processed_total{status}`, `ai_worker_retry_total{phase}`, `ai_worker_failed_total{error_code}`.
  - Logs (Structured): Retry → Level WARN (`submission_id`, `retry_count`, `next_visible_at`), finaler Fail → Level ERROR (ohne PII).
  - Audit-Log-Einträge dokumentieren Statuswechsel (`pending→completed`, `pending→failed`) inkl. `job_id`, `lease_key`.

- **Tests (pytest)**
  - `test_worker_retries_vision_transient_error`: Erwartet Requeue mit exponentiellem Backoff, `retry_count` steigt, Submission bleibt `pending`.
  - `test_worker_marks_failed_after_max_retries`: Nach Überschreiten des Limits → Submission `analysis_status='failed'`, `error_code='vision_failed'`, Job `status='failed'`.
  - `test_worker_handles_feedback_transient_then_success`: Erster Durchlauf wirft `FeedbackTransientError`, zweiter Lauf erfolgreich → final `completed`.
  - `test_worker_ignores_non_pending_submission`: Worker erkennt `analysis_status!='pending'` und entfernt Job ohne Adapter-Aufruf.

## Detailplan: Security-Definer-Funktionen & Grants

Ziel: Worker agiert mit minimalen Rechten, hält RLS ein und aktualisiert nur definierte Felder.

- **Rollenmodell**
  - Neue DB-Rolle `gustav_worker`, Mitglied von `gustav_runtime`, aber ohne direkten DML-Zugriff auf `learning_submissions`.
  - Verbindungen setzen `set_config('app.current_sub', 'gustav_worker', true)` zu Beginn jeder Session.

- **Funktionen (alle `SECURITY DEFINER`, Eigentümer `gustav_owner`)**
  1. `learning_worker_update_completed(submission_id uuid, p_text_body text, p_feedback_md text, p_analysis_json jsonb)`  
     - Guard: `where id = submission_id and analysis_status = 'pending'`.  
     - Aktionen: `analysis_status='completed'`, `text_body=p_text_body`, `feedback_md=p_feedback_md`, `analysis_json=p_analysis_json`, `error_code=NULL`, `vision_attempts += 1`, Retry-Metadaten zurücksetzen.
  2. `learning_worker_update_failed(submission_id uuid, p_error_code text, p_last_error text)`  
     - Guard: `p_error_code in ('vision_failed','feedback_failed')`.  
     - Aktionen: `analysis_status='failed'`, `error_code=p_error_code`, zuständiges `_last_error`-Feld aktualisieren, Versuchsmetadaten für die jeweilige Phase hochzählen.
  3. `learning_worker_mark_retry(submission_id uuid, p_phase text, p_message text, p_attempted_at timestamptz)`  
     - Unterstützt `p_phase in ('vision','feedback')`, aktualisiert die zugehörigen Attempt-/Fehlerfelder und setzt `error_code` auf `*_retrying`.
  4. `learning_worker_ack_job(job_id uuid, p_lease_key uuid)`  
     - Löscht Job, wenn `lease_key` noch passt. Verhindert unautorisierte Acks.
  5. `learning_worker_nack_job(job_id uuid, p_visible_at timestamptz, p_retry_count integer)`  
     - Setzt `status='queued'`, `visible_at=p_visible_at`, `retry_count=p_retry_count`, `lease_key=NULL`.

- **Schema-Erweiterung**
  - Felder ergänzen: `feedback_last_attempt_at timestamptz`, `feedback_last_error text`.
  - Indizes prüfen (`learning_submission_jobs(status, visible_at)` reicht).
  - Audit-Trigger (`moddatetime`) erweitern, damit Funktionsaufrufe `updated_at` setzen.

- **Grants & Policies**
  - `grant execute on function learning_worker_* to gustav_worker;`
  - `grant select, insert, update on learning_submission_jobs to gustav_worker;`
  - RLS auf `learning_submission_jobs`: Policy `using (true)` für `gustav_worker`, `with check (true)` (Jobs sind nicht personenbezogen).
  - Keine direkten `UPDATE`/`DELETE`-Grants auf `learning_submissions`; ausschließlich Funktionspfad zulässig.

- **Tests & Governance**
  - RLS-Test: Direkter `UPDATE learning_submissions` als `gustav_worker` failt (`permission denied`), Funktionsaufruf succeeds.
  - Funktionstest: Aufruf von `learning_worker_update_completed` aktualisiert nur erwartete Felder (kein `student_sub` etc.).
  - Dokumentation: Ergänzung in `docs/operations/runbook_learning_worker.md` inkl. Rotationshinweis für `gustav_worker`-Passwort.

---

## Detailplan: DSN-Verifikation & Testkonfiguration

Ziel: Sicherstellen, dass alle Codepfade korrekt zwischen Runtime-, Test- und Service-Rollen unterscheiden und RLS weiterhin greift.

- **Konfigurations-Variablen**
  - `DATABASE_URL` (Runtime, Service-Role für Web).
  - `LEARNING_DATABASE_URL` (optional, überschreibt `DATABASE_URL` für Learning-Komponenten im Worker).
  - `RLS_TEST_DSN` (Testpfad, nutzt Test-Rolle mit RLS aktiv für pytest).

- **Initialisierungslogik**
  - Repository-Layer liest DSN lazy via `get_learning_repo(dsn=None)`; Worker übergibt explizit `LEARNING_DATABASE_URL`.
  - Tests patchen `RLS_TEST_DSN`, um echte RLS-Rollen zu erzwingen (keine Fake-RLS).
  - Fallback: wenn `LEARNING_DATABASE_URL` fehlt, greift `DATABASE_URL` (Warn-Log, damit Betreiber informiert sind).

- **Verifikation**
  - pytest-Fixture `learning_repo` prüft beim Setup, ob `current_user` innerhalb einer Session `gustav_student` oder `gustav_teacher` analog RLS agieren muss.
  - Integrationstest `test_repo_raises_without_current_sub`: Erwartet `PermissionError`, wenn `app.current_sub` nicht gesetzt ist (defensiv).
  - CLI-Check (z. B. `scripts/check_dsn.py`) validiert, dass `LEARNING_DATABASE_URL` auf Rolle `gustav_worker` zeigt, bevor Worker startet.
  - In CI: Matrix-Lauf mit `LEARNING_DATABASE_URL` gesetzt und ungesetzt, um beide Pfade abzudecken.

- **Monitoring**
  - Beim Start loggt Worker die verwendete DSN-Quelle (`LEARNING_DATABASE_URL` vs. `DATABASE_URL`) ohne Credentials.
  - Healthcheck-Endpunkt (`/internal/health/learning-worker`) ruft `select current_user, current_setting('app.current_sub', true)` ab; Deployment überprüft, ob `gustav_worker` aktiv ist.

---

## Operations & Deployment (Compose, Healthchecks, Runbook-Verknüpfung)

Compose-Service (Entwurf):
```yaml
  learning-worker:
    build:
      context: .
      dockerfile: docker/learning-worker.Dockerfile
    restart: unless-stopped
    environment:
      - LEARNING_DATABASE_URL=${LEARNING_DATABASE_URL}
      - WORKER_MAX_RETRIES=3
      - WORKER_BACKOFF_SECONDS=10
      - AI_VISION_ADAPTER=${AI_VISION_ADAPTER:-stub}
      - AI_FEEDBACK_ADAPTER=${AI_FEEDBACK_ADAPTER:-stub}
    depends_on:
      - db
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://web:8000/internal/health/learning-worker | jq -e '.status == \"healthy\"'"]
      interval: 30s
      timeout: 5s
      retries: 3
    ports:
      - "9464:9464" # Prometheus /metrics (nur lokal freigeben)
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: "1g"
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
```

Healthchecks:
- HTTP: `/internal/health/learning-worker` (verlangt Auth; im Compose-Healthcheck nutzt der Container-Service-Account `gustav_operator`).
- DB-Probe: `learning_worker_health_probe()` prüft Rolle (`gustav_worker`) + `current_setting('app.current_sub', true) IS NULL` (Worker setzt Sub erst während Job).
- Prometheus: `/metrics` → Eigencheck (Scrape-Job `learning-worker` in `prometheus.yml` ergänzen).

Runbook-Verknüpfung:
- Plan verlinkt auf `docs/operations/runbook_learning_worker.md` (Abschnitt 2 „Routineprüfungen“) für tägliche Checks.
- Fehlerbehebungsschritte (Neu-Enqueue etc.) bleiben im Runbook; Plan referenziert die Kapitelnummern.
- Update-Task: Runbook aktualisieren, sodass Healthcheck-Interpretationen (Status `healthy/degraded`) beschrieben sind.

Deployment-Schritte (CI/CD):
1. `supabase migration up` im CI, sicherstellen, dass Rollen (gustav_worker/web/operator) existieren.
2. Docker-Build für `learning-worker`, Push in Registry.
3. Compose-Stack deployen (`docker compose up -d learning-worker`), Healthcheck abwarten.
4. Prometheus/Grafana Reload (falls Dashboard-JSON aktualisiert wurde).
5. Smoke-Test: `curl -u operator:... http://localhost:8000/internal/health/learning-worker`.

Sicherheitsaspekte:
- Worker-Container nutzt `read-only` Root-FS außer `/tmp`.
- `.env` enthält keine Klartext-Passwörter im Repo; Secrets via `.env.local` oder Orchestrierungs-Secret-Store.
- Netzwerk: `learning-worker` kommuniziert nur mit `db`, `web` (健康check), optional `ollama`.
- Logging-Rotation im Compose verhindert Datenablage von PII über lange Zeit.

Offene Aufgaben (Operations):
- Dockerfile härten (non-root user, Drop von Capabilities).
- Dokumentation von Resource-Limits (CPU/GPU) für Vision-Modelle ergänzen.
- Automatisierten Smoke-Test für Healthcheck in CI-Stage integrieren.

---

## Offene Fragen
- Welche lokalen Modelle bevorzugen wir initial (z. B. qwen2.5‑vl vs. gemma3 vision)?
- Gewünschte maximale Wartezeit (Timeout) aus UX‑Sicht?
- Benötigen Lehrkräfte Einsicht in Vision‑Qualität (z. B. Konfidenz)?

---

## KI-Adapter (Ollama/DSPy) – Fahrplan Iteration 1 → 2

Ziele (KISS, Security first):
- Produktionsfähige Vision-/Feedback-Pipelines auf lokalen Modellen; Stub bleibt Standard für Tests.
- Eval-Prozess dokumentiert und reproduzierbar, ohne personenbezogene Daten.
- Adapter trennen Prompting/Parsing von Infrastruktur (Ollama/DSPy) klar, um Wartbarkeit zu sichern.

Roadmap:
1. **Eval vorbereiten (Week 1)**
   - Anonymisierte Stichprobe zusammenstellen (≈20 Vision-, ≈20 Text-Submissions).
   - Metriken definieren: OCR-Recall, Markdown-Qualität, Rubric-Abdeckung.
   - Skript `scripts/ai/eval_prepare.py` erzeugt Eval-Pakete (Hashes statt IDs).

2. **Vision-Adapter umsetzen (Week 2)**
   - Modellvergleich: `qwen2.5-vl` vs. `gemma3-vision` (Leistung, Lizenz, VRAM).
   - Implementierung `LocalVisionAdapter`: DSPy-Pipeline, Timeout 30 s, Unix-Socket-Verbindung zu Ollama.
   - Tests: Integration mit Ollama-Mock (HTTP) → prüft Markdown-Extrakt & Fehlerpfade.
   - Security: Fehlertexte maskieren PII, Logs enthalten nur Submission-/Job-IDs.

3. **Feedback-Adapter umsetzen (Week 3)**
   - Modell: `qwen2.5-instruct:7b` (Fallback `llama3.2:8b`), Prompt in `backend/learning/ai/prompts/feedback.md`.
   - Implementierung `LocalFeedbackAdapter`: strukturiertes Ergebnis (`feedback_md`, `analysis_json`).
   - Tests: Snapshot-Vergleich, Schema-Validierung (`criteria.v2`), Timeout 15 s.
   - Safety: Guardrail „no personal data“, Response-Länge begrenzen.

4. **Gemeinsame Validierung (Week 4)**
   - Eval-Suite (`scripts/ai/eval_run.py`) → Report `docs/ai/eval_report.md`.
   - Acceptance: ≥85 % OCR-Recall, Feedback deckt alle Kriterien (manuelles Review durch Felix).
   - Feature-Flag `AI_BACKEND=local` schaltet produktive Adapter ein; Default bleibt `stub`.

5. **Betrieb & Härten**
   - Observability: Eigene Metriken (`ai_vision_latency_seconds`, `ai_feedback_latency_seconds`), Alerts auf Timeout.
   - Rate-Limiting: Max. 1 Vision-Job pro Submission gleichzeitig, Puffer gegen Überlast.
   - Failover: Bei Modellfehler → Stub aktivieren, Alert auslösen.

Dokumentation:
- `docs/references/learning_ai.md` aktualisieren (Architektur, Config, Sicherheitsnotizen).
- `docs/operations/runbook_learning_worker.md` bekommt Abschnitt „Ollama neu starten“.
- Schülergerechte Erklärung in `docs/science/vision_adapter.md` (Transparenz, Bias-Hinweise).

Offene Tasks:
- GPU-Bedarf evaluieren (Compose-Update mit `deploy.resources.reservations.devices`).
- Datenschutz-Freigabe für Eval-Dataset einholen.
- Prompt-Auditing automatisieren (DSPy Logging, Review durch Lehrkräfte).

---

## Manueller UI-E2E-Test: Submission → Feedback

### Voraussetzungen
- Dienste hochfahren: `docker compose up -d db supabase web learning-worker`. Vor Start `supabase status` kontrollieren.
- Testnutzer: Lehrer (`test2@test.de`) und Schüler (`test1@test.de`), Passwort jeweils `123456`; falls Accounts fehlen, via `scripts/dev/create_login_user.sql` anlegen.
- Browser-Setup: Zwei Profile oder getrennte Tabs (Privatmodus für Lehrer, normaler Tab für Schüler), damit parallele Sessions möglich sind.
- Seed-Daten: Sicherstellen, dass mindestens eine Aufgabe im Kurs verfügbar ist (`scripts/import_legacy_backup.py --minimal` oder manuelle Task-Erstellung).
- Monitoring: 
  - Worker-Logs (`docker compose logs -f learning-worker`).
  - Healthcheck beobachten (`watch -n 15 curl -s http://localhost:8000/internal/health/learning-worker`).
  - Optional: Grafana-Dashboard „Learning Worker“ für `analysis_jobs_inflight`, `ai_worker_failed_total`.
- Aufräumen: Nach dem Test Submission/Kurse entfernen oder `supabase db reset`, damit Folge-Tests sauber starten.

Die folgenden Teilabschnitte beschreiben den manuellen Flow Schritt für Schritt (Lehrer → Schüler → Lehrer).

---

### Schritt 1: Lehrer richtet Kurs & Abschnitt ein

1. Lehrer im Browser anmelden (`test2@test.de` / `123456`).
2. Dashboard → „Kurs erstellen“:
   - Kursname „KI-E2E Testkurs“ setzen.
   - Schuljahr wählen, Kurs speichern.
3. Kursdetail öffnen → „Lerneinheit hinzufügen“:
   - Titel „Integrationstest Vision/Feedback“.
   - Kurzbeschreibung (Ziel des Tests) eintragen.
4. Einheit öffnen → Abschnitt anlegen:
   - Abschnittstitel „Handschrift-Aufgabe“.
   - Aufgabe hinzufügen (Text oder Bild). Kriterien definieren (mindestens zwei).
5. Abschnitt freigeben:
   - „Für Kurs freischalten“ wählen, Kurs „KI-E2E Testkurs“ markieren.
   - Sichtbarkeit prüfen (Status „freigegeben“ im Kurs).
6. Aufgaben-ID notieren (URL `.../tasks/<task_id>` oder Entwicklertools) für spätere Kontrolle.
7. Worker-Log im Terminal offen lassen (`docker compose logs -f learning-worker`).

Checkpoint: Kurs sichtbar, Abschnitt freigegeben, Aufgabe bereit.

---

### Schritt 2: Schüler reicht Submission ein

1. Schüler in separatem Browser/Tab anmelden (`test1@test.de` / `123456`).
2. Kursübersicht → Kurs „KI-E2E Testkurs“ öffnen; Abschnitt „Handschrift-Aufgabe“ sollte sichtbar sein.
3. Aufgabe öffnen:
   - Variante A (Text): Markdown-Text eingeben (z. B. „Experimenteller Testtext…“).
   - Variante B (Bild): Beispielbild hochladen (≤10 MiB, akzeptiertes Format). SHA/Dateigröße prüfen, falls Upload-Fehler auftreten.
4. Submission absenden → System zeigt Status „Analyse läuft“ (pending).
5. Backend prüfen:
   - Worker-Log sollte neue Job-ID anzeigen (`lease job ...`).
   - `analysis_jobs_inflight` im Dashboard kurz >0.
   - In Supabase (`supabase db remote run "select analysis_status, error_code from learning_submissions where id='<submission_id>';"`) kontrollieren, dass `analysis_status='pending'` gesetzt ist.
6. Warten, bis Worker Job verarbeitet:
   - Erwartet: Logeintrag „completed submission=<id>“.
   - Bei Störung: Retry-Log (`vision_retrying`/`feedback_retrying`) beobachten.

Checkpoint: Submission `completed` oder `failed` (letzteres mit `error_code`), Feedback-Daten verfügbar.

---

### Schritt 3: Lehrer prüft Live-Darstellung & Nachbereitung

1. Zur Lehrer-Sitzung zurückkehren (oder erneut anmelden).
2. Kurs „KI-E2E Testkurs“ → Live-Ansicht öffnen.
   - Erwartet: Neue Submission mit Status „Abgeschlossen“ (oder „Fehlgeschlagen“) und Feedback-Text.
   - Prüfen, ob Retry-/Fehlerstatus konsistent angezeigt werden (`vision_retrying` → Hinweis „Analyse wiederholt“).
3. Wenn Feedback fehlt:
   - Backend-Logs checken (Worker-Log, `ai_worker_failed_total`).
   - Health-Endpunkt auf `degraded`? Dann Rolle prüfen (`gustav_worker`).
4. Ergebnisse dokumentieren:
   - Submission-ID, Zeitstempel, Status/Feedback notieren.
   - Screenshots aufnehmen (für QA-Archiv).
5. Nachbereitung:
   - Aufräumen: Kurs/Submission löschen oder `supabase db reset`.
   - Erkenntnisse / Bugs im Ticket-System erfassen (inkl. Logs, IDs).
   - Optional: Alerting-Metriken exportieren (Prometheus Query speichern).

Finaler Check: UI zeigt korrekte Daten, Worker-/Monitoring-Signale im erwarteten Bereich.

---

## Befehle & Workflow
- Contract‑First: `api/openapi.yml` anpassen
- Migration: `supabase migration new`, `supabase migration up`
- Tests: `.venv/bin/pytest -q`
- Lokal stacken: `docker compose up -d --build`, `supabase status`

---

## Quellen & Legacy‑Bezug
- Alpha2 Stub: `backend/learning/repo_db.py` (Analyse‑Platzhalter)
- Legacy (Alpha1) Vision: `legacy-code-alpha1/app/ai/vision_processor.py` (DSPy+Ollama)
- Glossar: `docs/glossary.md`

---

## Architektur‑Reflexion zum Worker (KISS, Konsistenz, Wartbarkeit, Robustheit, Sicherheit)

Kurzer Überblick: Fundament ist der einzelne Prozess `backend.learning.workers.process_learning_submission_jobs`. Er bindet die Ports `VisionAdapterProtocol` und `FeedbackAdapterProtocol`, orchestriert Retries über Postgres-Funktionen und hält sich strikt an die Glossar-Begriffe.

---

## TDD‑Fortschritt: Adapter‑ und DI‑Tests (heute)

Geschrieben (rote Tests, sollen aktuell fehlschlagen bis Implementierung folgt):
- Unit‑Tests Vision‑Adapter lokal: `backend/tests/learning_adapters/test_local_vision.py`
  - JPEG/PNG/PDF Happy‑Path liefert Markdown (`VisionResult.text_md`) und `raw_metadata.adapter in {local, local_vision}`.
  - Timeout → `VisionTransientError`.
  - Unsupported MIME (z. B. `application/zip`) → `VisionPermanentError`.
- Unit‑Tests Feedback‑Adapter lokal: `backend/tests/learning_adapters/test_local_feedback.py`
  - Happy‑Path liefert `feedback_md` und `analysis_json` gemäß `criteria.v2` mit Score‑Grenzen (0..5, 0..10; pro Kriterium `max_score` Default 10).
  - Timeout → `FeedbackTransientError`.
- DI‑Switch im Worker: `backend/tests/test_learning_worker_di_switch.py`
  - Default: ohne Env werden Stub‑Adapter geladen (Pfad‑Asserts auf Import‑Module).
  - `AI_BACKEND=local`: erwartet Import der Module `backend.learning.adapters.local_vision` und `...local_feedback`.

Nächste Schritte (grün machen):
- Minimal‑Implementierung `backend/learning/adapters/local_vision.py` und `local_feedback.py` mit `build()`‑Fabriken und Exceptions gemäß Ports.
- DI‑Alias in Worker ergänzen: `AI_BACKEND=stub|local` → setzt `LEARNING_*_ADAPTER` vor `import_module`.
- Unit‑Tests ausführen und iterativ Fehler beheben (Timeout‑Mapping, MIME‑Filter, Metadaten, Score‑Bounds).

- **KISS (Keep it simple)**
  - Single responsibility: Der Worker macht ausschließlich Leasing → Vision → Feedback → Persistieren; kein Mischmasch mit API/DI-Frameworks.

### Ports extrahiert: Motivation & Auswirkungen (heute)
- Motivation: Clean Architecture. Ports (Ergebnis‑Typen, Protokolle, Fehler) gehören nicht in den Worker, sondern in ein dediziertes, framework‑freies Modul, damit Adapter unabhängig sind und zyklische Abhängigkeiten vermieden werden.
- Umsetzung:
  - Neu: `backend/learning/adapters/ports.py` mit `VisionResult`, `FeedbackResult`, `VisionAdapterProtocol`, `FeedbackAdapterProtocol`, Fehlerklassen (`VisionTransientError`, `VisionPermanentError`, `FeedbackTransientError`, `FeedbackPermanentError`).
  - Worker und Adapter importieren jetzt aus `backend.learning.adapters.ports`.
  - Kompatibilität: Der Worker re‑exportiert die Ports‑Namen via `__all__`, damit existierende Tests/Imports (z.B. `from ...process_learning_submission_jobs import VisionResult`) weiterhin funktionieren.
- Auswirkungen auf Tests/Code:
  - Adapter‑Tests grün mit neuen Imports; DI‑Switch‑Test bleibt unverändert.
  - Keine API/DB‑Änderungen nötig; nur interne Python‑Modulstruktur.
- Sicherheit/Wartbarkeit:
  - Klare Grenze zwischen Use‑Case (Worker) und Infrastruktur (Adapter). Fehler‑Taxonomie an zentraler Stelle.
- Nächste Schritte:
  - E2E‑Tests mit `AI_BACKEND=local` (gemockte Clients) für Pending → Completed inkl. Retry‑Pfad spezifizieren und implementieren.
  - Privacy‑Logging‑Negativtests ergänzen (Logs dürfen keine Textauszüge/Binary enthalten; nur IDs/Fehlercodes/Timings).
  - Optional: Weitere Adapters (z.B. cloud_*) können nun konsistent gegen dieselben Ports implementiert werden.
  - Prozesskontrolle bleibt minimal (`run_once`, `run_forever`), Backoff wird über eine einzige Hilfsfunktion `_backoff_seconds` gesteuert.
  - Dataclasses (`QueuedJob`, `VisionResult`, `FeedbackResult`) transportieren nur zwingend notwendige Felder. Keine verschachtelten Nebenobjekte → einfach zu testen.

- **Konsistenz**
  - Glossar- und Domain-Sprache taucht 1:1 auf (`analysis_status`, `vision_retrying`, `feedback_failed`).
  - SQL-Funktionen heißen wie im Code: `_update_submission_completed` ruft `learning_worker_update_completed`; keine Abkürzungen, keine Dopplungen.
  - Migrationen und Code verwenden identische Feldnamen (`visible_at`, `retry_count`, `error_code`), wodurch Tests und Doku übereinstimmen.

- **Wartbarkeit**
  - Konfigurierbare Werte (`LEASE_SECONDS`, `MAX_RETRIES`, `WORKER_BACKOFF_SECONDS`, `LEARNING_*_ADAPTER`) stehen gebündelt am Datei-Anfang; Defaults sind konservativ.
  - Tests decken die Hauptpfade (Happy/Retries/Failed/Security) ab; Fehlerfälle spiegeln sich in klar benannten Exceptions (`VisionTransientError`, `FeedbackPermanentError`).
  - Hilfsfunktionen sind kurz (<40 Zeilen) und beschreiben ihr Ziel über Docstrings (Intent + Permissions), wodurch neue Kollegen zügig einsteigen.

- **Robustheit**
  - Leasing via `FOR UPDATE SKIP LOCKED` und `lease_key` schützt vor Doppeltverarbeitung; `_nack_retry` setzt Sichtbarkeit sauber zurück.
  - Terminale Fehler landen in Submission (`learning_worker_update_failed`) und Queue (`_mark_job_failed`), somit vollständige Auditspur.
  - `_truncate_error_message` verhindert Log-/DB-Overflow; Backoff ist exponentiell und deckelt so Dauerschleifen.

- **Sicherheit**
  - `_set_current_sub` erzwingt RLS-Kontext bevor gelesen/geschrieben wird; Sub stammt aus Job-Payload bzw. Submission.
  - Security-Definer-Funktionen isolieren DML auf `learning_submissions`; Worker-Rolle (`gustav_worker`) hat keine direkten UPDATE-Rechte.
  - Logs enthalten ausschließlich IDs, Retry-Zähler und Fehlercodes. Keine Modellantworten oder Rohtexte.

- **Benennungen & Lesbarkeit**
  - Funktionsnamen verwenden klare Verben (`_mark_feedback_retry`, `_handle_vision_error`). Bei Dopplungen (Vision/Feedback) sorgt die Phase im Namen für Orientierung.
  - Variablen bleiben sprechend (`next_visible`, `lease_until`, `truncated`). UUIDs werden als Strings behandelt, was die JSON-Serialisierung vereinfacht.
  - Exceptions spiegeln Domain-Ereignisse wider und erleichtern das Mapping auf `error_code`.

**Verbesserungspotenzial / Beobachtungen**
- Logging-Level für Retries steht derzeit auf `warning`; evtl. auf `info` reduzieren, um Alert-Fatigue zu vermeiden (Alerting übernimmt Monitoring).
- `_mark_submission_retry` und `_mark_feedback_retry` sind thin wrappers; belassen sie wegen Lesbarkeit. Bei Bedarf könnte ein Param-Enum eingeführt werden.
- `QueuedJob.id` und `.submission_id` sind `str`; langfristig könnte eine kleine Value-Object-Schicht (`UUID`) Tippfehler verhindern, ist aktuell aber nicht zwingend.
- Tests prüfen bereits Security-Definer-Aufrufe; ergänzend könnten wir eine Smoke-Regel einführen, die `gustav_worker`-Rolle ohne Funktionszugriff scheitern lässt (Defense in depth).

Unterm Strich bleibt die Implementation KISS-konform, konsistent benannt und sicher verschlossen. Die genannten kleinen Nacharbeiten würden vor allem die Developer Experience schärfen, ohne das Grunddesign zu verändern.
