# Plan: Unify 404/403 semantics for Teaching members endpoints (XS)

Goal: Align add/remove/list members with OpenAPI: return 404 when the course does not exist, 403 when the caller is not the owner; add minimal logging for diagnostics.

Scope (XS):
- Backend: `backend/web/routes/teaching.py` (small local changes)
- Tests: `backend/tests/test_teaching_members_semantics.py` (new)
- No schema or migrations; OpenAPI already describes desired semantics.

User Story
- As a teacher (course owner), when I delete a course, any immediate roster operations (add/remove/list) against that id should yield 404 Not Found, not 403 Forbidden, so the client can react correctly.

BDD Scenarios
- Given a teacher owns a course, When they delete it, Then subsequent POST /members returns 404.
- Given a teacher owns a course, When they delete it, Then subsequent DELETE /members/{student} returns 404.
- Given a teacher owns a course, When they delete it, Then subsequent GET /members returns 404.

API Contract (reference only)
- `api/openapi.yml` already specifies 404 for non-existent course on these endpoints; no changes required.

Tests (TDD)
- Add `backend/tests/test_teaching_members_semantics.py` with three async tests (DB-backed, skip if helpers unavailable):
  - add-after-delete -> 404
  - remove-after-delete -> 404
  - list-after-delete -> 404

Implementation Notes
- In `add_member` and `remove_member`, when `course_exists` is False, always return 404 (remove the “seen”-based 403 branch). Optionally treat “recently deleted” as 404 as a defensive shortcut.
- Add a `logger.warning` on list_members exception path (without leaking details to clients).
- Update PATCH docstring to reflect DB-backed 404/403 disambiguation.

Security
- Preserve RLS-first behavior via DB repo helpers; avoid information leakage. Logging only to server logs.

Out of Scope
- Larger refactors and cross-endpoint helper extraction; keep change minimal and local.

