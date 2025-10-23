# Plan: Teaching Tasks PATCH fix & contract sync

## Goal
Restore PATCH stability for section tasks and align the API contract/error codes after the review findings.

## Context
- `backend/teaching/services/tasks.py` forwards a private `_UNSET` sentinel to the DB repo which expects its own sentinel object, causing a 500 on partial updates.
- OpenAPI spec misses the documented `invalid_hints_md` detail code while the adapter returns it.
- Tests currently lack coverage for single-field PATCH behaviour.

## Steps
1. Add regression tests (API integration + unit if needed) that exercise partial PATCH updates and expect 200.
2. Adjust service/repo handoff so omitted fields honour the repo sentinel instead of leaking custom objects.
3. Update `api/openapi.yml` (and docs/CHANGELOG) to include `invalid_hints_md`.
4. Run targeted pytest suite (`backend/tests/test_teaching_tasks_service_unit.py` & `backend/tests/test_teaching_tasks_api.py`) to verify fixes.

## Risks & Mitigations
- **Risk:** Circular dependency or leaky abstractions when sharing sentinels.  
  **Mitigation:** Only pass kwargs for provided fields so repo defaults remain untouched.
- **Risk:** Test runtime if DB unavailable.  
  **Mitigation:** Tests already guard via `require_db_or_skip`; ensure environment ready before running.
