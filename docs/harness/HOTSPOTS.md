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
- `backend/web/routes/teaching_inmemory_repo.py` übernimmt seit Closeout v1.1 das In-Memory-Fallback-Repository inklusive Teaching-Fallback-Datenklassen. `backend/web/routes/teaching.py` behält die alten Namen nur als Kompatibilitätsaliase für bestehende Tests und Offline-Fallbacks.
- `backend/web/routes/teaching_courses.py` besitzt seit Closeout v1.1 die Course-Handler selbst statt nur an `backend/web/routes/teaching.py` zu delegieren; `backend/web/routes/teaching_course_state.py` hält den kurzlebigen Course-Deletion-Marker für Course-Delete und Course-Members.
- `backend/web/routes/teaching_units.py` besitzt seit Closeout v1.1 die Unit-Handler für List/Create/Get/Patch/Delete selbst statt nur an `backend/web/routes/teaching.py` zu delegieren. Bestehende Storage-Cleanup-Monkeypatch-Punkte bleiben über dynamische Kompatibilitätsauflösung erhalten.
- `backend/web/routes/teaching_unit_sections.py` besitzt seit Closeout v1.1 die Section-Handler für List/Create/Patch/Delete/Reorder selbst statt nur an `backend/web/routes/teaching.py` zu delegieren.
- `backend/web/routes/teaching_unit_tasks.py` besitzt seit Closeout v1.1 die Task-Handler für Section- und Module-Task-Authoring selbst statt nur an `backend/web/routes/teaching.py` zu delegieren; die eigentliche Task-Geschäftslogik bleibt im bestehenden `TasksService`.
- `backend/web/routes/teaching_course_modules.py` besitzt seit Closeout v1.1 die Course-Module- und Module-Section-Visibility-Handler selbst statt nur an `backend/web/routes/teaching.py` zu delegieren.
- `backend/web/routes/teaching_course_members.py` besitzt seit Closeout v1.1 die Course-Member-Handler selbst statt nur an `backend/web/routes/teaching.py` zu delegieren.
- `backend/web/routes/teaching_unit_modules.py` besitzt seit Closeout v1.1 die Unit-Phase-, Unit-Module-, Unit-Module-Edge-, Content-Target- und Unit-Module-Reorder-Handler selbst statt nur an `backend/web/routes/teaching.py` zu delegieren. Der Test-Reset für Teaching-Route-Globals stellt Helper jetzt aus dem jeweiligen Endpoint-Modul wieder her, damit Split-Router ihre eigenen dynamischen Provider behalten.
- `backend/web/routes/teaching_unit_materials.py` besitzt seit Closeout v1.1 die Section-Material-, Module-Material-, Upload-Intent-, Finalize-, Download-URL- und Reorder-Handler selbst statt nur an `backend/web/routes/teaching.py` zu delegieren. Storage-Adapter und MaterialsService werden dynamisch über die Teaching-Fassade aufgelöst, damit bestehende Test- und Runtime-Overrides kompatibel bleiben.
- `backend/web/routes/teaching_live.py` besitzt seit Closeout v1.1 die Live-Summary-, Live-Delta-, Student-Overview-, Latest-Submission-Detail- und Teaching-Submission-File-Handler selbst statt nur an `backend/web/routes/teaching.py` zu delegieren.
- `backend/web/routes/teaching.py` ist dadurch von 6146 auf 782 LOC gesunken. C1 ist damit als Route-Handler-Monolith weitgehend abgebaut; offen bleiben die schrittweise Ablösung der Teaching-Fassade, Repo-Provider-Globals, Storage-Adapter-Globals und gemeinsam genutzte Live-Helfer in fokussierte Provider-/Read-Model-Module.
- `backend/teaching/repo_row_mappers.py` übernimmt seit Closeout v1.1 reine Material-/Task-Row-Mapper und die Live-Score-Normalisierung. `backend/teaching/repo_live_queries.py` übernimmt seit Closeout v1.1 die Live-/Dashboard-Read-Model-Queries für Summary, Delta, Helper-Rows, Average-Scores und Live-Cursor. `backend/teaching/repo_material_queries.py` übernimmt seit Closeout v1.1 Material-CRUD, Upload-Intent, Finalize und Material-Reorder-SQL. `backend/teaching/repo_task_queries.py` übernimmt seit Closeout v1.1 Section-Task-CRUD, Task-Reorder, Course-Unit-Task-Read-Models und Latest-Submission-Aggregate. `backend/teaching/repo_db.py` ist dadurch von 4854 auf 3697 LOC gesunken. C2 ist damit begonnen, aber noch nicht abgeschlossen: Course-Module-Zugriffe und weitere Schreibfälle müssen weiter in klare Repository-Module getrennt werden.
- `backend/web/routes/learning_downloads.py` übernimmt seit Closeout v1.1 den SSRF-geschützten, größenbegrenzten Download-Fetcher inklusive Public-to-Internal-Supabase-Rewrite. `backend/web/routes/learning.py` behält nur den alten privaten Wrapper für bestehende Monkeypatch-Punkte.
- `backend/web/routes/learning_upload_proxy.py` übernimmt seit Closeout v1.1 Presign-Header-Encoding/-Decoding, Header-Allowlisting, URL-Part-Normalisierung und den patchbaren Upstream-PUT-Forwarder für den Learning-Upload-Proxy. `backend/web/routes/learning.py` behält Endpoint, Auth, CSRF, Body-Limit und kleine Kompatibilitätswrapper.
- `backend/web/routes/learning_upload_config.py` übernimmt seit Closeout v1.1 die Upload-Intent-TTL-, Dev-Stub-, Upload-Proxy- und Proxy-Timeout-Env-Parser.
- `backend/web/routes/learning.py` ist dadurch von 2884 auf 2670 LOC gesunken. C3 ist damit begonnen, aber noch nicht abgeschlossen: Upload-Intent-Endpoint, Submission- und Material-File-Flächen müssen weiter getrennt werden.
- `backend/web/routes/app_session_helpers.py` übernimmt seit Closeout v1.1 Runtime-/Session-Store-Auflösung, private App-Header, BFF-Shared-Secret-Prüfung und kleine Session-/User-Payload-Builder.
- `backend/web/routes/app_profile_helpers.py` übernimmt seit Closeout v1.1 reine Profil-Claims-, Namens-, Lock-Timestamp- und Identity-Attribute-Normalisierung. `backend/web/routes/app.py` behält die Keycloak-Admin-Schreibfunktionen und Kompatibilitätsaliase.
- `backend/web/routes/app.py` ist dadurch von 2499 auf 2362 LOC gesunken. C4 ist damit begonnen, aber noch nicht abgeschlossen: CLI-Token-Flächen, View-Modelle und große Dashboard-/Live-App-Read-Models müssen weiter getrennt werden.
- `backend/learning/repo_submission_mapping.py` übernimmt seit Closeout v1.1 Submission-Row-Mapping, öffentliche Fehler-Sanitizer und deterministische MVP-Analyse-/Feedback-Stubs. `backend/learning/repo_db.py` ist dadurch von 2425 auf 2249 LOC gesunken. C5 ist damit begonnen, aber noch nicht abgeschlossen: Course/Unit-Read-Modelle, Submission-Schreibfälle und Worker-nahe DB-Zugriffe müssen weiter getrennt werden.

## Regel
Hotspots dürfen nicht ohne bewusst dokumentierten Grund wachsen. Kleine Extraktionen brauchen passende Contract- oder Komponententest-Abdeckung. Die monatliche Scorecard dokumentiert LOC-Veränderungen; relevantes Wachstum braucht entweder eine getestete Extraktion oder einen expliziten Tech-Debt-Eintrag mit Exit-Kriterium.
