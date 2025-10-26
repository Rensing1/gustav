# Plan: Course GET UUID validation and Users cache/permissions

Context: Review identified two main improvements:
- API robustness: Validate `course_id` (UUID) for GET /api/teaching/courses/{course_id} and return 400 `invalid_course_id`.
- Governance: Ensure Users endpoints document/return private no-store and permissions in OpenAPI.

Steps (TDD):
1) Add failing tests: course GET invalid id -> 400.
2) Update OpenAPI: 400 invalid_course_id + Cache-Control headers for GETs; x-permissions for Users endpoints.
3) Implement minimal code: UUID guard in route; align Users cache headers.
4) Update docs (CHANGELOG).

Acceptance:
- pytest covers the new 400 case; existing tests remain passing.
- OpenAPI contains the new response/header entries and x-permissions.
