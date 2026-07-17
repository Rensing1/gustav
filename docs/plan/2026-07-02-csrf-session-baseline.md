# CSRF and Session Baseline

Status: Implemented in working tree
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_makefile_targets.py`, `make test-db-security`
CI status: Keine anbietergebundene CI erforderlich; `test-db-security` wird als lokaler Hard-Gate-Baustein vorbereitet.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: nach Abschluss von PR 2

## Zweck
PR 2 macht die bestehende CSRF- und Session-Sicherheit als harten, benannten Gate-Satz sichtbar. Der Fokus liegt nicht auf neuer Produktfunktion, sondern auf Regressionen, die vor späteren Refactors zuverlässig laufen müssen.

## User Story
Als Produktverantwortlicher will ich, dass Browser-Writes ohne same-origin `Origin`/`Referer` und unsichere Session-Cookies durch einen klaren Gate-Satz auffallen, damit spätere Refactors keine CSRF- oder Cookie-Regressionen einführen.

## BDD-Szenarien
- Given ein authentifizierter Browser-Client sendet eine Learning-Submission ohne `Origin` und ohne `Referer`, when er die Submission abschickt, then antwortet die API mit `403` und `detail=csrf_violation`.
- Given ein authentifizierter Browser-Client sendet einen Teaching-Write ohne `Origin` und ohne `Referer`, when der Write ausgeführt wird, then antwortet die API mit `403` und `detail=csrf_violation`.
- Given ein authentifizierter Browser-Client sendet einen same-origin Write, when der fachliche Request gültig ist, then blockiert CSRF nicht.
- Given ein Session-Cookie gesetzt oder ersetzt wird, when die Antwort ausgeliefert wird, then ist das Cookie host-only, `HttpOnly`, `Secure` und `SameSite=lax`.

## Teststrategie
- Rot: `backend/tests/test_makefile_targets.py` fordert, dass `make test-db-security` die CSRF- und Session-Baseline-Tests enthält.
- Grün: `Makefile` erweitert `test-db-security` um vorhandene CSRF-/Cookie-Tests und eine direkte Session-Sync-Cookie-Flag-Regression.
- Refactor: `docs/harness/SECURITY_BASELINE.md`, `docs/harness/QUALITY_GATES.md` und der übergreifende Harness-Plan werden auf PR-2-Status aktualisiert.

## Evidenz
Ausgeführte Checks:
- `.venv/bin/pytest -q backend/tests/test_makefile_targets.py`: 2 passed.
- `.venv/bin/pytest -q backend/tests/test_session_sync_api.py`: 3 passed.
- `make test-db-security`: 62 passed, 2 skipped.

Umsetzung:
- `make test-db-security` enthält jetzt die vorhandenen CSRF-Baselines für Learning-Submissions, Teaching-Writes, Trust-Proxy-Verhalten und redigiertes CSRF-Diagnoselogging.
- `backend/tests/test_session_sync_api.py` prüft direkt, dass `gustav_session` bei BFF-Session-Sync host-only, `HttpOnly`, `Secure` und `SameSite=lax` bleibt.
