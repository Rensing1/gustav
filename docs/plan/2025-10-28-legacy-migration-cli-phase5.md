# Plan: Legacy Migration CLI – Phase 5 (Materials & Tasks)

## Ziel
Das Migration-CLI importiert Abschnitts-Materialien und Aufgaben aus dem Legacy-Staging in Alpha2 und protokolliert jeden Schritt auditierbar.

## Scope
- `staging.materials_json` → `public.unit_materials`
  - Markdown: `kind='markdown'`, `body_md`, `title`, `position`.
  - Dateien: Nur mit vollständiger Metadatenlage (`storage_key`, `size_bytes>0`, `sha256` 64-hex, `mime_type` in Whitelist) als `kind='file'`; sonst Fallback auf Markdown-Link ("Datei nicht verfügbar: …").
  - `section_id` → `unit_id` via Lookup aus `public.unit_sections`.
- `staging.tasks_base` + `staging.tasks_regular` → `public.unit_tasks`
  - `instruction_md`, `hints_md`, `max_attempts`, `order_in_section` → `position`.
  - `criteria`: aus JSON in Textarray, trimmen, leere entfernen, deduplizieren, max 10.
  - `section_id` → `unit_id` via Lookup.
- Audit-Logging je Entität (`legacy_material`, `legacy_task`) mit Status `ok/skip/conflict/error`.
- Dry-Run-Unterstützung: keine Writes, nur Audit.

## Risiken & Annahmen
- Materials/Tasks erfordern existierende `unit_sections` (und damit `units`).
- Datei-Metadaten im Legacy können unvollständig sein → Fallback-Markdown vermeiden Constraint-Verletzungen.

## TDD-Schritte
1. Neuer Test `backend/tests/migration/test_legacy_migration_materials_tasks.py`: seeded Units/Sections, `staging.materials_json` (Markdown + unvollständige Datei → Fallback) und Tasks (Base+Regular). Erwartet Inserts in `unit_materials`/`unit_tasks` mit Audit.
2. CLI minimal erweitern (Lade-/Apply-Funktionen), bis Test grün ist.
3. Review & Kommentare ergänzen.

## Done Criteria
- Test zunächst rot, danach grün; Idempotenz gewährleistet (Upsert/Do-Nothing).
