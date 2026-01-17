# Plan: Textareas are vertically too small (students + teachers)
Stand: 2026-01-16
Status: DONE (implemented 2026-01-17)

## Implementation (done)
- Learner answer textarea (`text_body`) renders with `class="form-textarea"` and `rows="5"` (and stays non-`required` to allow switching to Upload mode).
- Teacher authoring textareas render with explicit defaults:
  - Material Markdown (`body_md`): `rows="12"`
  - Task instruction (`instruction_md`): `rows="10"`
  - Task AI context (`teacher_context_md`): `rows="6"`
- Regression guard: `TextAreaField` now always includes `form-textarea`, so future forms don’t accidentally fall back to browser-default textarea sizing.
- Tests were added/updated to lock this behavior in.

## Why
- Learner and teacher textareas often render at the browser default (`rows=2`) which shows only ~2–3 lines and feels broken for longer answers / Markdown.
- Root cause is inconsistent markup: many `<textarea>` use `class="form-input"` (or no textarea-specific defaults), while our stylesheet expects `.form-textarea` for `min-height` + `resize`.
- Goal: make textarea sizing **consistent, accessible, and maintainable** by rendering them through our form components (single source of truth).

## User Story
- As a student, I want a sufficiently tall answer field, so I can see and edit my solution comfortably.
- As a teacher, I want sufficiently tall Markdown/instruction fields when creating/editing materials and tasks, so authoring is efficient.

## Acceptance Criteria
- All user-facing textareas in learner submission forms and teacher authoring forms have:
  - a consistent textarea class (`form-textarea`) and
  - an explicit `rows` default (so the UI is not dependent on browser defaults).
- Concrete defaults:
  - Learner `text_body`: `rows=5` (keeps the unit page compact; reduces layout jump when switching Text ↔ Upload)
  - Teacher `body_md`: `rows=12`
  - Teacher `instruction_md`: `rows=10`
  - Teacher `teacher_context_md`: `rows=6`
- Textareas remain resizable (`resize: vertical`) and keyboard accessible.
- No API / OpenAPI change required (pure SSR/CSS refactor).

## BDD Scenarios (Given/When/Then)
### Learner UI (task submission)
1) Given a learner opens a unit page with tasks, When the submission form renders in SSR, Then the `text_body` textarea has `class` containing `form-textarea` and `rows="5"`.
2) Given the learner switches to upload mode, When the form is submitted, Then the browser does not block submission because the textarea is hidden (textarea must not be HTML-`required`).

### Teacher UI (materials/tasks create + edit)
3) Given a teacher opens “Material anlegen”, When the Markdown textarea renders, Then it has `class` containing `form-textarea` and `rows="12"`.
4) Given a teacher opens “Aufgabe anlegen”, When the instruction and teacher-context textareas render, Then both have `class` containing `form-textarea` and `rows="10"` / `rows="6"`.
5) Given a teacher opens “Material/Aufgabe bearbeiten”, When the edit form renders, Then the corresponding textareas also have consistent class + rows.

## Design (long-term consistency)
### Defaults (final)
- Learner `text_body`: `rows=5`
- Teacher `body_md` (Markdown): `rows=12`
- Teacher `instruction_md`: `rows=10`
- Teacher `teacher_context_md`: `rows=6`

Rationale:
- Students need a medium field to start (answers vary) while keeping the unit page compact.
- The text/upload toggle should not cause a large layout jump; `rows=5` is a deliberate compromise.
- Teachers write longer Markdown; instruction is typically shorter than full material text.
- Teacher context is usually short but should not feel cramped.

### Code Changes (implemented)
1) Form component:
   - `TextAreaField.render(...)` always includes `form-textarea` to prevent accidental regressions.
2) SSR HTML:
   - Explicit `rows` + `form-textarea` for learner and teacher textareas in `backend/web/main.py` (keeps names/maxlength/required semantics).
3) Unit forms:
   - Unit edit summary is rendered with `form-textarea` and an explicit small default (`rows=3`).

### Security / Privacy Notes
- No new data is stored; this is a UI-only change.
- Ensure teacher-only fields remain teacher-only (no exposure change).

## TDD Plan (Red → Green → Refactor)
1) Red: Add/adjust UI tests to assert textarea defaults:
   - Learner: `text_body` has `form-textarea` + `rows=5`, and is not `required`.
   - Teacher: `body_md` (`rows=12`), `instruction_md` (`rows=10`), `teacher_context_md` (`rows=6`) have `form-textarea` + explicit rows.
2) Green: Implement minimal component refactor so tests pass:
   - Use `TextAreaField` consistently in SSR rendering paths.
   - Apply explicit `rows` per field.
3) Refactor: Remove any remaining ad-hoc textarea markup in these flows and keep styles consistent.

## Follow-ups (optional)
1) Do we want a max height (e.g. via CSS) for very large textareas, or leave it fully resizable?
2) Do we want to actively reduce layout jumps when switching Text ↔ Upload (e.g. matching approximate heights), or accept the small jump from `rows=5`?
