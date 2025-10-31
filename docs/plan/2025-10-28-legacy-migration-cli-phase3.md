# Plan: Legacy Migration CLI – Phase 3 (Units & Sections)

## Ziel
Das Migration-CLI überträgt jetzt Lerneinheiten (Units) und deren Abschnitte (Sections) aus dem Legacy-Staging nach Alpha2. Es gelten die Audit/Idempotenz-Regeln aus den Vorphasen.

## Scope
- `staging.learning_units` → `public.units` (description → summary, creator_id → author_id via `legacy_user_map`, IDs erhalten).
- `staging.unit_sections` → `public.unit_sections` (order_in_unit → position, IDs erhalten).
- Audit-Logging für `legacy_unit` und `legacy_unit_section` (ok/skip/conflict/error).
- Dry-Run-Unterstützung ohne DB-Writes.

Nicht enthalten:
- Course-Module-Verknüpfungen, Releases, Materials, Tasks.

## Risiken & Annahmen
- Für jede Unit muss `creator_id` in `legacy_user_map` aufgelöst werden.
- Sections setzen eine existierende Unit voraus (importiert oder bereits vorhanden).
- Positions-Constraints in `unit_sections` (unique unit_id,position) sind deferrable, wir nutzen einfache Inserts ohne Reorders.

## TDD-Schritte
1. Neuer Test `backend/tests/migration/test_legacy_migration_units_sections.py` seeden `staging.learning_units`/`staging.unit_sections`, pflegen `legacy_user_map` und prüfen Inserts + Audit.
2. Minimaler Code im CLI zur Ausführung der Phase, bis der Test grün ist.
3. Review: Kommentare/Dokumentation anpassen.

## Done Criteria
- Test zunächst rot, danach grün.
- CLI protokolliert Audits konsistent und ist idempotent.
