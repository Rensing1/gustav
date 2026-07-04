# Legacy HTML/HTMX Exit Wave 1

Status: Implemented as first PR 16 slice in working tree
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_learning_legacy_entry_retired.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_learning_legacy_unit_routes_retired.py backend/tests/test_teaching_live_student_overview_ssr.py`, `make test-route-map`, `make harness-minimum`
CI status: `make harness-minimum` prüft den Legacy-Exit-Contract; `make verify` schützt zusätzlich Route Map, API-Contract und Docker-Smoke.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/plan/2026-07-02-route-surface-map.md`, `docs/plan/2026-07-02-app-composition-entrypoint.md`
Review cadence: nach jeder Legacy-Route-Entfernung

## Zweck
PR 16 entfernt die ersten bereits retired FastAPI-HTML/HTMX-Einstiegspfade aus der registrierten Routenoberfläche. Die direkte Backend-Antwort bleibt absichtlich erhalten, aber zentral über die Retirement-Schicht statt über eigene lokale Handler.

## User Story
Als Produktverantwortlicher will ich, dass alte Produkt-Einstiegspunkte nicht mehr als aktive FastAPI-Routen erscheinen, damit IDEs, Route Map und Entwickler nicht den Eindruck bekommen, diese HTML/HTMX-Flows seien weiterhin produktive Oberfläche.

## BDD-Szenarien
- Given ein Schüler ist angemeldet, when er `/learning` direkt im Backend öffnet, then erhält er weiter eine 410-Retirement-Antwort mit `Cache-Control: private, no-store`.
- Given eine Lehrkraft ist angemeldet, when sie `/learning` direkt im Backend öffnet, then wird sie weiter auf `/` umgeleitet.
- Given eine Lehrkraft ist angemeldet, when sie `/courses` oder `/units` direkt im Backend öffnet, then erhält sie weiter eine 410-Retirement-Antwort.
- Given ein Schüler ist angemeldet, when er `/courses` direkt im Backend öffnet, then wird er weiter auf `/` umgeleitet.
- Given eine Lehrkraft ist angemeldet, when sie `/teaching/live`, `/teaching/live/open` oder `/teaching/live/units` direkt im Backend öffnet, then erhält sie weiter eine 410-Retirement-Antwort.
- Given ein Schüler ist angemeldet, when er `/teaching/live` direkt im Backend öffnet, then wird er weiter auf `/` umgeleitet.
- Given eine Lehrkraft ist angemeldet, when sie entfernte Units-Einstiegs- und Phasenpfade direkt im Backend öffnet, then erhält sie weiter eine 410-Retirement-Antwort.
- Given eine Lehrkraft ist angemeldet, when sie entfernte Units-Modul- oder Modular-Editor-Pfade direkt im Backend öffnet, then erhält sie weiter eine 410-Retirement-Antwort.
- Given eine Lehrkraft ist angemeldet, when sie entfernte Units-Section-, Material- oder Task-Pfade direkt im Backend öffnet, then erhält sie weiter eine 410-Retirement-Antwort.
- Given ein Schüler ist angemeldet, when er einen entfernten Units-Lehrkraftpfad direkt im Backend öffnet, then wird er weiter auf `/` umgeleitet.
- Given ein Schüler ist angemeldet, when er entfernte `/learning/courses*`-HTML-/HTMX-Pfade direkt im Backend öffnet, then erhält er weiter eine 410-Retirement-Antwort ohne inhaltliche Veränderung seiner Einreichungen.
- Given eine Lehrkraft ist angemeldet, when sie entfernte `/learning/courses*`-HTML-/HTMX-Pfade direkt im Backend öffnet, then wird sie weiter auf `/` umgeleitet.
- Given die FastAPI-Routenoberfläche inspiziert wird, when die ausgewählten Legacy-Einstiegspfade geprüft werden, then sind sie nicht mehr als `APIRoute` registriert.

## Teststrategie
- Rot: Ein neuer Contract fordert, dass die ausgewählten retired Einstiegspfade nicht mehr in der Runtime-Route-Liste stehen, während direkte Requests weiterhin intentional beantwortet werden.
- Grün: `_retired_legacy_product_response` übernimmt die ausgewählten Pfade zentral; die lokalen Handler werden entfernt.
- Refactor: Route Map und Harness-Gates werden aktualisiert, damit die kleinere registrierte Oberfläche überprüfbar bleibt.

## Evidenz
- Rot: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py` → zunächst rot, weil `/learning`, `/teaching/live`, `/teaching/live/open` und `/teaching/live/units` noch als `APIRoute` registriert waren; `/teaching/live/units` ohne Query fiel außerdem noch durch Handler-Validation statt durch die Retirement-Schicht.
- Grün: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_learning_legacy_entry_retired.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_learning_legacy_unit_routes_retired.py backend/tests/test_teaching_live_student_overview_ssr.py` → 13 passed.
- Grün: `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py backend/tests/test_legacy_html_exit_wave1_contract.py` → 8 passed.
- Grün: `make test-route-map` → `route-map-inventory-ok`.
- Grün: `make harness-minimum` → 110 passed; Docker-Compose-Konfiguration valide.
- Rot: Der erweiterte Contract wurde für `/courses` und `/units` erneut rot, weil beide Top-Level-Lehrkraft-Einstiege noch als `APIRoute` registriert waren.
- Grün: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 12 passed.
- Grün: `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 17 passed.
- Grün: `make test-route-map` → `route-map-inventory-ok`.
- Grün: `make harness-minimum` → 111 passed; Docker-Compose-Konfiguration valide.
- Rot: Der erweiterte Contract wurde für `/courses/{course_id}/edit`, `/courses/{course_id}/delete` und `/courses/{course_id}/members/search` rot, weil diese tieferen Courses-Legacy-Handler noch registriert waren.
- Grün: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 13 passed.
- Grün: `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 18 passed.
- Grün: `make test-route-map` → `route-map-inventory-ok`.
- Grün: `make harness-minimum` → 112 passed; Docker-Compose-Konfiguration valide.
- Rot: Der erweiterte Contract wurde für `POST /courses`, `/courses/{course_id}/modules*` und `/courses/{course_id}/members*` rot, weil diese Courses-Legacy-Handler noch registriert waren.
- Grün: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 14 passed.
- Grün: `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 19 passed.
- Grün: `make test-route-map` → `route-map-inventory-ok`.
- Grün: `make harness-minimum` → 113 passed; Docker-Compose-Konfiguration valide.
- Rot: Der erweiterte Contract wurde für `POST /units`, `/units/{unit_id}`, `/units/{unit_id}/edit`, `/units/{unit_id}/modules` und `/units/{unit_id}/phases*` rot, weil diese Units-Legacy-Handler noch registriert waren; direkte Requests wurden bereits durch die zentrale Retirement-Schicht intentional beantwortet.
- Grün: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 15 passed.
- Grün: `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 20 passed.
- Grün: `make test-route-map` → `route-map-inventory-ok`; die frühere Diagnose `Teaching repo unavailable ... using in-memory fallback` ist behoben, weil das Teaching-Repository beim reinen Route-Inventory nicht mehr importzeitlich initialisiert wird.
- Grün: `make harness-minimum` → 114 passed; Docker-Compose-Konfiguration valide.
- Rot: Der erweiterte Contract wurde für `/units/{unit_id}/modules/{module_id}*` und `/units/{unit_id}/modular-editor*` rot, weil diese Modul-/Modular-Editor-Legacy-Handler noch registriert waren; direkte Requests wurden bereits durch die zentrale Retirement-Schicht intentional beantwortet.
- Grün: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 16 passed.
- Grün: `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 21 passed.
- Grün: `make test-route-map` → `route-map-inventory-ok` ohne stderr-Warnung.
- Grün: `make harness-minimum` → 115 passed; Docker-Compose-Konfiguration valide.
- Rot: Der erweiterte Contract wurde für `/units/{unit_id}/sections*`, Material- und Task-Legacy-Handler rot, weil diese Units-Section-/Material-/Task-Handler noch registriert waren; direkte Requests wurden bereits durch die zentrale Retirement-Schicht intentional beantwortet.
- Grün: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 17 passed.
- Grün: `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 22 passed.
- Grün: `make test-route-map` → `route-map-inventory-ok` ohne stderr-Warnung; die Route Map enthält keine `/units*`-Legacy-HTML-Routen mehr.
- Grün: `make harness-minimum` → 116 passed; Docker-Compose-Konfiguration valide.
- Rot: Der erweiterte Contract wurde für `/learning/courses/{course_id}`, `/learning/courses/{course_id}/units/{unit_id}`, `/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}/fragment`, `/learning/courses/{course_id}/tasks/{task_id}/submit` und die History-Pfade rot, weil diese Learning-Legacy-Handler noch registriert waren; direkte Requests wurden bereits durch die zentrale Retirement-Schicht intentional beantwortet.
- Grün: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_learning_legacy_entry_retired.py backend/tests/test_learning_legacy_unit_routes_retired.py` → 16 passed.
- Grün: `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_learning_legacy_entry_retired.py backend/tests/test_learning_legacy_unit_routes_retired.py backend/tests/test_teaching_legacy_routes_retired.py backend/tests/test_navigation_roles_ui.py` → 29 passed.
- Grün: `make test-route-map` → `route-map-inventory-ok` ohne stderr-Warnung; die Route Map enthält keine `/learning/courses*`-Legacy-HTML-/HTMX-Routen mehr.
- Grün: `make harness-minimum` → 117 passed; Docker-Compose-Konfiguration valide.
- Rot: Der erweiterte Contract wurde für die tiefen Teaching-Live-GET-Pfade (`/teaching/courses/{course_id}/students/{student_sub}/live`, `/teaching/courses/{course_id}/units/{unit_id}/live*`) rot, weil diese Routen noch registriert waren; direkte Requests wurden bereits durch lokale Handler intentional retired beantwortet.
- Grün: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py::test_first_legacy_exit_wave_routes_are_not_registered_as_fastapi_handlers backend/tests/test_legacy_html_exit_wave1_contract.py::test_removed_deep_teaching_live_entries_return_retirement_response` → 2 passed.
- Rot: Der erweiterte Contract wurde für `POST /teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility` rot, weil der alte HTMX-Visibility-Helfer noch registriert war; direkte Requests wurden bereits intentional retired beantwortet.
- Grün: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py::test_first_legacy_exit_wave_routes_are_not_registered_as_fastapi_handlers backend/tests/test_teaching_live_section_release_ssr.py::test_live_section_release_helpers_are_retired` → 3 passed.
- Grün: `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_live_section_release_ssr.py backend/tests/test_teaching_live_unit_ui_ssr.py backend/tests/test_teaching_live_detail_ssr.py backend/tests/test_teaching_live_student_overview_ssr.py backend/tests/test_teaching_live_h5p_matrix_cell_rendering.py` → 26 passed.
- Grün: `make test-route-map` → `route-map-inventory-ok` ohne stderr-Warnung; die Route Map enthält keine tiefen Teaching-Live-HTML-/HTMX-Routen und keinen alten Teaching-Live-POST-Visibility-Helfer mehr.
- Grün: `make harness-minimum` → 123 passed; Docker-Compose-Konfiguration valide.
- Vollständige Verifikation: `make verify` → DB-Preflight, Import-/OpenAPI-/Architektur-/Route-Map-Gates, Docker-Image-Smoke, Backend-Pytest (`1778 passed, 35 skipped`), Frontend-Check (`0 errors and 0 warnings`), Frontend-Vitest (`73 passed`) und H5P-Node-Tests (`21 pass`) erfolgreich.
- Rot: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py::test_removed_teacher_unit_entries_leave_no_ssr_helpers_in_main` → 1 failed, weil `backend/web/main.py` nach der Routenentfernung noch retired Teacher-Unit-/Course-SSR-Helfer enthielt.
- Grün: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py::test_removed_teacher_unit_entries_leave_no_ssr_helpers_in_main backend/tests/test_app_composition_contract.py` → 6 passed.
- Grün: `.venv/bin/pytest -q backend/tests/test_legacy_html_exit_wave1_contract.py backend/tests/test_teaching_live_h5p_matrix_cell_rendering.py backend/tests/test_csrf_tokens_contract.py backend/tests/test_app_composition_contract.py` → 24 passed.
- Grün und warning-clean: `make test-route-map` → `route-map-inventory-ok`; `backend/web/main.py` enthält keine retired Teacher-Unit-/Course-SSR-Renderer und keine zugehörigen internen API-Fetch-Helfer mehr.
- Grün: `.venv/bin/pytest -q backend/tests/test_app_composition_contract.py backend/tests/test_ssr_helpers_contract.py backend/tests/test_learning_ui_makecode_evidence_rendering.py backend/tests/test_learning_ui_scratch_evidence_rendering.py backend/tests/test_learning_ui_feedback_failure_messages.py` → 17 passed; Learning-Submission-/History-Renderer liegen jetzt in `backend/web/submission_history_rendering.py` statt in `backend/web/main.py`.
- Grün und warning-clean: `make test-route-map` → `route-map-inventory-ok`; der aktuell reproduzierte Route-Map-Lauf erzeugt keine stderr-Warnung.

## Offene Arbeit
- Dieser Schnitt entfernt noch nicht die verbleibenden Root-/About-HTML-Seiten. Diese sind in der Route Map weiterhin als aktive Legacy-UI markiert und brauchen eine eigene Produktentscheidung.
- Warnungen in Harness-Gates werden nicht als irrelevant behandelt. `make test-route-map`, `make harness-minimum` und der letzte vollständige `make verify` sind aktuell warning-clean; neu auftretende stderr-Ausgaben sollen vor dem nächsten größeren Aufräumschnitt behoben oder bewusst als Finding dokumentiert werden.
