# Plan: Legacy Migration CLI – Phase 4 (Course Modules & Section Releases)

## Ziel
Das Migration-CLI überträgt Kursmodule (Zuordnung Kurs↔Unit mit Position) und Abschnittsfreigaben (Releases) aus dem Legacy-Staging nach Alpha2.

## Scope
- `staging.course_unit_assignments` → `public.course_modules`
  - Position je Kurs von 1..n; bei Legacy-Positionen übernehmen, sonst stabil sortieren und nummerieren.
  - Idempotenz: `(course_id, unit_id)` unique – Upsert/Do-Nothing.
- `staging.section_releases` → `public.module_section_releases`
  - Nur sichtbare (visible=true) Datensätze.
  - `released_at` übernehmen; `released_by` setzen (Owner des Kurses, sonst `'system'`).
  - Lookup des `course_module_id` über `(course_id, unit_id)`.
- Audit-Logging je Entität (`legacy_course_module`, `legacy_section_release`) mit Status `ok/skip/conflict/error`.
- Dry-Run-Unterstützung: keine Writes, nur Audit-Einträge.

## Risiken & Annahmen
- Benötigt bereits importierte Kurse und Units; andernfalls `skip`/`conflict` mit Audit.
- `released_by` ist NOT NULL; Fallback auf `'system'` wenn nicht ermittelbar (Regel im Runbook).
- Positions-Constraint in `course_modules` (unique per Kurs) muss bei Write korrekt sein; wir nutzen Upsert ohne Reorders.

## TDD-Schritte
1. Neuer Test `backend/tests/migration/test_legacy_migration_modules_releases.py` seeded `staging.course_unit_assignments` und `staging.section_releases`, plus vorhandene Kurse/Units; prüft Inserts in `public.course_modules` und `public.module_section_releases` sowie Audit.
2. CLI minimal erweitern, bis Test grün ist.
3. Review & Dokumentation.

## Done Criteria
- Test zunächst rot, danach grün.
- CLI protokolliert Audits konsistent und ist idempotent.
