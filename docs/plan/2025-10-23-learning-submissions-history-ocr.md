# Plan: Lernen – Submissions-Historie und OCR/Analyse/Feedback (MVP+)

Ziel: UI‑fertige Backend‑Funktionen für (Mehrfach‑)Einreichungen inklusive abrufbarer Historie und minimaler KI‑Stub‑Pipeline (OCR für Bilder, Analyse + Feedback für Text/Bild). Contract‑First, TDD, Clean Architecture, KISS.

## Scope
- History‑API: Schüler sieht eigene Abgaben zu einer Aufgabe (neueste zuerst).
- Create‑API: Bestehende Einreichung bleibt, erweitert um konsistentes `analysis_json` (OCR/Analyse‑Stub) und `feedback`.
- OCR‑Stub: Für Bild‑Abgaben einheitlich `text` im `analysis_json` (erkannter Text).
- Analyse‑Stub: Für Text/Bild ein minimalistisches Analyseergebnis im `analysis_json` (z. B. Länge, simple Heuristik), Status `completed`.

Komplexitätsgrenze (KISS):
- Kein zusätzlicher Service/Worker in dieser Iteration. OCR/Analyse‑Stub als reine, kleine Hilfsfunktionen im Repo‑Modul (keine neue Schicht), um Single‑Responsibility nicht zu verletzen: Persistenz bleibt im Repo, Stub‑Logik ist pure function, lokal gekapselt.

Nicht enthalten (später): Asynchrone Jobs/Worker, echtes Modell‑Inference, SSE/Polling‑Endpunkt, Spaced Repetition, Analytics Dashboard.

## User Stories
1) Als Schüler möchte ich alle meine bisherigen Abgaben zu einer Aufgabe sehen, um meinen Fortschritt zu verstehen.
2) Als Schüler möchte ich Text‑ oder Bild‑Lösungen einreichen und direkt ein Feedback erhalten, um weiterzuarbeiten.
3) Als Schüler möchte ich bei Bild‑Abgaben, dass erkennbarer Text im Feedback berücksichtigt wird (OCR‑Stub).

## BDD‑Szenarien (Given‑When‑Then)
- History – Happy Path:
  - Given: Mitglied des Kurses, Abschnitt freigegeben, ≥1 Abgabe vorhanden.
  - When: GET `/api/learning/courses/{cid}/tasks/{tid}/submissions?limit=20&offset=0`.
  - Then: 200, Liste nur eigener Abgaben, neueste zuerst, Felder: `id, attempt_nr, kind, analysis_status, analysis_json, feedback, created_at, completed_at`.
- History – Leere Historie:
  - Given: Mitglied, Abschnitt freigegeben, noch keine Abgabe.
  - When: GET history.
  - Then: 200, leeres Array `[]`, Header `Cache-Control: private, no-store`.
- History – Forbidden:
  - Given: Kein Mitglied.
  - When: GET history.
  - Then: 403 `forbidden` mit `Cache-Control: private, no-store`.
- History – Not Found:
  - Given: Mitglied, Task/Section nicht freigegeben.
  - When: GET history.
  - Then: 404 `not_found` (keine Existenz‑Leaks).
- History – Stabiler Sortierschlüssel:
  - Given: Mehrere Abgaben mit identischem `created_at` (Randfall).
  - When: GET history.
  - Then: Sekundärsortierung `attempt_nr desc` stellt stabile Reihenfolge sicher.
- History – Ungültige UUID:
  - Given: Authentifiziert.
  - When: GET mit `course_id` oder `task_id` ≠ UUID.
  - Then: 400 `detail=invalid_uuid`, Header `Cache-Control: private, no-store`.
- Create – Text + Analyse‑Stub:
  - Given: Freigegeben, Versuche verfügbar.
  - When: POST submission `{ kind: 'text', text_body: 'Hallo Welt' }`.
  - Then: 201, `analysis_status='completed'`, `analysis_json` enthält z. B. `{ text: 'Hallo Welt', length: 10, scores: [{criterion:'Graph korrekt', score:8, explanation:'…'}] }`, `feedback` gefüllt.
- Create – Bild + OCR‑Stub:
  - Given: Freigegeben, valide Metadaten (png/jpeg, sha256, size>0).
  - When: POST submission `{ kind: 'image', storage_key, mime_type, size_bytes, sha256 }`.
  - Then: 201, `analysis_status='completed'`, `analysis_json` enthält mindestens `{ text: '…', scores: [...] }`, `feedback` gefüllt.
- Create – Attempt‑Limit:
  - Given: `max_attempts=2`, zwei Abgaben existieren.
  - When: POST dritte Abgabe.
  - Then: 400 `detail=max_attempts_exceeded`.
- Create – Idempotenz:
  - Given: Gleiches `Idempotency-Key`.
  - When: POST zweimal.
  - Then: 201 identische Antwort; keine Doppelanlage.
- Security – CSRF:
  - Given: Fremde `Origin`.
  - When: POST.
  - Then: 403 `csrf_violation` (Forwarded‑Header nur mit `GUSTAV_TRUST_PROXY=true`).

## API Contract‑Entwurf (OpenAPI‑Erweiterungen)
- GET `/api/learning/courses/{course_id}/tasks/{task_id}/submissions`
  - tags: [Learning]
  - summary: List submissions for the current student (most recent first)
  - security: cookieAuth; x-permissions.requiredRole: student
  - parameters:
    - path: `course_id` (uuid), `task_id` (uuid)
    - query: `limit` (int, 1..100, default 20), `offset` (int, ≥0, default 0)
  - responses:
    - 200: array of `LearningSubmission` (bestehendes Schema), Header `Cache-Control: private, no-store`
    - 400: `invalid_uuid`
    - 401/403/404: wie bestehende Learning‑Endpunkte (gleiche Cache‑Header)

- Hinweis: Für UI ist ein zusätzlicher Einzel‑Abruf (`GET /api/learning/submissions/{submission_id}`) optional; wird bei Bedarf separat spezifiziert.

`LearningSubmission` wird weiterverwendet. `analysis_json` enthält:
- Einheitlich: `text: string` (typed oder OCR), `scores: array<{ criterion: string, score: 0..10, explanation: string }>`
- Optional: `length: number` (Zeichenanzahl des analysierten Textes)

## Datenbank & Migrationen
- Keine neue Tabelle erforderlich (Synchron‑Stub). Historie nutzt vorhandene Indizes: `idx_learning_submissions_student_task_created`.
- Optional (später, Async): `learning_analysis_jobs` + RLS/Policies.

## TDD‑Plan (rote Tests zuerst)
- `test_list_submissions_history_happy_path`
- `test_list_submissions_history_empty_returns_200_array`
- `test_list_submissions_forbidden_non_member`
- `test_list_submissions_404_when_not_released`
- `test_list_submissions_invalid_uuid_returns_400_with_cache_header`
- `test_list_submissions_ordering_is_stable_by_created_at_then_attempt_desc`
-- `test_create_submission_image_includes_text_and_scores_in_analysis_json`
  - Variante: Text‑Abgabe setzt `analysis_json.text`, `length` und `scores[*].explanation`.
  - Variante: Idempotenz liefert identische Submission (id/attempt_nr/created_at gleich).

Alle Tests prüfen zusätzlich `Cache-Control`‑Header gemäß Vertrag.

## Implementierung (minimal, Clean Architecture)
- Use Case: `ListSubmissionsUseCase` (repo‑agnostisch) mit Paging‑Bounds.
- Repo (DB): `DBLearningRepo.list_submissions(student_sub, course_id, task_id, limit, offset)`
  - Enforce: Mitgliedschaft + Sichtbarkeit (via `get_task_metadata_for_student`) und `SET LOCAL app.current_sub`.
  - Rückgabe: Neueste zuerst (`created_at desc, attempt_nr desc`).
- Web‑Adapter: FastAPI‑Route für GET History (Validierungen, UUID, Cache‑Header, Fehlercodes wie Learning‑Konventionen).
- OCR/Analyse‑Stub: In `create_submission` erzeugt Repo synchron `analysis_json`:
  - Text: `text` (aus `text_body`), `length`, `scores` je Kriterium mit `explanation`.
  - Bild: `text` (Dummy‑OCR aus Bild‑Metadaten), `length`, `scores` je Kriterium mit `explanation`.

Wartbarkeit:
- Pure Helper im Repo‑Modul (`_make_text_analysis_json`, `_make_image_analysis_json`) mit klaren Docstrings; keine Seiteneffekte.
- Einheitliche Pagination‑Normalisierung wie bei Sections (1..100, offset ≥0) im Use Case.

## Sicherheit
- RLS bleibt maßgeblich; Limited‑DSN (`gustav_limited`) erzwingen.
- CSRF Same‑Origin (bereits implementiert); Proxy‑Trust nur mit `GUSTAV_TRUST_PROXY=true`.
- Idempotenz (bereits vorhanden) unverändert nutzen.
- Rate‑Limit (Folgeschritt): pro `sub`/Task/Zeitfenster, um Missbrauch zu verhindern.
- Datenschutz: `analysis_json` bleibt klein, ohne PII; keine Payload‑Inhalte in Logs.

## Rollout
1) OpenAPI ergänzen (History‑Pfad) + Doku (Referenz) aktualisieren; Property in `LearningSubmission` von `feedback_md` → `feedback` umbenennen; Beschreibung von `analysis_json` gemäß oben.
2) Tests schreiben (rot).
3) Minimal‑Implementierung, bis Tests grün.
4) Review: Code‑Klarheit, Clean Architecture, Sicherheitscheck.
5) Changelog‑Eintrag.

## Erfolgskriterien
- UI kann Historie listen und unmittelbar nach Einreichen den neuen Datensatz inklusive `analysis_json`/`feedback` anzeigen.
- Alle neuen Contract‑ und Sicherheitstests grün; keine Leaks (403/404/Cache‑Header konsistent).

Hinweise
- `student_sub` (API) ≙ `student_id` (DB) bleibt bestehen (Naming‑Refactor später separat).
- `GUSTAV_TRUST_PROXY` bleibt `true` hinter Reverse‑Proxy, sonst `false` (lokal ohne Proxy).
