# Quality Scorecard

Status: Active
Owner: Produktverantwortlicher
Related plan: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Snapshot 2026-09 (generated 2026-09-06)

### Hotspot LOC trend
| File | LOC | Delta vs previous month |
| --- | ---: | ---: |
| backend/learning/repo_db.py | 597 | +86 |
| backend/learning/repo_submission_command_queries.py | 912 | n/a |
| backend/learning/workers/process_learning_submission_jobs.py | 1500 | +233 |
| backend/teaching/repo_db.py | 1779 | +292 |
| backend/tests/test_gustav_cli.py | 1299 | +89 |
| backend/tests/test_learning_api_contract.py | 2354 | +28 |
| backend/tests/test_learning_worker_jobs.py | 2018 | +9 |
| backend/tests/test_teaching_live_detail_api.py | 1237 | +53 |
| backend/tests/test_teaching_live_unit_summary_api.py | 1351 | +132 |
| backend/web/main.py | 101 | +8 |
| backend/web/routes/app.py | 540 | +158 |
| backend/web/routes/learning.py | 1194 | +70 |
| backend/web/routes/teaching.py | 758 | +24 |
| backend/web/routes/teaching_live.py | 965 | -121 |
| backend/web/static/css/gustav.css | 2684 | +0 |
| frontend/src/lib/components/learning-unit/LearningTaskCard.svelte | 1301 | n/a |
| frontend/src/lib/components/learning-unit/LearningTaskCard.test.ts | 2612 | +1410 |
| frontend/src/lib/styles/app.css | 862 | -430 |
| frontend/src/lib/styles/design-system.css | 5 | +0 |
| frontend/src/lib/styles/learning-unit.css | 5112 | +2620 |
| frontend/src/lib/styles/teaching-workspace.css | 3828 | +1360 |
| frontend/src/lib/styles/theme-tokens.css | 86 | +30 |
| frontend/src/lib/styles/typography.css | 39 | -1 |
| frontend/src/lib/styles/ui-primitives.css | 1455 | +314 |
| frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte | 1983 | +379 |
| frontend/src/routes/live/+page.svelte | 1183 | n/a |
| frontend/src/routes/teaching/units/[unitId]/+page.svelte | 1439 | +376 |
| frontend/src/routes/teaching/units/[unitId]/nodes/[nodeId]/+page.svelte | 1887 | n/a |
| h5p-service/server.mjs | 1363 | +43 |

### Security status
- Security quick checks: pass (.venv/bin/pytest -q backend/tests/test_config_security.py backend/tests/test_privacy_logging_contract.py backend/tests/test_csrf_tokens_contract.py)

### Contract diff status
- OpenAPI contract baseline: pass (.venv/bin/python -m backend.tools.openapi_contract_check --spec api/openapi.yml)
- Route map inventory: pass (.venv/bin/python -m backend.tools.route_map_inventory --check docs/harness/ROUTE_MAP.md)

### Docker image parity
- Web image smoke check: pass (.venv/bin/python -m backend.tools.docker_image_smoke)

- OpenAPI operations: 190
- Runtime operations: 177

### Open TECH_DEBT
- Outstanding entries: 3
| ID | Bereich | Risiko | Exit criterion |
| --- | --- | --- | --- |
| TD-001 | Abhängigkeiten | Sicherheitslücken | Drei aktuelle Audits und nachvollziehbare Bewertung aller Meldungen |
| TD-004 | Backend | Globale Kopplung und Testleckagen | Appbezogene Provider und grüne Isolationstests ohne Reparatur-Fixtures |
| TD-006 | Frontend und Abläufe | Hohe Änderungskosten und Designabweichungen | Gemeinsame Komponenten, getrennte Controller und vollständige Feature-/Designnachweise |

### Skill inventory and eval status
- Active skills: 7
- Active skills with manual-forward eval status: 7
| Skill | Eval status | Activation status |
| --- | --- | --- |
| gustav-plan-status | manual forward-tested | active |
| gustav-harness-gardener | manual forward-tested | active |
| gustav-pr-review | manual forward-tested | active |
| gustav-pr-fix | manual forward-tested | active |
| gustav-api-contract | manual forward-tested | active |
| gustav-security-review | manual forward-tested | active |
| gustav-route-map | manual forward-tested | active |
