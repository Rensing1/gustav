# Hotspots

Status: Active
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Zweck
Dieses Dokument markiert Dateien, die im Refactor nicht weiter anwachsen sollen, ohne dass bewusst Debt dokumentiert wird.

## Initiale Hotspots
| Datei | Baseline LOC | Bereich | Split-Ziel |
| --- | ---: | --- | --- |
| `backend/web/main.py` | 98 | App Composition | nicht wieder mit Route-, Auth- oder Rendering-Logik füllen |
| `backend/web/routes/teaching.py` | 6146 | Teaching Web Adapter | Use-Case-, Guard-, Read-Model- und Serializer-Grenzen klein halten |
| `backend/web/routes/learning.py` | 2884 | Learning Web Adapter | Upload-/Storage-, Submission- und Material-Read-Grenzen klein halten |
| `backend/web/routes/app.py` | 2499 | Browser-BFF und App-Routen | Profil-, Session- und View-Helfer klein halten |
| `backend/learning/repo_db.py` | 2425 | Learning Repository | Read Models und Query-Gruppen schrittweise isolieren |
| `backend/teaching/repo_db.py` | 4854 | Teaching Repository | Live-/Dashboard-Read-Models und Schreibfälle trennen |
| `h5p-service/server.mjs` | 1633 | H5P Sidecar | Route-Handler klein halten |
| `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte` | 1644 | Learning Workspace | Loader- und View-Komponenten klein halten |
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
- `h5p-service/server.mjs` ist dadurch von 1942 auf 1633 LOC gesunken; Route-Handler-Wachstum bleibt im Scorecard-Monitoring.
- `frontend/src/lib/learning-unit/layout.ts` übernimmt seit PR20 die reinen Viewport-, Workspace-Chrome-, Layout-Preference- und gespeicherten Workspace-State-Normalisierer der großen Learning-Unit-Route; `frontend/src/lib/learning-unit/layout.test.ts` schützt Breakpoints, Defaults, Clamping, Legacy-Layout-Normalisierung, Pane-Fokus und offene Modul-Tabs.
- `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte` ist dadurch von 1846 auf 1644 LOC gesunken; Ladezustand und View-Komposition bleiben im Scorecard-Monitoring.

## Closeout v1.1 Fortschritt
- `backend/web/routes/teaching_payloads.py` übernimmt seit Closeout v1.1 die Pydantic-Request-Payloads für Teaching-Routen. `backend/web/routes/teaching.py` exportiert die Namen weiterhin als Kompatibilitätsalias für bestehende Split-Router und Tests.
- `backend/web/routes/teaching_validation.py` übernimmt seit Closeout v1.1 reine UUID-, Integer- und Pagination-Helfer ohne FastAPI-Response-Abhängigkeit.
- `backend/web/routes/teaching_storage_cleanup.py` übernimmt seit Closeout v1.1 die Unit-delete-Storage-Ermittlung, das Page-Key-Metadaten-Parsing und die fail-closed Storage-Löschung. `backend/web/routes/teaching.py` behält nur kleine Kompatibilitätswrapper für bestehende Monkeypatch-Punkte.
- `backend/web/routes/teaching_submission_files.py` übernimmt seit Closeout v1.1 Dateinamen-Sanitizing, begrenztes Download-Fetching und den Teaching-Submission-File-Href-Builder. `backend/web/routes/teaching.py` exportiert die bisherigen privaten Namen weiterhin als Kompatibilitätsalias für bestehende Tests.
- `backend/teaching/repo_row_mappers.py` ist außerdem der einzige Besitzer der Live-Score-Normalisierung; `backend/web/routes/teaching.py` re-exportiert diese Funktion nur noch für bestehende Tests.
- `backend/web/routes/teaching.py` ist dadurch von 6146 auf 5591 LOC gesunken. C1 ist damit begonnen, aber noch nicht abgeschlossen: Route-Handler, Repo-Provider, weitere Storage-Adapter-Globals und Live-/Material-/Task-Flächen müssen weiter aus dem Hotspot herausgelöst werden.
- `backend/teaching/repo_row_mappers.py` übernimmt seit Closeout v1.1 reine Material-/Task-Row-Mapper und die Live-Score-Normalisierung. `backend/teaching/repo_db.py` ist dadurch von 4854 auf 4716 LOC gesunken. C2 ist damit begonnen, aber noch nicht abgeschlossen: Live-/Dashboard-Read-Models, Material-/Task-Zugriffe und Schreibfälle müssen weiter in klare Repository-Module getrennt werden.
- `backend/web/routes/learning_downloads.py` übernimmt seit Closeout v1.1 den SSRF-geschützten, größenbegrenzten Download-Fetcher inklusive Public-to-Internal-Supabase-Rewrite. `backend/web/routes/learning.py` behält nur den alten privaten Wrapper für bestehende Monkeypatch-Punkte.
- `backend/web/routes/learning_upload_proxy.py` übernimmt seit Closeout v1.1 Presign-Header-Encoding/-Decoding, Header-Allowlisting, URL-Part-Normalisierung und den patchbaren Upstream-PUT-Forwarder für den Learning-Upload-Proxy. `backend/web/routes/learning.py` behält Endpoint, Auth, CSRF, Body-Limit und kleine Kompatibilitätswrapper.
- `backend/web/routes/learning_upload_config.py` übernimmt seit Closeout v1.1 die Upload-Intent-TTL-, Dev-Stub-, Upload-Proxy- und Proxy-Timeout-Env-Parser.
- `backend/web/routes/learning.py` ist dadurch von 2884 auf 2670 LOC gesunken. C3 ist damit begonnen, aber noch nicht abgeschlossen: Upload-Intent-Endpoint, Submission- und Material-File-Flächen müssen weiter getrennt werden.
- `backend/web/routes/app_session_helpers.py` übernimmt seit Closeout v1.1 Runtime-/Session-Store-Auflösung, private App-Header, BFF-Shared-Secret-Prüfung und kleine Session-/User-Payload-Builder. `backend/web/routes/app.py` ist dadurch von 2499 auf 2412 LOC gesunken. C4 ist damit begonnen, aber noch nicht abgeschlossen: Profil-Helfer, CLI-Token-Flächen, View-Modelle und große Dashboard-/Live-App-Read-Models müssen weiter getrennt werden.

## Regel
Hotspots dürfen nicht ohne bewusst dokumentierten Grund wachsen. Kleine Extraktionen brauchen passende Contract- oder Komponententest-Abdeckung. Die monatliche Scorecard dokumentiert LOC-Veränderungen; relevantes Wachstum braucht entweder eine getestete Extraktion oder einen expliziten Tech-Debt-Eintrag mit Exit-Kriterium.
