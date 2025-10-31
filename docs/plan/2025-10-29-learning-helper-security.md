# Plan — Learning Helper Security ohne SECURITY DEFINER

## Kontext
- Migration `20251027114908_learning_course_units_helper.sql` setzt aktuell `SECURITY DEFINER` und versucht, den Owner (`gustav_limited`) zu überschreiben.
- `supabase db reset` wird mit der reservierten Rolle `supabase_admin` ausgeführt. Diese Rolle darf nicht modifiziert werden (`SQLSTATE 42501`), daher kann der Owner-Wechsel nicht erfolgen.
- Tests (`backend/tests/test_learning_rls_owners.py`) erwarten, dass Learning-Helper `gustav_limited` gehören. Das führt zu Skip/Workarounds.

## Zielbild
- Helper funktionieren out-of-the-box mit Supabase-Migrationen, ohne Superuser-Hacks.
- Sicherheitsversprechen bleibt bestehen: RLS verhindert unberechtigte Datenzugriffe, da Anwendungen ausschließlich mit `gustav_limited` arbeiten.
- Tests erkennen versehentliche `SECURITY DEFINER`-Einsätze und BYPASSRLS-Risiken.

## Maßnahmen
1. Migration `20251027114908_learning_course_units_helper.sql` anpassen:
   - `SECURITY DEFINER` entfernen (implicit `SECURITY INVOKER`), Owner-Änderung löschen.
   - Kommentar ergänzen: „Works with RLS via gustav_limited invoker“.
2. Tests aktualisieren:
   - `backend/tests/test_learning_rls_owners.py`: Statt Owner-Verifikation prüfen, dass Learning-Helper nicht als SECURITY DEFINER (`prosecdef = true`) angelegt sind.
3. Dokumentation:
   - `docs/CHANGELOG.md`: Hinweis auf geänderte Sicherheitsstrategie.
   - `docs/references/learning.md`: Abschnitt „RLS & DSN“ um Formulierung ergänzen („Helper rely on RLS; no SECURITY DEFINER required“).
4. Verifikation:
 - `supabase db reset`
 - `.venv/bin/pytest backend/tests/test_learning_rls_owners.py -q`

## Offene Fragen
- Müssen weitere Helper (aus anderen Kontexten) ebenfalls auf SECURITY INVOKER umgestellt werden?
- Ist zusätzliche Laufzeitprüfung sinnvoll (z. B. `current_setting('row_security')`)?

## Umsetzung (2025-10-29)
- Migration `20251027114908_learning_course_units_helper.sql` aktualisiert (SECURITY INVOKER, kein Owner-Switch).
- Neue Migration `20251029124035_learning_helpers_security_invoker.sql` setzt sämtliche Learning-Helper
  (`next_attempt_nr`, `check_task_visible_to_student`, `get_released_*`, `get_task_metadata_for_student`) auf
  SECURITY INVOKER und lässt Grants bestehen.
- Neue Migration `20251029124213_learning_student_rls_policies.sql` ergänzt helper Funktionen
  (`student_is_course_member`, `student_can_access_unit`, `student_can_access_course_module`,
  `student_can_access_section`) und darauf aufbauende SELECT-Policies für Schüler auf
  `course_modules`, `units`, `unit_sections`, `module_section_releases`, `unit_materials`, `unit_tasks`.
- Tests: `backend/tests/test_learning_rls_owners.py` prüft weiterhin `SECURITY DEFINER` → `skip` in Sandbox mangels DB,
  erwartet jedoch grün mit laufender Supabase-Instanz. Learning API/UI-Tests sollen wieder 200 liefern.
- Dokumentation (`docs/CHANGELOG.md`, `docs/references/learning.md`) aktualisiert: Helper nutzen RLS, Policies beschrieben.

## Nacharbeiten
- Sicherstellen, dass andere SECURITY DEFINER Helper (außerhalb Learning) überprüft/angepasst werden.
- Optional: zusätzliche Integrationstests für die neuen Policies hinzufügen, sobald DB im Testlauf verfügbar ist.
