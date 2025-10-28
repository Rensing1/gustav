# 2025-10-28 — Security and OpenAPI Fixes

Goal:
- Harden SECURITY DEFINER helper `get_released_sections_for_student_by_unit` by setting `search_path = pg_catalog, public`.
- Fix OpenAPI contract for `GET /api/learning/courses/{course_id}/units/{unit_id}/sections` by adding 401/403/404 responses and removing misplaced blocks.

Context:
- Rationale: SECURITY DEFINER functions must not rely on attacker-controlled schemas. OpenAPI must remain valid for tooling, docs, and tests.

User Stories:
- As a platform admin, I want SECURITY DEFINER helpers to be safe-by-default (no search_path abuse), so RLS guarantees hold.
- As a developer, I want a valid OpenAPI contract so clients and documentation remain trustworthy.

BDD Scenarios:
- Given the unit sections endpoint, When I read the OpenAPI, Then 401/403/404 responses are documented.
- Given malformed `include`, When I call the endpoint, Then I receive 400 with `detail=invalid_include`.
- Given a non-member student, When they call the endpoint, Then they receive 403.

Implementation Steps:
1) Add failing contract test for OpenAPI unit sections responses.
2) Add API tests for invalid include and 403.
3) Fix OpenAPI YAML (add responses, remove stray blocks).
4) Harden SQL helper search_path.
5) Run tests; update changelog.

Risks:
- YAML indentation errors → mitigated by contract test.
- Migration ordering: current change is forward-only and does not drop data.

