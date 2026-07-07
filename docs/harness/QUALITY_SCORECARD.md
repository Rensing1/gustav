# Quality Scorecard

Status: Active
Owner: Produktverantwortlicher
Related plan: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Snapshot 2026-07 (generated 2026-07-07)

### Hotspot LOC trend
| File | LOC | Delta vs previous month |
| --- | ---: | ---: |
| backend/learning/repo_db.py | 511 | +0 |
| backend/teaching/repo_db.py | 1487 | +0 |
| backend/tests/test_gustav_cli.py | 1210 | n/a |
| backend/tests/test_learning_api_contract.py | 2326 | n/a |
| backend/tests/test_learning_worker_jobs.py | 2009 | n/a |
| backend/tests/test_teaching_live_detail_api.py | 1184 | n/a |
| backend/tests/test_teaching_live_unit_summary_api.py | 1219 | n/a |
| backend/web/main.py | 93 | +0 |
| backend/web/routes/app.py | 382 | +0 |
| backend/web/routes/learning.py | 1124 | +0 |
| backend/web/routes/teaching.py | 734 | +0 |
| backend/web/static/css/gustav.css | 2684 | +0 |
| frontend/src/lib/components/learning-unit/LearningTaskCard.test.ts | 1202 | n/a |
| frontend/src/lib/styles/app.css | 1292 | +0 |
| frontend/src/lib/styles/design-system.css | 5 | +0 |
| frontend/src/lib/styles/learning-unit.css | 2492 | +0 |
| frontend/src/lib/styles/teaching-workspace.css | 2468 | +0 |
| frontend/src/lib/styles/theme-tokens.css | 56 | +0 |
| frontend/src/lib/styles/typography.css | 40 | +0 |
| frontend/src/lib/styles/ui-primitives.css | 1141 | +0 |
| frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte | 1604 | -40 |
| frontend/src/routes/teaching/units/[unitId]/+page.svelte | 1063 | -43 |
| h5p-service/server.mjs | 1394 | +0 |

### Security status
- Security quick checks: pass (/home/felix/gustav-alpha2/.venv/bin/pytest -q backend/tests/test_config_security.py backend/tests/test_privacy_logging_contract.py backend/tests/test_csrf_tokens_contract.py)

### Contract diff status
- OpenAPI contract baseline: pass (/home/felix/gustav-alpha2/.venv/bin/python -m backend.tools.openapi_contract_check --spec /home/felix/gustav-alpha2/api/openapi.yml)
- Route map inventory: pass (/home/felix/gustav-alpha2/.venv/bin/python -m backend.tools.route_map_inventory --check /home/felix/gustav-alpha2/docs/harness/ROUTE_MAP.md)

### Docker image parity
- Web image smoke check: pass (/home/felix/gustav-alpha2/.venv/bin/python -m backend.tools.docker_image_smoke)

- OpenAPI operations: 147
- Runtime operations: 134

### Open TECH_DEBT
- Outstanding entries: 0

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
