# Plan: Learning Modular - File-Material-Previews serverseitig aufloesen

Status: umgesetzt (2026-03-14)
Datum: 2026-03-14

## Ergebnis
- `backend/web/main.py` enthaelt jetzt einen modularen Resolver fuer
  `module_id + material_id`, falls keine lineare Section-Map verfuegbar ist.
- Der Resolver prueft Kursmitgliedschaft, Unit-in-Course,
  `module_id -> section_id` und
  `modular_section_is_open_or_done_for_student(...)`, bevor eine Presign-URL
  erzeugt wird.
- Das Modulfragment cached lineare und modulare File-URLs getrennt pro Request.
- Verifiziert mit:
  - `backend/tests/test_learning_modular_unit_page_ui.py`

## Ziel
Modulare Lernmodule sollen fuer Datei-Materialien wieder Inline-Previews
rendern, auch wenn kein linearer Section-Release-Pfad verfuegbar ist.

## Scope
- SSR-Fragment `/learning/.../modules/{module_id}/fragment`
- kein neuer API-Endpunkt
- kein Schema-Umbau

## Sicherheitsregeln
- nur unter Student-Scoping aufloesen
- Modul muss zum Kurs und zur Unit gehoeren
- `modular_section_is_open_or_done_for_student(...)` bleibt verpflichtend
- `storage_key` bleibt serverintern

## Red-Green-Refactor
1. RED:
   - SSR-Test fuer modularen Fallback ohne Section-Mapping
   - SSR-Test, dass gelockte Module keine URL leaken
2. GREEN:
   - modularen Resolver fuer `module_id + material_id` einfuehren
   - per-Request Cache im Fragment beibehalten
3. REFACTOR:
   - linearen und modularen Resolver klar trennen

## Verifikation
- `backend/tests/test_learning_modular_unit_page_ui.py`
- ggf. neue gezielte SSR-Tests fuer das Modulfragment
