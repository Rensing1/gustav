# Authz and RLS Baseline

Status: Implemented in working tree
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_makefile_targets.py`, `make test-db-security`
CI status: Keine anbietergebundene CI erforderlich; `test-db-security` bleibt ein lokaler Hard-Gate-Baustein.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: nach Abschluss von PR 3

## Zweck
PR 3 macht Authz- und RLS-Regressionen als benannten Sicherheits-Gate-Satz sichtbar. `make test-db-security` setzt dafür `REQUIRE_DB_TESTS=1`, sodass DB-abhängige RLS-Tests in diesem Gate nicht mehr still skippen, wenn die lokale Supabase-Struktur fehlt.

## User Story
Als Produktverantwortlicher will ich, dass Schüler-, Lehrer- und Admin-Grenzen durch einen klaren Gate-Satz geschützt werden, damit spätere Refactors keine Daten anderer Lernender, Kurse oder Rollen freilegen.

## BDD-Szenarien
- Given ein Schüler ist authentifiziert, when er eine lehrerbezogene Detailroute für fremde Kursdaten aufruft, then erhält er `403`.
- Given ein Request nutzt nur ein Cookie für eine BFF-bearer-only Route, when er Session-Bootstrap ausführt, then erhält er `401`.
- Given ein ungültiger Bearer-Token wird für eine geschützte Route genutzt, when die Route aufgerufen wird, then erhält der Client `401`.
- Given ein Schüler ist Mitglied eines Kurses, when RLS-geschützte Learning-Tabellen gelesen werden, then sieht er nur freigegebene Zeilen seines Kurses.
- Given ein anderer Schüler oder keine Identity liest dieselben Tabellen, when RLS greift, then sind fremde Zeilen unsichtbar.
- Given ein Teacher arbeitet unter limited-role-RLS, when er fremde Kurse liest oder Memberships löscht, then dürfen nur owner-gebundene Pfade funktionieren.

## Teststrategie
- Rot: `backend/tests/test_makefile_targets.py` fordert, dass `make test-db-security` Authz- und RLS-Baseline-Tests enthält.
- Grün: `Makefile` erweitert `test-db-security` um vorhandene Authz-, Bearer-/BFF-, Teaching-Owner-, DB/RLS- und RLS-Migrationstests.
- Refactor: Security- und Milestone-Dokumente markieren PR 3 als im Arbeitsbaum umgesetzt und nennen Supabase/DB-Rollen als Voraussetzung.

## Umgesetzter Gate-Satz
`make test-db-security` enthält jetzt zusätzlich zu PR-1- und PR-2-Signalen diese Authz/RLS-Baseline:
- `backend/tests/test_api_auth_unauthenticated.py`
- `backend/tests/test_bearer_jwt_auth_api.py`
- `backend/tests/test_bff_authorization_session_api.py`
- `backend/tests/test_session_bootstrap_api.py`
- `backend/tests/test_teaching_live_detail_api.py::test_latest_detail_requires_owner_and_valid_ids`
- `backend/tests/test_teaching_live_detail_api.py::test_latest_detail_fallback_respects_unit_relation`
- `backend/tests/test_teaching_live_detail_relation_guard.py`
- `backend/tests/test_learning_student_rls_policies.py`
- `backend/tests/test_learning_rls_owners.py`
- `backend/tests/test_teaching_rls_policies_optional.py`
- `backend/tests/test_teaching_memberships_delete_rls_policy.py`
- `backend/tests/migration/test_course_memberships_rls_delete_policy.py`
- `backend/tests/migration/test_memberships_remove_definer_owner_binding.py`
- `backend/tests/migration/test_rls_exec_privileges.py`

## Evidenz
- Rot: `.venv/bin/pytest -q backend/tests/test_makefile_targets.py` schlug fehl, weil `test-db-security` die Authz/RLS-Dateien noch nicht enthielt.
- Rot: `.venv/bin/pytest -q backend/tests/test_makefile_targets.py` schlug erneut fehl, weil `test-db-security` noch kein hartes `REQUIRE_DB_TESTS=1` setzte.
- Grün: `.venv/bin/pytest -q backend/tests/test_makefile_targets.py` → 3 passed.
- Harness-Contract: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py backend/tests/test_harness_test_strategy_docs_contract.py backend/tests/test_makefile_targets.py` → 16 passed.
- CI-naher Harness: `make harness-minimum` → 68 passed und `docker compose config` OK.
- Gate mit laufender lokaler Supabase und provisionierten Rollen: `make test-db-security` → 85 passed, 2 warnings.

## Restrisiko
Die DB/RLS-Testdateien sind im Gate enthalten und werden mit `REQUIRE_DB_TESTS=1` hart erwartet. In der aktuellen Sandbox kann der Postgres-Port nicht direkt erreicht werden; die erfolgreiche Verifikation lief deshalb außerhalb der Sandbox gegen die gestartete lokale Supabase-Instanz. Das ist ein Tooling-/Sandbox-Risiko, kein Produkt-Sonderpfad.

Breite Teaching-Live-Detail-Integrationen bleiben außerhalb dieses harten Security-Gates, solange sie keine direkte Authz/RLS-Grenze prüfen. Das Gate verwendet deshalb gezielte pytest-Node-IDs für die relevanten Live-Detail-Fälle.
