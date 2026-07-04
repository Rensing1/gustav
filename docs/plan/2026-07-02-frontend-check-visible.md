# Make Frontend Check Visible

Status: Implemented in working tree
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_makefile_targets.py`, `make test-frontend-h5p`
CI status: `make harness-minimum` prüft die Makefile-Composition; `make verify` führt `make test-frontend-h5p` als Teil des vollständigen Verify-Pfads aus.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: nach Abschluss von PR 7

## Zweck
PR 7 macht Frontend-Typecheck und Frontend-Unit-Tests zu einem sichtbaren Bestandteil des vollständigen Verify-Pfads. Backend- und API-Refactors gelten dadurch nicht mehr als vollständig geprüft, wenn sie das SvelteKit-Frontend nicht mindestens typ- und testseitig passiert haben.

## User Story
Als Produktverantwortlicher will ich, dass `make verify` auch das SvelteKit-Frontend prüft, damit Backend- oder API-Änderungen nicht grün wirken, obwohl sie Frontend-Verträge brechen.

## BDD-Szenarien
- Given `make verify` läuft, when die vollständige lokale Verifikation startet, then wird `make test-frontend-h5p` ausgeführt.
- Given das Frontend einen TypeScript- oder Svelte-Fehler enthält, when `make test-frontend-h5p` läuft, then schlägt `npm run check` fehl.
- Given Frontend-Unit-Tests fehlschlagen, when `make test-frontend-h5p` läuft, then schlägt `npm test` fehl.
- Given die lokale Umgebung `localhost` nicht per DNS auflösen kann, when Vitest startet, then nutzt die Testkonfiguration `127.0.0.1` als numerischen Loopback-Host.

## Teststrategie
- Rot: `backend/tests/test_makefile_targets.py::test_verify_runs_frontend_h5p_profile` forderte, dass `verify` das kombinierte Profil `test-frontend-h5p` statt nur `test-h5p` nutzt.
- Rot: `backend/tests/test_makefile_targets.py::test_frontend_vitest_uses_numeric_loopback_host` forderte, dass Vitest nicht von `localhost`-DNS abhängt.
- Grün: `Makefile` ruft in `verify` `make test-frontend-h5p` auf.
- Grün: `frontend/vitest.config.ts` setzt den Vite-Testserver auf `127.0.0.1`.

## Evidenz
- Rot: `.venv/bin/pytest -q backend/tests/test_makefile_targets.py::test_verify_runs_frontend_h5p_profile` schlug fehl, weil `verify` nur `test-h5p` aufrief.
- Rot: `cd frontend && npm test` schlug vor der Vitest-Konfiguration beim Start mit `getaddrinfo EAI_AGAIN localhost` fehl.
- Rot: `.venv/bin/pytest -q backend/tests/test_makefile_targets.py::test_frontend_vitest_uses_numeric_loopback_host` schlug fehl, weil `frontend/vitest.config.ts` keinen numerischen Loopback-Host setzte.
- Grün: `cd frontend && npm run check` → `svelte-check found 0 errors and 0 warnings`.
- Grün: `cd frontend && npm test` → 73 test files passed, 282 tests passed.
- Grün: `make test-frontend-h5p` → Frontend-Typecheck grün, 282 Frontend-Tests grün, 7 H5P-Tests grün.

## Restrisiko
PR 7 macht Frontend-Typecheck und Frontend-Unit-Tests sichtbar und hart im vollständigen Verify-Pfad. Browser-E2E, API-Live-Diff und visuelle Regressionen bleiben separate spätere Gates.
