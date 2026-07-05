# Route Map

Status: Active
Owner: Produktverantwortlicher
Local checks: `make test-route-map`, `make test-api-contract-baseline`
CI status: `make verify` führt `make test-route-map` als hartes Gate aus; `make harness-minimum` prüft den Contract-Test.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/plan/2026-07-02-route-surface-map.md`
Review cadence: nach jedem Route-Surface- oder API-Vertrags-Refactor

## Zweck
Diese Route Map klassifiziert die technischen Oberflächen, damit OpenAPI-Lücken, BFF-Flächen, H5P-Service-Routen, Auth-Brücken, Health/Ops-Endpunkte und Legacy-UI-Routen nicht miteinander verwechselt werden.

## Gate-Regel
`make test-route-map` prüft, dass die generierte Route-für-Route-Inventur synchron mit Runtime-App und `api/openapi.yml` bleibt. Undokumentierte `/api/*`-Routen bleiben zusätzlich durch `make test-api-contract-baseline` verboten.

<!-- route-map:generated:start -->

| Route/Endpoint | Surface | Role | Data Access | Response Model | Existing Tests | Risk | Legacy Status | Decision | Target Layer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DELETE /api/app/profile/cli-tokens/{token_id} | BFF/internal | authenticated BFF | identity/session | empty/redirect | backend/tests/test_app_*, test_session_* | high | active | retain | SvelteKit BFF/view model |
| DELETE /api/teaching/courses/{course_id} | public API | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /api/teaching/courses/{course_id}/members/{student_sub} | public API | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /api/teaching/courses/{course_id}/modules/{module_id} | public API | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /api/teaching/units/{unit_id} | public API | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /api/teaching/units/{unit_id}/modules/edges | public API | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /api/teaching/units/{unit_id}/modules/{from_module_id}/edges/{to_module_id} | public API | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /api/teaching/units/{unit_id}/modules/{module_id} | public API | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id} | public API | teacher | teaching/learning repo + storage | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id} | public API | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /api/teaching/units/{unit_id}/phases/{phase_id} | public API | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /api/teaching/units/{unit_id}/sections/{section_id} | public API | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id} | public API | teacher | teaching/learning repo + storage | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id} | public API | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| DELETE /backend-internal/app/bff-session | BFF/internal | authenticated BFF | identity/session | unspecified | backend/tests/test_app_*, test_session_* | high | active | retain | SvelteKit BFF/view model |
| DELETE /h5p/contents/{content_id} | H5P service | teacher | H5P storage/service | empty/redirect | backend/tests/test_h5p_*, h5p-service/test/*.mjs | high | active | retain | H5P sidecar |
| GET /api/app/profile | BFF/internal | authenticated BFF | identity/session | AppProfileView | backend/tests/test_app_*, test_session_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/app/profile/cli-tokens | BFF/internal | authenticated BFF | identity/session | array | backend/tests/test_app_*, test_session_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/app/session-bootstrap | BFF/internal | authenticated BFF | identity/session | SessionBootstrap | backend/tests/test_app_*, test_session_* | high | active | retain | SvelteKit BFF/view model |
| GET /api/diagnostics/views/courses/{course_id}/matrix | BFF/internal | teacher | teaching repo | DiagnosticsCourseMatrixView | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/diagnostics/views/learners/{student_sub}/profile | BFF/internal | teacher | teaching/learning repo + storage | DiagnosticsLearnerProfileView | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/learning/courses | public API | student | learning repo | array | backend/tests/test_learning_*, test_openapi_learning_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/learning/courses/{course_id}/h5p/contents/{content_id}/access | public API | student | learning repo | empty/redirect | backend/tests/test_learning_*, test_openapi_learning_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/learning/courses/{course_id}/materials/{material_id}/file | public API | student | teaching/learning repo + storage | application/octet-stream | backend/tests/test_learning_*, test_openapi_learning_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/learning/courses/{course_id}/sections | public API | student | learning repo | array | backend/tests/test_learning_*, test_openapi_learning_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/learning/courses/{course_id}/sections/{section_id}/materials/{material_id}/file | public API | student | teaching/learning repo + storage | application/octet-stream | backend/tests/test_learning_*, test_openapi_learning_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/learning/courses/{course_id}/tasks/{task_id}/submissions | public API | student | learning repo | array | backend/tests/test_learning_*, test_openapi_learning_* | high | active | retain | OpenAPI + use case adapter |
| GET /api/learning/courses/{course_id}/tasks/{task_id}/submissions/{submission_id}/file | public API | student | teaching/learning repo + storage | application/octet-stream | backend/tests/test_learning_*, test_openapi_learning_* | high | active | retain | OpenAPI + use case adapter |
| GET /api/learning/courses/{course_id}/units | public API | student | learning repo | array | backend/tests/test_learning_*, test_openapi_learning_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/learning/courses/{course_id}/units/{unit_id}/modules/graph | public API | student | learning repo | LearningUnitModulesGraphResponse | backend/tests/test_learning_*, test_openapi_learning_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id} | public API | student | learning repo | LearningModuleContent | backend/tests/test_learning_*, test_openapi_learning_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/learning/courses/{course_id}/units/{unit_id}/sections | public API | student | learning repo | array | backend/tests/test_learning_*, test_openapi_learning_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/learning/views/concern-box | BFF/internal | student | learning repo | LearnerConcernBoxView | backend/tests/test_learning_*, test_openapi_learning_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/learning/views/learner-home | BFF/internal | student | learning repo | LearnerHome | backend/tests/test_learning_*, test_openapi_learning_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/live/views/courses/{course_id}/units | BFF/internal | teacher | teaching repo | LiveCourseUnitsView | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | SvelteKit BFF/view model |
| GET /api/live/views/courses/{course_id}/units/{unit_id}/dashboard | BFF/internal | teacher | teaching repo | LiveUnitDashboardView | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | SvelteKit BFF/view model |
| GET /api/live/views/courses/{course_id}/units/{unit_id}/detail-sheet | BFF/internal | teacher | teaching repo | LiveDetailSheetView | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | SvelteKit BFF/view model |
| GET /api/live/views/courses/{course_id}/units/{unit_id}/matrix | BFF/internal | teacher | teaching repo | LiveUnitMatrixView | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | SvelteKit BFF/view model |
| GET /api/me | public API | authenticated | none | Me | backend/tests/test_api_me_with_db_session_store.py, backend/tests/test_auth_contract.py, backend/tests/test_auth_middleware.py | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/courses | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/courses/{course_id} | public API | teacher | teaching repo | Course | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/courses/{course_id}/members | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/courses/{course_id}/modules | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/courses/{course_id}/modules/{module_id}/sections | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/courses/{course_id}/modules/{module_id}/sections/releases | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/courses/{course_id}/students/{student_sub}/submissions/overview | public API | teacher | learning repo | TeachingStudentLiveOverview | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta | public API | teacher | learning repo | object | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary | public API | teacher | learning repo | object | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest | public API | teacher | learning repo | TeachingLatestSubmission | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest/file | public API | teacher | teaching/learning repo + storage | application/octet-stream | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/units | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/units/{unit_id} | public API | teacher | teaching repo | Unit | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/units/{unit_id}/modules/graph | public API | teacher | teaching repo | TeachingUnitModulesGraphResponse | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/units/{unit_id}/modules/{module_id}/content-target | public API | teacher | teaching repo | object | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/units/{unit_id}/phases | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/units/{unit_id}/sections | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/units/{unit_id}/sections/{section_id}/materials | public API | teacher | teaching/learning repo + storage | array | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url | public API | teacher | teaching/learning repo + storage | MaterialDownloadUrlResponse | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/units/{unit_id}/sections/{section_id}/tasks | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/editor-model | public API | teacher | teaching repo | H5PEditorModelResponse | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/export | public API | teacher | teaching repo | application/zip | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | OpenAPI + use case adapter |
| GET /api/teaching/views/concern-box | BFF/internal | teacher | teaching repo | TeacherConcernBoxView | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/teaching/views/courses | BFF/internal | teacher | teaching repo | TeacherCourseListView | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/teaching/views/courses/{course_id}/ai-usage | BFF/internal | teacher | teaching repo | TeacherCourseAiUsageView | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/teaching/views/courses/{course_id}/context | BFF/internal | teacher | teaching repo | TeacherCourseContextView | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/teaching/views/teacher-home | BFF/internal | teacher | teaching repo | TeacherHome | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/teaching/views/units/catalog | BFF/internal | teacher | teaching repo | TeacherUnitsCatalogView | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/teaching/views/units/{unit_id}/nodes/{node_id}/editor | BFF/internal | teacher | teaching repo | TeacherUnitNodeEditorView | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/teaching/views/units/{unit_id}/workspace | BFF/internal | teacher | teaching repo | TeacherUnitWorkspaceView | backend/tests/test_teaching_*, test_openapi_teaching_* | medium | active | retain | SvelteKit BFF/view model |
| GET /api/users/list | public API | teacher/admin | none | array | backend/tests/test_users_*, test_openapi_* | high | active | retain | OpenAPI + use case adapter |
| GET /api/users/search | public API | teacher/admin | none | array | backend/tests/test_users_*, test_openapi_* | high | active | retain | OpenAPI + use case adapter |
| GET /auth/callback | auth bridge | public/authenticated | identity/session | unspecified | backend/tests/test_auth_* | high | active | retain | identity adapter |
| GET /auth/continue | auth bridge | public/authenticated | identity/session | unspecified | backend/tests/test_auth_* | high | active | retain | identity adapter |
| GET /auth/forgot | auth bridge | public/authenticated | identity/session | unspecified | backend/tests/test_auth_* | high | active | retain | identity adapter |
| GET /auth/login | auth bridge | public/authenticated | identity/session | empty/redirect | backend/tests/test_auth_* | high | active | retain | identity adapter |
| GET /auth/logout | auth bridge | public/authenticated | identity/session | unspecified | backend/tests/test_auth_* | high | active | retain | identity adapter |
| GET /auth/logout/success | auth bridge | public/authenticated | identity/session | HTML | backend/tests/test_auth_* | high | active | retain | identity adapter |
| GET /auth/password | auth bridge | public/authenticated | identity/session | empty/redirect | backend/tests/test_auth_* | high | active | retain | identity adapter |
| GET /auth/register | auth bridge | public/authenticated | identity/session | empty/redirect | backend/tests/test_auth_* | high | active | retain | identity adapter |
| GET /backend-internal/app/bff-session | BFF/internal | authenticated BFF | identity/session | unspecified | backend/tests/test_app_*, test_session_* | high | active | retain | SvelteKit BFF/view model |
| GET /h5p/auth/me | H5P service | authenticated principal bridge | web /api/me principal bridge | Me | backend/tests/test_h5p_*, h5p-service/test/*.mjs | high | active | retain | H5P sidecar |
| GET /h5p/contents/{content_id}/export | H5P service | teacher | H5P storage/service | application/zip | backend/tests/test_h5p_*, h5p-service/test/*.mjs | medium | active | retain | H5P sidecar |
| GET /h5p/editor | H5P service | admin | H5P storage/service | HTML | backend/tests/test_h5p_*, h5p-service/test/*.mjs | medium | active | retain | H5P sidecar |
| GET /h5p/editor/model | H5P service | teacher | H5P storage/service | H5PEditorModelResponse | backend/tests/test_h5p_*, h5p-service/test/*.mjs | medium | active | retain | H5P sidecar |
| GET /h5p/healthz | H5P service | public | service status | H5PHealth | backend/tests/test_h5p_*, h5p-service/test/*.mjs | medium | active | retain | H5P sidecar |
| GET /h5p/libraries | H5P service | teacher | H5P storage/service | H5PLibrariesResponse | backend/tests/test_h5p_*, h5p-service/test/*.mjs | medium | active | retain | H5P sidecar |
| GET /h5p/player | H5P service | admin | H5P storage/service | HTML | backend/tests/test_h5p_*, h5p-service/test/*.mjs | medium | active | retain | H5P sidecar |
| GET /h5p/player/model | H5P service | student/teacher | H5P storage/service | H5PPlayerModelResponse | backend/tests/test_h5p_*, h5p-service/test/*.mjs | medium | active | retain | H5P sidecar |
| GET /h5p/player/review | H5P service | teacher/admin | H5P storage + review token | H5PPlayerModelResponse | backend/tests/test_h5p_*, h5p-service/test/*.mjs | medium | active | retain | H5P sidecar |
| GET /health | health/ops | ops | service status | object | backend/tests/test_*health* | low | active | retain | ops adapter |
| GET /internal/health/learning-worker | health/ops | ops | service status | LearningWorkerHealth | backend/tests/test_*health* | low | active | retain | ops adapter |
| GET /internal/health/openai | health/ops | ops | service status | OpenAIHealth | backend/tests/test_*health* | low | active | retain | ops adapter |
| PATCH /api/app/profile/display-name | BFF/internal | authenticated BFF | identity/session | empty/redirect | backend/tests/test_app_*, test_session_* | high | active | retain | SvelteKit BFF/view model |
| PATCH /api/app/profile/name | BFF/internal | authenticated BFF | identity/session | empty/redirect | backend/tests/test_app_*, test_session_* | high | active | retain | SvelteKit BFF/view model |
| PATCH /api/teaching/courses/{course_id} | public API | teacher | teaching repo | Course | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| PATCH /api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility | public API | teacher | teaching repo | ModuleSectionVisibility | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| PATCH /api/teaching/units/{unit_id} | public API | teacher | teaching repo | Unit | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| PATCH /api/teaching/units/{unit_id}/modules/{module_id} | public API | teacher | teaching repo | TeachingUnitModule | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| PATCH /api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id} | public API | teacher | teaching/learning repo + storage | Material | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| PATCH /api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id} | public API | teacher | teaching repo | Task | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| PATCH /api/teaching/units/{unit_id}/phases/{phase_id} | public API | teacher | teaching repo | TeachingUnitPhase | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| PATCH /api/teaching/units/{unit_id}/sections/{section_id} | public API | teacher | teaching repo | Section | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| PATCH /api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id} | public API | teacher | teaching/learning repo + storage | Material | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| PATCH /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id} | public API | teacher | teaching repo | Task | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| PATCH /backend-internal/app/bff-session | BFF/internal | authenticated BFF | identity/session | unspecified | backend/tests/test_app_*, test_session_* | high | active | retain | SvelteKit BFF/view model |
| PATCH /h5p/contents/{content_id} | H5P service | teacher | H5P storage/service | H5PContentSaveResponse | backend/tests/test_h5p_*, h5p-service/test/*.mjs | high | active | retain | H5P sidecar |
| POST /api/app/profile/cli-tokens | BFF/internal | authenticated BFF | identity/session | CLITokenCreated | backend/tests/test_app_*, test_session_* | high | active | retain | SvelteKit BFF/view model |
| POST /api/app/session-sync | BFF/internal | authenticated BFF | identity/session | empty/redirect | backend/tests/test_app_*, test_session_* | high | active | retain | SvelteKit BFF/view model |
| POST /api/learning/concern-box/entries | BFF/internal | student | learning repo | ConcernBoxEntryCreated | backend/tests/test_learning_*, test_openapi_learning_* | high | active | retain | SvelteKit BFF/view model |
| POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions | public API | student | learning repo | LearningSubmission | backend/tests/test_learning_*, test_openapi_learning_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions/finalize | public API | student | learning repo | LearningSubmission | backend/tests/test_learning_*, test_openapi_learning_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/learning/courses/{course_id}/tasks/{task_id}/upload-intents | public API | student | teaching/learning repo + storage | StudentUploadIntentResponse | backend/tests/test_learning_*, test_openapi_learning_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/concern-box/entries/{entry_id}/archive | BFF/internal | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | SvelteKit BFF/view model |
| POST /api/teaching/concern-box/entries/{entry_id}/restore | BFF/internal | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | SvelteKit BFF/view model |
| POST /api/teaching/courses | public API | teacher | teaching repo | Course | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/courses/{course_id}/members | public API | teacher | teaching repo | empty/redirect | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/courses/{course_id}/modules | public API | teacher | teaching repo | CourseModule | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/courses/{course_id}/modules/reorder | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units | public API | teacher | teaching repo | Unit | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/modules | public API | teacher | teaching repo | TeachingUnitModule | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/modules/edges | public API | teacher | teaching repo | TeachingUnitGraphEdge | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/modules/{module_id}/materials | public API | teacher | teaching/learning repo + storage | Material | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/modules/{module_id}/materials/finalize | public API | teacher | teaching/learning repo + storage | Material | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/modules/{module_id}/materials/reorder | public API | teacher | teaching/learning repo + storage | array | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/modules/{module_id}/materials/upload-intents | public API | teacher | teaching/learning repo + storage | MaterialUploadIntentResponse | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/modules/{module_id}/tasks | public API | teacher | teaching repo | Task | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/modules/{module_id}/tasks/reorder | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/import | public API | teacher | teaching repo | Task | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/reset | public API | teacher | teaching repo | Task | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/phases | public API | teacher | teaching repo | TeachingUnitPhase | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/phases/reorder | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/phases/{phase_id}/modules/reorder | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/sections | public API | teacher | teaching repo | Section | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/sections/reorder | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/sections/{section_id}/materials | public API | teacher | teaching/learning repo + storage | Material | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize | public API | teacher | teaching/learning repo + storage | Material | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/sections/{section_id}/materials/reorder | public API | teacher | teaching/learning repo + storage | array | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents | public API | teacher | teaching/learning repo + storage | MaterialUploadIntentResponse | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/sections/{section_id}/tasks | public API | teacher | teaching repo | Task | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/sections/{section_id}/tasks/reorder | public API | teacher | teaching repo | array | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/import | public API | teacher | teaching repo | Task | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/reset | public API | teacher | teaching repo | Task | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/save | public API | teacher | teaching repo | H5PContentSaveResponse | backend/tests/test_teaching_*, test_openapi_teaching_* | high | active | retain | OpenAPI + use case adapter |
| POST /h5p/ajax | H5P service | service | H5P storage + learning forwarding | object | backend/tests/test_h5p_*, h5p-service/test/*.mjs | high | active | retain | H5P sidecar |
| POST /h5p/contents | H5P service | teacher | H5P storage/service | H5PContentSaveResponse | backend/tests/test_h5p_*, h5p-service/test/*.mjs | high | active | retain | H5P sidecar |
| POST /h5p/contents/import | H5P service | teacher | H5P storage/service | H5PContentImportResponse | backend/tests/test_h5p_*, h5p-service/test/*.mjs | high | active | retain | H5P sidecar |
| POST /h5p/finishedData | H5P service | student/teacher | H5P storage + learning forwarding | object | backend/tests/test_h5p_*, h5p-service/test/*.mjs | high | active | retain | H5P sidecar |
| POST /h5p/libraries/import | H5P service | teacher | H5P storage/service | H5PLibraryImportResponse | backend/tests/test_h5p_*, h5p-service/test/*.mjs | high | active | retain | H5P sidecar |
| PUT /api/learning/internal/upload-proxy | BFF/internal | student | teaching/learning repo + storage | object | backend/tests/test_learning_*, test_openapi_learning_* | high | active | retain | SvelteKit BFF/view model |
| PUT /api/learning/internal/upload-stub | BFF/internal | student | teaching/learning repo + storage | object | backend/tests/test_learning_*, test_openapi_learning_* | high | active | retain | SvelteKit BFF/view model |
| PUT /backend-internal/app/bff-session | BFF/internal | authenticated BFF | identity/session | unspecified | backend/tests/test_app_*, test_session_* | high | active | retain | SvelteKit BFF/view model |

<!-- route-map:generated:end -->

## Abschlussstand
- FastAPI registriert keine aktiven Legacy-Produkt-HTML-Seiten mehr.
- Bereits entfernte Legacy-Produktpfade bleiben durch Characterization-Tests als 410- oder Redirect-Verhalten geschützt.
- `make test-route-map` hält Runtime-App und generierte Route Map synchron.
