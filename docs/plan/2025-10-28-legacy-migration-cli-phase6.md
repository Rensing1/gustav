# Plan: Legacy Migration CLI – Phase 6 (Submissions)

## Ziel
Submissions (Abgaben) aus Legacy-Staging werden in `public.learning_submissions` importiert, inklusive deterministischer Kursableitung und Versuchszähler pro `(course_id, task_id, student_sub)`.

## Scope
- `staging.submissions` → `public.learning_submissions`
  - Kursableitung: über `unit_tasks.section_id` → `unit_id`, Kandidatenkurse sind die Kurse, in denen der Schüler Mitglied ist und deren `course_modules` die `unit_id` enthalten, und die eine Release für den Abschnitt haben (`module_section_releases.visible=true`). Bei genau einem Kandidaten: importieren, sonst Audit `ambiguous_course`/`missing_course`.
  - Versuchszähler: fortlaufend je `(course_id, task_id, student_sub)` durch Sortierung nach `created_at` (bestehende DB-Werte berücksichtigen, idempotent durch Unique-Constraint).
  - Kinds: `text` mit `text_body`, `image` nur mit vollständiger Metadatenlage (`storage_key`, `mime_type` in ('image/jpeg','image/png'), `size_bytes>0`, `sha256` 64-hex). Sonst `skip` mit Grund `invalid_payload`.
  - Dry-Run: keine Writes, aber vollständige Audit-Erzeugung.

## Risiken & Annahmen
- Tasks/Units/Course Modules/Releases sind importiert/verfügbar, Mitgliedschaften vorhanden.
- Inkonsistenzen im Legacy (fehlende Freigabe, Mehrdeutigkeiten) werden auditiert und nicht importiert.

## TDD-Schritte
1. Neuer Test `backend/tests/migration/test_legacy_migration_submissions.py` seeded Kurse/Units/Sections, Tasks, Memberships, Course-Modules/Release, und `staging.submissions` (Text + Bild + Ambiguität). Erwartung: 2 Imports, 1 Skip mit Audit `ambiguous_course`, korrekte `attempt_nr` (1..n) nach `created_at`.
2. CLI minimal erweitern: Lade-/Apply-Funktionen, Kursableitung, Validierung, Attemptzählung, idempotenter Insert.
3. Review: Kommentare, Sicherheit (Service-Role), Idempotenz.

## Done Criteria
- Test läuft rot → grün, Idempotenz stimmt, Audit-Einträge decken Kantenfälle ab.
