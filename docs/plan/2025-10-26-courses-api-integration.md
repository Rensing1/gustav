Title: Connect SSR Courses Page to DB via API

Context
- Goal: The “Kurse” page should display real DB-backed courses and allow creating new ones using the public API, not private repos.
- Scope: SSR /courses (GET, POST). No API contract or schema changes required; endpoints already exist in api/openapi.yml.

User Story
- As a teacher, I want to see my existing courses on the Courses page and create a new course so I can manage my classes.

BDD Scenarios
- Given a teacher is logged in, when they open /courses, then the page calls GET /api/teaching/courses and renders the returned list with a pager.
- Given a teacher has a valid CSRF token, when they submit the create form with a non-empty title, then the UI calls POST /api/teaching/courses and shows the new course in the list (HTMX partial or PRG redirect).
- Given a teacher submits the create form with an empty title or invalid input, then the UI shows a validation error without redirecting (HTMX reswap) and preserves inputs.
- Given a non-teacher (student) visits /courses, then they are redirected to / (UI policy).

API Contract (unchanged)
- GET /api/teaching/courses: List courses for current user (teacher: owner; student: memberships), parameters: limit (1..50), offset (>=0), 200 → [Course]
- POST /api/teaching/courses: Create a course (teacher only), 201 → Course; 400 → { error: bad_request, detail: invalid_input }; 403 → forbidden

DB Migration (unchanged)
- Courses table and RLS already exist (see supabase/migrations/20251020150101_teaching_courses.sql and RLS policies in 20251020154107_teaching_rls_policies.sql).

Test Strategy (TDD)
- Reuse existing UI tests that seed via the API and assert SSR rendering: backend/tests/test_teaching_courses_ui.py
- These tests already validate: role gate, CSRF, create PRG & HTMX behaviors, XSS escaping, cache headers, pagination clamp.

Implementation Notes
- Switch /courses (GET) to call GET /api/teaching/courses with httpx + ASGITransport, forwarding the session cookie.
- Switch /courses (POST) to call POST /api/teaching/courses, keep CSRF at UI boundary. On HTMX, return updated list partial + OOB form; otherwise PRG redirect.
- Keep UI stable for current tests; no template changes required.

Security
- CSRF remains enforced at the UI boundary for the HTML form.
- API uses authenticated cookie session and DB RLS.

Open Questions / Future Work
- Add HTMX delete/edit wired to API endpoints (patch/delete) to remove the remaining dummy delete handler.
- Surface API validation details more granularly in the UI (subject/term constraints) if needed.

