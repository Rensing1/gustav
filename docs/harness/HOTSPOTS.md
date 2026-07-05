# Hotspots

Status: Draft
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich während des Harness-Refactors

## Zweck
Dieses Dokument markiert Dateien, die im Refactor nicht weiter anwachsen sollen, ohne dass bewusst Debt dokumentiert wird.

## Initiale Hotspots
| Datei | Baseline LOC | Bereich | Split-Ziel |
| --- | ---: | --- | --- |
| `backend/web/main.py` | 98 | App Composition | nicht wieder mit Route-, Auth- oder Rendering-Logik füllen |
| `backend/web/routes/teaching.py` | 6146 | Teaching Web Adapter | weitere Use-Case-, Guard-, Read-Model- und Serializer-Grenzen extrahieren |
| `backend/web/routes/learning.py` | 2884 | Learning Web Adapter | Upload-/Storage-, Submission- und Material-Read-Grenzen weiter entflechten |
| `backend/web/routes/app.py` | 2499 | Browser-BFF und App-Routen | Profil-, Session- und View-Helfer klein halten |
| `backend/learning/repo_db.py` | 2425 | Learning Repository | Read Models und Query-Gruppen schrittweise isolieren |
| `backend/teaching/repo_db.py` | 4854 | Teaching Repository | Live-/Dashboard-Read-Models und Schreibfälle trennen |
| `h5p-service/server.mjs` | 1633 | H5P Sidecar | Route-Handler weiter splitten |
| `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte` | 1644 | Learning Workspace | weitere Loader- und View-Komponenten trennen |
| `frontend/src/routes/teaching/units/[unitId]/+page.svelte` | 1210 | Teaching Workspace | Graph-State, Command-Bar und Node-Editor-Komposition trennen |
| `frontend/src/lib/styles/app.css` | 5617 | App CSS | Komponentennahe Styles und Tokens auslagern |
| `frontend/src/lib/styles/design-system.css` | 1903 | Design System CSS | Tokens, Layout-Utilities und Komponentenregeln schärfer trennen |

## PR20 Fortschritt
- `h5p-service/lib/finished_submission_context.mjs` übernimmt seit PR20 die Origin-/Referer-Auswertung und Idempotency-Key-Erzeugung für H5P-Finished-Data-Forwarding.
- `h5p-service/test/finished_submission_context.test.mjs` schützt diese reine Forwarding-Kontextlogik mit Node-Contracts.
- `h5p-service/lib/review_tokens.mjs` übernimmt seit PR20 die signierte Review-Token-Prüfung; `h5p-service/test/review_tokens.test.mjs` schützt gültige, abgelaufene, unvollständige und manipulierte Token.
- `h5p-service/lib/security_headers.mjs` übernimmt seit PR20 die H5P-CSP- und Security-Header-Policy; `h5p-service/test/security_headers.test.mjs` schützt Default-CSP, Debug-CSP und Header-Overrides.
- `h5p-service/lib/model_helpers.mjs` übernimmt seit PR20 die reinen H5P-Response-Helfer für Theme-Styles und Embed-Types; `h5p-service/test/model_helpers.test.mjs` schützt Reihenfolge, Deduplikation und Fallbacks.
- `h5p-service/lib/cookies.mjs` übernimmt seit PR20 auch das Cookie-Parsing für H5P-Session- und BFF-Session-Erkennung; `h5p-service/test/cookies.test.mjs` schützt Decoding, malformed Fallbacks und leere Cookie-Teile.
- `h5p-service/lib/response_helpers.mjs` übernimmt seit PR20 die zentralen JSON-/HTML-Sendehelfer mit Security- und Cache-Headern; `h5p-service/test/response_helpers.test.mjs` schützt Defaults und explizite Header-Overrides.
- `h5p-service/lib/storage_helpers.mjs` übernimmt seit PR20 H5P-Storage-Verzeichnisaufbau, Storage-Readiness-Probe und Header-Dateinamen-Sanitizing; `h5p-service/test/storage_helpers.test.mjs` schützt Layout, Fehlerpfad und Header-Sicherheit.
- `h5p-service/lib/auth_forwarding.mjs` übernimmt seit PR20 die H5P-Auth- und H5P-Content-Access-Forwarding-Calls zum Backend und zur SvelteKit-BFF; `h5p-service/test/auth_forwarding.test.mjs` schützt Cookie-Minimierung, Backend/BFF-Fallback, URL-Encoding und Fail-Closed-Netzwerkfehler.
- `h5p-service/server.mjs` ist dadurch von 1942 auf 1633 LOC gesunken; weitere H5P-Splits sollen Route-Handler betreffen.
- `frontend/src/lib/learning-unit/layout.ts` übernimmt seit PR20 die reinen Viewport-, Workspace-Chrome-, Layout-Preference- und gespeicherten Workspace-State-Normalisierer der großen Learning-Unit-Route; `frontend/src/lib/learning-unit/layout.test.ts` schützt Breakpoints, Defaults, Clamping, Legacy-Layout-Normalisierung, Pane-Fokus und offene Modul-Tabs.
- `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte` ist dadurch von 1846 auf 1644 LOC gesunken; weitere Frontend-Splits sollen Ladezustand und View-Komposition trennen.

## Regel
Hotspots dürfen im Refactor nicht ohne bewusst dokumentierten Grund wachsen. Kleine Extraktionen sollen eine passende Contract- oder Komponententest-Abdeckung haben; harte LOC-Schwellen folgen, sobald die Baseline über mehrere Scorecards stabil ist.
