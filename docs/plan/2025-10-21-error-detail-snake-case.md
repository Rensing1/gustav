# Plan: Harmonize error detail codes (snake_case)

## Context
- Existing HTTP error responses sometimes expose `detail` strings with spaces.
- API governance requires snake_case detail codes for consistency and machine parsing.
- Multiple teaching and users endpoints return these `detail` values; contract/tests must reflect the change before implementation.

## User Story
**As** Felix (Product Owner and teacher)\
**I want** every documented `detail` string in Teaching and Users APIs to use snake_case\
**So that** clients can rely on a uniform, parseable error contract.

## Scope
- Endpoints: `/api/teaching/courses*`, `/api/teaching/units/*/sections*`, `/api/users/search`, related reorder helpers.
- Align OpenAPI error descriptions, pytest expectations, and route implementations.
- No database or repository changes.

## Out of Scope
- Introducing new error types.
- Refactoring repository/business logic.
- Frontend adaptations (communicate separately).

## Assumptions
- Clients accept a short-lived breaking change once contract + changelog communicate it.
- Error schema continues using `{ "error": "bad_request", "detail": "<snake_case>" }`.

## Risks & Mitigations
- **Risk:** Clients still expect old strings → mitigated by updating contract/tests and highlighting in release notes.
- **Risk:** Missing coverage on an endpoint → mitigated by reviewing tests and adding assertions where absent.

## BDD Scenarios (Given-When-Then)
1. **Create course invalid title**
   - Given a teacher session
   - When POST `/api/teaching/courses` with blank title
   - Then response is 400 with `detail` == `invalid_title`
2. **Update course empty payload**
   - Given teacher owns a course
   - When PATCH `/api/teaching/courses/{course_id}` with empty JSON
   - Then response is 400 with `detail` == `empty_payload`
3. **Reorder sections invalid unit**
   - Given teacher session
   - When POST `/api/teaching/units/not-a-uuid/sections/reorder`
   - Then response is 400 with `detail` == `invalid_unit_id`
4. **Reorder sections duplicate IDs**
   - Given teacher owns unit with sections
   - When POST reorder with duplicates
   - Then response is 400 with `detail` == `duplicate_section_ids`
5. **Users search short query**
   - Given teacher session
   - When GET `/api/users/search?q=x&role=student`
   - Then response is 400 with `detail` == `q_too_short`

## Tasks
1. Update `api/openapi.yml` error documentation for affected endpoints.
2. Extend/adjust pytest cases to assert new snake_case detail values.
3. Modify backend route handlers to emit the snake_case detail strings.
4. Run targeted pytest modules to confirm all scenarios.
5. Summarize change for PR (notes + changelog entry if required).

## Test Plan
- `python -m pytest backend/tests/test_teaching_courses_api.py`
- `python -m pytest backend/tests/test_teaching_sections_api.py`
- `python -m pytest backend/tests/test_users_search_api.py`
