Title: Student Unit UI — Cards per Item and Markdown Rendering
Date: 2025-10-27
Owner: Felix + Teacher/Dev Pair

Context
- Current student unit page (`/learning/courses/{course_id}/units/{unit_id}`) renders all released materials and tasks inside a single section card with plain text for markdown bodies.
- Desired: Each material and each task appears as its own card. Markdown in materials should render as HTML (safe), improving readability.
- No backend data shape changes required; we consume the existing Learning API.

User Story
- As a student, I want each material and each task to be presented in its own visual card so that I can quickly scan content, and I want markdown text in materials to render properly so headings, bold and emphasis are readable.

BDD Scenarios
- Given a course unit with one released section that contains one markdown material and one task
  When I open the student unit page
  Then I see two separate cards: one material card and one task card
  And the material body shows rendered markdown (e.g., ** → <strong>, * → <em>)

- Given multiple released sections
  When I open the student unit page
  Then materials and tasks remain grouped by their sections visually (one horizontal rule between section groups)
  And section titles are not shown to the student

- Given a released section with no materials and no tasks
  When I open the student unit page
  Then I see a neutral “Noch keine Inhalte freigeschaltet.” message

API Contract (openapi.yml)
- No changes. The SSR page continues to call
  GET /api/learning/courses/{course_id}/units/{unit_id}/sections?include=materials,tasks
  Existing contract already includes markdown fields: `materials[].body_md` and `tasks[].instruction_md`.

Database Migration
- None. This is a pure presentation change.

Implementation Notes
- Add a minimal, safe markdown renderer for a subset used in materials (headings, strong, em, basic paragraphs). Escape first, then replace patterns to avoid XSS. Keep KISS; no external dependency required.
- Update SSR route to render each material with `MaterialCard` and each task with `TaskCard`.
- Keep private, no-store cache headers.

Testing (TDD)
- Add a failing UI test asserting:
  - presence of `surface-panel material-entry` and `surface-panel task-panel` for the two items
  - markdown rendered to <strong>/<em>
  - raw `**` not present in the HTML

Risks / Security
- Markdown rendered only from teacher-authored content; escape-before-replace ensures tags are limited to the ones we emit (<strong>, <em>, <h1..h6>, <p>, <br>). No raw HTML passthrough.

Out of scope
- Submission forms and history within TaskCard
- Extended markdown (links, code blocks) — can be iterated later.

