# Plan: Lernen — Datei-Uploads für Submissions, OCR und persistenter Rohtext

Ziel: Schüler können Lösungen als Datei (Foto meiner Handschrift oder PDF) hochladen. Die Datei wird sicher im Storage-Bucket abgelegt. Anschließend wird Handschrift/Text per OCR extrahiert und der Rohtext „wie eine normale Textabgabe“ in der Datenbank gespeichert, sodass der Analyse-/Feedback-Flow identisch funktioniert.

Status heute (Ist):
- Upload-Intent für Schüler vorhanden (Stub-URL, kein echter Bucket-Presign). Route: `POST /api/learning/courses/{course_id}/tasks/{task_id}/upload-intents`.
- Submissions-Endpoint akzeptiert `text | image | file (PDF)`. Für `image/file` werden nur Metadaten gespeichert. OCR ist ein Platzhalter („OCR placeholder …“) in `analysis_json`; `text_body` bleibt leer.
- DB-Constraint verbietet aktuell für `image` ein gefülltes `text_body`.

Dieses Plan-Dokument beschreibt die Umsetzung hin zu: echter Presign/Verify gegen Storage, OCR-Adapter, und Persistenz des OCR-Rohtexts in `text_body` (auch für `image/file`).

---

## User Story
Als Schüler möchte ich Aufgabenlösungen als Datei (Foto meiner Handschrift oder PDF) hochladen, damit ich nicht alles abtippen muss. Nach dem Upload soll GUSTAV die Datei automatisch per OCR auswerten und den erkannten Text wie eine normale Textabgabe speichern, damit ich sofort Feedback und eine einheitliche Historie erhalte.

## Architekturleitplanken
- Die HTTP-Schicht löst nur den Use Case `IngestLearningSubmission` aus. Sie orchestriert keine OCR- oder Analyse-Details, sondern delegiert an Ports.
- `IngestLearningSubmission` nutzt zwei Ports: `SubmissionStoragePort` (Presign/Head/Verify) und `SubmissionOCRPort` (OCR-Aufträge terminieren). Beide Ports sind frameworkfrei und werden im Web-Layer per Adapter injiziert.
- Der Use Case persistiert Submissions sofort mit `analysis_status=pending` und emittiert das Domänenereignis `LearningSubmissionOCRRequested` inklusive Storage-Metadaten.
- Ein Worker (`learning_ocr_job_processor`) konsumiert das Ereignis, ruft den OCR-Adapter auf, schreibt das Ergebnis über den Repository-Port und stößt anschließend den Analysis-/Feedback-Flow an (`LearningSubmissionAnalysisRequested`).
- Falls die OCR-Laufzeit extrem kurz ist, darf der Worker synchron inline laufen; der Hook bleibt dennoch bestehen, damit später ohne Umbau auf echte Asynchronität umgestellt werden kann (z. B. PostgreSQL-Notify, Supabase Queue oder Celery).

## BDD-Szenarien (Given-When-Then)
Happy Path — Bild (JPEG/PNG):
- Given ich bin als Schüler im Kurs eingeschrieben und die Aufgabe ist freigeschaltet
- And ich fordere einen Upload-Intent für `kind=image` an
- When ich die Datei über die Presign-URL hochlade und anschließend eine Submission mit `storage_key, mime_type, size_bytes, sha256` erstelle
- Then speichert der Server die Submission mit `analysis_status=pending` und emittiert `LearningSubmissionOCRRequested`
- And die Antwort enthält `analysis_status=pending`, `analysis_json` leer, `text_body` noch leer
- And ein Worker verarbeitet das Ereignis, führt OCR aus, aktualisiert Submission mit `text_body` und `analysis_status=completed`
- And die Historie zeigt den erkannten Text an

Happy Path — PDF:
- Given ich bin als Schüler im Kurs eingeschrieben
- When ich Upload-Intent `kind=file` (PDF) hole, hochlade und Submission erstelle
- Then gilt derselbe Pending-Flow: Submission `analysis_status=pending`, Worker liefert OCR-Text nach

Idempotenz:
- Given ich sende dieselbe Submission erneut mit gleichem `Idempotency-Key`
- Then erhalte ich dieselbe gespeicherte Abgabe zurück (kein Duplikat)

Validierung (Client-/Server-seitig):
- Given MIME-Type ist nicht erlaubt (`image/gif`)
- When ich Upload-Intent/Submissions anfrage
- Then erhalte ich `400 detail=mime_not_allowed/invalid_image_payload`

Integritätscheck:
- Given `size_bytes/sha256` passen nicht zur hochgeladenen Datei
- Then `POST /submissions` antwortet mit `400 invalid_image_payload|invalid_file_payload`

Sicherheit — CSRF/Origin:
- Given der `Origin` ist fremd oder fehlt in STRICT/PROD-Mode
- Then `POST /upload-intents` und `POST /submissions` antworten `403 csrf_violation`

Sicherheit — RLS/Mitgliedschaft:
- Given ich bin kein Kursmitglied
- Then beide Endpunkte liefern `403` (oder `404` bei nicht sichtbaren Tasks)

Edge Cases:
- Erste/weitere Versuche: `attempt_nr` wird korrekt inkrementiert; max_attempts enforced → `400 max_attempts_exceeded`.
- Dateigröße: exakt 10 MiB erlaubt, >10 MiB → `400 size_exceeded`.
- Ungültiger `storage_key` (Traversal `..`, Großbuchstaben): `400 invalid_*_payload`.
- OCR-Timeout: Worker erkennt OCR-Timeout > 30s, markiert Submission mit `analysis_status=failed` und audit-loggt den Fehler.
- OCR-Retry: Bei transientem Fehler wird der Job max. dreimal mit Exponential Backoff erneut ausgeführt; danach `analysis_status=failed` + Hinweis in `analysis_json`.

## API (OpenAPI) — Contract-First Änderungen
Ziel: Keine neue Route notwendig. Verhalten präzisieren:
- `POST /api/learning/courses/{course_id}/tasks/{task_id}/upload-intents` bleibt, liefert echte Presign-URL (Storage-Adapter), `storage_key` im Namensraum `submissions/{course}/{task}/{student}/…`.
- `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions`: Für `kind=text` bleibt Response `201` (Analyse abgeschlossen). Für `kind=image|file` liefert die Route `202`, `analysis_status=pending`, `error_code` leer; Worker aktualisiert später `analysis_status=completed` oder `failed`.

OpenAPI-Ausschnitt (Ergänzungen in Beschreibung; keine Schema-Änderung nötig):
```yaml
  /api/learning/courses/{course_id}/tasks/{task_id}/submissions:
    post:
      description: >-
        Akzeptiert Text direkt oder Metadaten zu hochgeladenen Bildern/PDFs. Bei reinen Textabgaben wird die Submission synchron erstellt (`201`). Für Bild/PDF persistiert der Server zunächst eine Submission mit `analysis_status=pending`, stößt OCR asynchron über den Worker an und liefert `202 Accepted`. Sobald der Worker das OCR-Ergebnis gespeichert hat, aktualisiert sich `analysis_status=completed` und `analysis_json.text` spiegelt den erkannten Text.
      responses:
        '201':
          description: Submission erstellt; gilt für `kind=text`.
        '202':
          description: Submission angenommen; OCR und Analyse laufen asynchron, `analysis_status=pending`.
```

## Datenbank — Migrationen (Supabase/PostgreSQL)
Notwendig: `text_body` muss für `image/file` optional gefüllt sein (für OCR-Ergebnis). Zusätzlich harte „file“-Constraints. Die Submission wird zunächst mit `analysis_status='pending'` gespeichert; Worker aktualisiert später auf `completed` bzw. `failed`.

Skizze SQL (neue Migration):
```sql
set search_path = public, pg_temp;
-- 1) Relax image-Constraint: `text_body` darf (optional) gefüllt sein
alter table public.learning_submissions drop constraint if exists learning_submissions_image_kind;
alter table public.learning_submissions add constraint learning_submissions_image_kind
  check (
    kind <> 'image' or (
      storage_key is not null and
      mime_type in ('image/jpeg','image/png') and
      size_bytes is not null and size_bytes between 1 and 10485760 and
      sha256 ~ '^[0-9a-f]{64}$'
    )
  );
-- 2) Ergänze file-Constraint symmetrisch (falls noch nicht vorhanden)
alter table public.learning_submissions drop constraint if exists learning_submissions_file_kind;
alter table public.learning_submissions add constraint learning_submissions_file_kind
  check (
    kind <> 'file' or (
      storage_key is not null and
      mime_type = 'application/pdf' and
      size_bytes is not null and size_bytes between 1 and 10485760 and
      sha256 ~ '^[0-9a-f]{64}$'
    )
  );
-- 3) Bestehendes Size-Limit (10 MiB) bleibt übergreifend aktiv (separate Check-Constraint existiert bereits).
-- 4) Analyse-Status um pending/failed erweitern
alter table public.learning_submissions drop constraint if exists learning_submissions_analysis_status_check;
alter table public.learning_submissions add constraint learning_submissions_analysis_status_check
  check (analysis_status in ('pending','completed','failed'));
-- 5) Neue Spalten für OCR-Jobs
alter table public.learning_submissions
  add column if not exists ocr_attempts integer not null default 0,
  add column if not exists ocr_last_error text,
  add column if not exists ocr_last_attempt_at timestamptz;
-- 6) Job-Tabelle für Worker (FIFO-Queue)
create table if not exists public.learning_submission_ocr_jobs (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references public.learning_submissions(id) on delete cascade,
  payload jsonb not null,
  status text not null default 'queued' check (status in ('queued','processing','completed','failed')),
  retry_count integer not null default 0,
  visible_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists learning_submission_ocr_jobs_visible_idx
  on public.learning_submission_ocr_jobs (visible_at) where status = 'queued';
```
Hinweis: Keine Backfill-Änderungen nötig. Historische Datensätze bleiben gültig. Bei neuen Submissions (image/file) setzt der Use Case `analysis_status=pending`; der Worker schreibt nach erfolgreicher OCR den erkannten Rohtext in `text_body`.

## Testplan (pytest, TDD)
Vor Implementierung failing Tests schreiben. Echte lokale Test-DB; externe Dienste mocken.

- Contract-/Route-Tests (API):
- `test_upload_intent_uses_storage_adapter_and_returns_presign_url()`
  - Arrange: Fake Storage-Adapter injizieren (liefert URL + headers). Kurs/Task/Release vorbereiten, Student einschreiben.
  - Act: `POST /upload-intents` (image/pdf)
  - Assert: 200, `storage_key`-Prefix `submissions/…`, erlaubte MIME, TTL-Hinweis.

- `test_create_submission_image_returns_pending_and_enqueues_job()`
  - Arrange: Fake OCR-Adapter ge-patcht (wird vom Worker genutzt), Storage-Verify aktiv.
  - Act: Upload-Intent → PUT (simuliert) → `POST /submissions` mit Metadaten.
  - Assert: 202, Response `analysis_status == "pending"`, `learning_submission_ocr_jobs` enthält neuen Eintrag.

- `test_worker_processes_job_and_persists_text_body()`
  - Arrange: Initial Submission erzeugen wie oben, dann Worker-Task aufrufen.
  - Act: Worker holt Job, OCR-Adapter liefert „Hallo OCR“.
  - Assert: Submission `analysis_status == "completed"`, `text_body == "Hallo OCR"`, `analysis_json.text` aktualisiert.

- `test_worker_marks_submission_failed_after_max_retries()`
  - Arrange: OCR-Adapter wirft transienten Fehler; Worker läuft dreimal.
  - Assert: Submission `analysis_status == "failed"`, `ocr_last_error` gesetzt, Job `status=failed`.

- `test_submission_rejected_on_integrity_mismatch()`
  - Size/Hash absichtlich falsch → 400 mit `invalid_*_payload`.

- `test_csrf_enforced_on_upload_intents_and_submissions()`
  - Fremder Origin/fehlender Header in STRICT/PROD → 403.

- `test_idempotency_returns_same_row()`
  - Doppelter POST mit gleichem Header liefert identischen Datensatz.

Repo-/RLS-Tests:
- `test_repo_allows_pending_submission_without_text_body()`
  - Direkter Insert (über Repo) mit `kind=image|file`, `analysis_status=pending`, leeres `text_body`.
- `test_repo_allows_completed_submission_with_text_body_after_worker()`
  - Repo-Update von Pending → Completed mit OCR-Text funktioniert.
- `test_repo_records_ocr_attempts_and_errors()`
  - `ocr_attempts`, `ocr_last_error` werden korrekt fortgeschrieben.

## Implementierungsschritte (minimal, Red-Green-Refactor)
1) OpenAPI-Beschreibung anpassen (201 vs. 202, Pending-Status), CHANGELOG-Eintrag vorbereiten.
2) Migration: Constraints, Analyse-Status, OCR-Metadaten und Job-Tabelle laut SQL-Skizze. `supabase migration new`, dann `supabase migration up`.
3) Application-Layer:
   - Use Case `IngestLearningSubmission` erstellen (oder vorhandenen erweitern) mit Ports `SubmissionStoragePort`, `SubmissionOCRPort`, `LearningSubmissionEventPort`.
   - Use Case validiert Kurs-/Task-Zugriff, führt Storage-Verify (`head_object`) aus, persistiert Submission mit `analysis_status=pending`, `ocr_attempts=0`, und ruft den Event-Port auf (`LearningSubmissionOCRRequested`).
4) Web-Layer:
   - In `backend/web/routes/learning.py` `set_storage_adapter(adapter)` und `set_submission_event_bus(bus)` nutzen, Request → Use Case mappen.
   - `create_upload_intent`: echten Presign über Storage-Adapter (Bucket via `SUBMISSIONS_STORAGE_BUCKET`, Default `submissions`). Pfad-Layout: `submissions/{course_id}/{task_id}/{student_sub}/{timestamp}-{uuid}.{ext}`.
   - `create_submission`: Aufruf des Use Case, Response 202 mit Pending-Payload.
5) Worker (`learning_ocr_job_processor`):
   - Adapter `SubmissionOCRPort` implementiert (Stub + lokales Ollama-Backend via DSPy).
   - Worker zieht Jobs aus `learning_submission_ocr_jobs`, führt OCR aus, aktualisiert Submission (`analysis_status=completed`, `text_body`, `analysis_json`), stößt `LearningSubmissionAnalysisRequested` an.
   - Fehlerpfade: Retries (max. 3, exponential backoff), danach `analysis_status=failed`, Audit-Log.
6) Repo-/Persistence-Layer:
   - Repository-Funktionen für Pending-Insert, Completed-Update, Failed-Update, Job-Queue-Operationen (enqueue, lease, ack, retry).
   - `_build_analysis_payload` nutzt `text_body`, sobald verfügbar.
7) Sicherheit/DX:
   - CSRF- und RLS-Prüfungen unverändert; zusätzlich Audit-Logging für OCR-Jobs (wer/was/wann).
   - Logging: `storage_key` ohne PII, Presign-URLs nie loggen; OCR-Ergebnisse nur auf INFO-Level, kein Debug-Logging von Rohtext.
8) Dokumentation & Kommentare:
   - Docstrings für Use Case, Ports, Worker (Warum, Parameter, Berechtigungen).
   - `docs/references/learning.md` Abschnitt „OCR & Datei-Uploads“ ergänzen.

## Sicherheit & Datenschutz (DSGVO)
- Buckets privat; nur kurzlebige Presign-URLs (≤ 10 min). Keine PII in Query-Parametern.
- Hash/Größe validieren; Storage-Key-Namensraum verhindert Traversal; Regex sperrt `..`.
- Rollen: Presign/Head nur über Service-Key (Server-Seite). Schüler sehen/verändern keine Bucket-Inhalte direkt.
- `Cache-Control: private, no-store` auf allen Antworten.
- OCR-Dienst: läuft lokal über Ollama/DSPy (localhost/Unix-Socket); Service-Credentials im Secret-Store; Ergebnisse werden nur temporär im Arbeitsspeicher gehalten.
- Logging & Audit: Jeder OCR-Job (Start, Erfolg, Failure) wird in `learning_submission_ocr_jobs` protokolliert und zusätzlich im Audit-Log erfasst (Submission-ID, Kurs-ID, User-ID, Status). Keine Rohtexte im Audit-Log.
- Incident Response: Fehlgeschlagene OCR nach max. Retries erzeugt Monitoring-Event (`ocr_failed_total`), löst Alert aus.
- Data Minimization: PDFs/Bilder nur im Storage-Bucket, Worker streamt Daten direkt an den lokalen OCR-Prozess (kein Zwischen-Write auf Disk). OCR-Rohtext wird ausschließlich in `text_body` persistiert.

## Rollout
- Migrations ausführen.
- Bucket `submissions` (privat) anlegen (Supabase UI/CLI) und Service-Key konfigurieren (`SUBMISSIONS_SERVICE_URL/KEY`, `SUBMISSIONS_STORAGE_BUCKET`).
- Worker-Infrastruktur bereitstellen (z. B. Celery Worker oder Supabase Queue-Function) und Deployment-Skripte ergänzen.
- Feature-Flag für OCR-Adapter: Start mit Stub (deterministische Demo), später lokaler Ollama-Adapter. Flag steuert auch, ob Worker Jobs konsumiert.

## Definition of Done
- Tests grün: Intent, Pending-Response (202), Worker-Flow (Retry/Fail), OCR-Text in `text_body`, Idempotenz, CSRF, Integritätsprüfung.
- Monitoring: Alerts für `ocr_failed_total` und Job-Stau eingerichtet.
- Manuell: E2E (lokal) via UI — Bild/PDF hochladen → Submission erscheint sofort mit Pending-Status, nach Worker-Durchlauf zeigt History den erkannten Text, Download-Link funktioniert.
- Docs aktualisiert (API-Hinweis, Referenz, CHANGELOG).

---

## Offene Punkte / spätere Iterationen
- Adaptive Priorisierung der OCR-Jobs (z. B. Lehrer wartet auf Ergebnis) → Prioritätsfeld in Queue sowie UI-Anzeige.
- Textnormalisierung (z. B. Zeilenumbrüche, Sprache) vor Analyse.
- Weitere Dateitypen (HEIC, DOCX) bewusst ausgeklammert.
- OCR-Qualitätsmetriken (Confidence, Sprache) sammeln und im Feedback darstellen.
