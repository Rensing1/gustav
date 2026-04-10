# Modularer Task-Kontext im Visual-Feedback-Worker

## Ausgangsproblem
- Im Lernraum erschien bei Datei-Uploads für `native`-Aufgaben die Meldung: `Die Rückmeldung konnte nicht erstellt werden.`
- Die Worker-Logs zeigten dafür:
  - erfolgreicher Upload und erfolgreicher Dateizugriff
  - danach `invalid_feedback_format`
  - gleichzeitig `has_instruction=False` und `has_teacher_context=False`

## Root Cause
- Der Submission-Job verlor bei modularen Aufgaben den Aufgabenkontext an zwei Stellen:
  1. `DBLearningRepo.create_submission(...)` schrieb `instruction_md` über `get_released_tasks_for_student(...)` in den Queue-Payload. Dieser Lookup lieferte für den konkreten modularen Task hier keine Zeile.
  2. Der Worker-Fallback las `unit_tasks` nur mit `app.current_sub`, aber ohne `app.current_course_id`. Unter modularer Sichtbarkeit reichte dieser RLS-Kontext nicht aus.

## Ziel
- Visuelle Native-Uploads sollen im Worker denselben Task-Kontext erhalten wie Text-Submissions:
  - `instruction_md` im Queue-Payload
  - `teacher_context_md` nur worker-intern nachgeladen
- Keine Änderung an der Produktentscheidung:
  - `native + file/image` bleibt `visual_direct`
  - kein OCR-Schritt

## Geplanter Fix
- `DBLearningRepo.create_submission(...)`
  - `instruction_md` direkt aus `public.unit_tasks` per `task_id` lesen
  - dabei den bereits gesetzten student/course-RLS-Kontext nutzen
  - `teacher_context_md` weiterhin **nicht** in den Payload schreiben
- `process_learning_submission_jobs.py`
  - vor `_fetch_task_context(...)` zusätzlich `app.current_course_id` setzen
  - Fallback für `instruction_md` und `teacher_context_md` damit im modularen Kontext stabilisieren

## Teststrategie
- Red:
  - modularer Submission-Job enthält `instruction_md`, aber kein `teacher_context_md`
  - Worker reicht bei modularem visuellen Upload `instruction_md` und `teacher_context_md` an `analyze_visual(...)` weiter
- Green:
  - Repo- und Worker-Fix minimal umsetzen
- Refactor:
  - kurze Why-Kommentare an den beiden Kontext-Übergängen

## Verifikation
```bash
./.venv/bin/pytest -q backend/tests/test_learning_worker_task_context.py backend/tests/test_learning_worker_visual_dspy_pipeline.py
```
