# Plan: Learning API cache hardening and ordering docs (2025-10-27)

Context
- Security-first: prevent caching of student-facing API responses that might contain PII.
- Contract-first: explicitly document stable secondary ordering for course lists.

Scope
- Align success responses of Learning API to `Cache-Control: private, no-store`.
- Clarify ordering of `/api/learning/courses`: `title asc, id asc`.
- Extend tests: pagination clamping and empty-list.

Changes
- OpenAPI (`api/openapi.yml`): update header examples and descriptions.
- Web adapter (`backend/web/routes/learning.py`): success headers -> `private, no-store`; docstring mentions stable order.
- Tests (`backend/tests/test_learning_my_courses_api.py`):
  - Update header assertions to `private, no-store`.
  - Add `test_list_student_courses_empty_list`.
  - Add `test_courses_pagination_clamp_limit_and_offset`.
- Docs: CHANGELOG additions.

Acceptance Criteria
- All adjusted tests pass locally (or skip if DB unavailable).
- Contract examples and runtime headers are consistent.
- Clear documentation of ordering and caching in code and contract.

