# Plan: Members UI without dummy data

Context
- The members page `/courses/{id}/members` still used dummy student data for the search UI.
- We already have a contract and API for directory search: `GET /api/users/search`.
- Goal: Remove all dummy data from this page and wire to the API end-to-end.

User Story
- As a teacher, I can search real students by name and add/remove them as course members. The page should not display or depend on hard-coded dummy users.

BDD Scenarios
- Given a teacher on the members page, when typing at least two characters, then the UI shows candidates returned by `GET /api/users/search` and excludes already enrolled students.
- Given a one-character query, when searching, then the UI shows no candidates (API not called).
- Given a teacher adds or removes a member, then the UI re-renders from the API (no local dummy state).

API Contract
- `GET /api/users/search` already exists in `api/openapi.yml` and returns `{sub, name}` with cache control `no-store`.
- No schema or migration changes are needed.

Implementation Notes
- Include `users_router` in the FastAPI app to expose `/api/users/search`.
- Replace `_ALL_STUDENTS` usage with an in-process API call from the members search handler.
- Remove `_DUMMY_MEMBERS_STORE` and the unused `_handle_member_change` fallback.
- Keep CSRF enforcement and teacher-only gates.

Tests (TDD)
- Add UI tests:
  - Search uses API and excludes existing members.
  - Too-short query returns empty results without calling the API.

Security
- No caching for search responses; SSR members page remains `private, no-store`.
- CSRF enforced on add/remove.

Risks
- The initial list scan for course title remains (limit=50). This is unrelated to members search and will be addressed by adding a direct `GET /api/teaching/courses/{id}` later.

