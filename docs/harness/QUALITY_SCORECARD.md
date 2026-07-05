# Quality Scorecard

Status: Draft
Owner: Produktverantwortlicher
Related plan: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Snapshot 2026-07 (generated 2026-07-05)

### Hotspot LOC trend
| File | LOC | Delta vs previous month |
| --- | ---: | ---: |
| backend/learning/repo_db.py | 2425 | +0 |
| backend/teaching/repo_db.py | 4854 | +0 |
| backend/web/main.py | 98 | +0 |
| backend/web/routes/app.py | 2499 | +0 |
| backend/web/routes/learning.py | 2884 | +0 |
| backend/web/routes/teaching.py | 6146 | +0 |
| frontend/src/lib/styles/app.css | 5617 | +0 |
| frontend/src/lib/styles/design-system.css | 1903 | +0 |
| frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte | 1710 | -136 |
| frontend/src/routes/teaching/units/[unitId]/+page.svelte | 1210 | +0 |
| h5p-service/server.mjs | 1709 | +0 |

### Security status
- Security quick checks: pass (/home/felix/gustav-alpha2/.venv/bin/pytest -q backend/tests/test_config_security.py backend/tests/test_privacy_logging_contract.py backend/tests/test_csrf_tokens_contract.py)

### Contract diff status
- OpenAPI contract baseline: pass (/home/felix/gustav-alpha2/.venv/bin/python -m backend.tools.openapi_contract_check --spec /home/felix/gustav-alpha2/api/openapi.yml)
- Route map inventory: pass (/home/felix/gustav-alpha2/.venv/bin/python -m backend.tools.route_map_inventory --check /home/felix/gustav-alpha2/docs/harness/ROUTE_MAP.md)

### Docker image parity
- Web image smoke check: not run (/home/felix/gustav-alpha2/.venv/bin/python -m backend.tools.docker_image_smoke)

- OpenAPI operations: 147
- Runtime operations: 136

### Open TECH_DEBT
- Outstanding entries: 1
| ID | Bereich | Risiko | Exit criterion |
| --- | --- | --- | --- |
| TD-001 | Harness PR 1 | Warning-Signale blockieren noch nicht | `make harness-signals` ist stabil und einzelne Signale sind als harte Gates eingeordnet |

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
