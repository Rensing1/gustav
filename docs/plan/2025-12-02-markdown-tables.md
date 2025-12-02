Title: Markdown Tables in Student Materials
Date: 2025-12-02
Owner: Felix + Teacher/Dev Pair

Context
- Teachers author Materials within Sections using markdown (`kind='markdown'`, `body_md`).
- The current minimal renderer (`backend/web/components/markdown.py`) intentionally supports only headings, bold, italics and paragraphs.
- Tables written in common markdown syntax (e.g. GitHub-style with `|` and a separator row of `---`) are not recognised; they appear as plain text with pipe characters, which reduces readability for students.
- The renderer is used across the student-facing UI (material previews, task instructions, feedback, analysis explanations), so changes must preserve safety and avoid regressions.

User Story
- As a Teacher, I want to write tables in my Material markdown using standard markdown table syntax so that Students see structured HTML tables with clear columns and headings, making numeric comparisons (e.g. climate cost vs. climate payment per family) easy to understand.

Example Table (from a real Material)
```markdown
|                                              | Familie Groborz | Familie Jensen |
|----------------------------------------------|------------------|----------------|
| **Gesamtbelastung durch Emissionshandel 2025** | 1.153 €          | 1.509 €        |
| **Entlastung durch Klimageld von 139 €**       | × 3 = 417 €      | × 5 = 695 €    |
| **Entlastung durch Klimageld von 317 €**       | × 3 = 951 €      | × 5 = 1.585 €  |
```

BDD Scenarios
- Given a Material with `kind='markdown'` and a `body_md` that contains a valid markdown table (header row, separator row with `---`, data rows)
  And the Teacher has released the corresponding Section for a Course
  When a Student opens the unit detail page `/learning/courses/{course_id}/units/{unit_id}`
  Then the HTML output for this Material contains a `<table>` element with `<tr>` rows and `<th>`/`<td>` cells
  And the cells display the expected values (e.g. “Familie Groborz”, “1.153 €”)
  And bold markers inside cells (e.g. `**Gesamtbelastung durch Emissionshandel 2025**`) render as `<strong>` inside the table cells
  And no raw `|` or `---` markers remain in the rendered HTML outside of code blocks.

- Given a Material whose `body_md` contains normal prose before a table and additional prose after the table
  When the Student opens the unit detail page
  Then the prose renders as paragraphs with `<strong>`/`<em>` as today
  And the table appears as a separate `<table>` block in between
  And the original order (text – table – text) is preserved.

- Given a Material whose table cells include malicious HTML (e.g. `<script>` tags or images with `onerror` handlers)
  When the markdown is rendered to HTML
  Then the output still includes the semantic table structure (`<table>`, `<tr>`, `<th>`, `<td>`)
  But the malicious content is escaped and shown as text (e.g. `&lt;script&gt;`)
  And no executable script or unsafe attributes are injected into the DOM.

- Given a Material whose `body_md` contains pipe characters but does not form a valid markdown table (e.g. missing separator row or inconsistent column counts)
  When the Student opens the unit detail page
  Then the renderer does not emit broken `<table>` markup
  And the content is rendered as regular text/paragraphs so that the HTML remains valid and layout does not break.

- Given a Material with more than one markdown table in its `body_md`
  When the Student views the Material
  Then each table is rendered as its own `<table>` block
  And any text or headings between the tables still render correctly as paragraphs/headings.

Options Considered
- Option 1: Extend the existing minimal regex-based renderer to recognise markdown tables.
  - Pros: No new dependency; keeps the security model simple (escape first, then controlled tags); code remains fully under our control.
  - Cons: Table parsing via regex is error-prone; limited table dialect support; renderer becomes more complex to maintain and explain.

- Option 2 (Preferred): Replace the ad-hoc renderer implementation with a well-maintained markdown library that supports tables.
  - Pros: Table support comes “for free” alongside consistent handling of headings, emphasis and other inline elements; less custom parsing code; easier future extensions.
  - Cons: Introduces an external dependency; security model must be reviewed carefully (HTML escaping and sanitising must stay strict); requires regression tests for all current markdown usages.

- Option 3: Model tables as a separate structured Material type instead of relying purely on markdown.
  - Pros: Very explicit domain model for tabular content; enables future analytics or accessibility improvements on structured tables; safety remains trivial because we control all HTML generation.
  - Cons: Larger feature scope (new Material kind, API and DB changes, new UI for authoring tables); diverges from the simple “markdown in a textarea” authoring model.

API Contract (openapi.yml)
- No immediate changes for Option 2: existing fields `materials[].body_md` and `tasks[].instruction_md` remain the source of markdown.
- The Learning API for sections already exposes markdown bodies; SSR reads them and passes them through the renderer.
- If we later model structured tables as their own Material kind (Option 3), the API contract would need to be extended with an additional Material variant and a JSON structure for rows/cells.

Database Migration
- None for Option 2: markdown remains stored as plain text in `body_md`.
- Future Option 3 would require migrations to introduce a new Material kind and potentially a table-specific JSON column or related table.

Testing (TDD Plan)
- Add new failing tests around `render_markdown_safe` in `backend/tests/test_markdown_renderer.py` to cover:
  - Happy path table rendering (presence of `<table>`, `<tr>`, `<th>`, `<td>` and expected text content).
  - Mixed content (text + table + text) without breaking paragraphs/headings.
  - Escaping of malicious content inside table cells.
  - Non-table pipe usage handled as regular text.
- Add an integration test in `backend/tests/test_learning_unit_sections_ui_cards_markdown.py`:
  - Create a course/unit/section and a markdown Material containing the example table.
  - Release the section, open the student unit page, and assert that:
    - The material card HTML contains a `<table>` element.
    - The rendered HTML still contains the expected cell contents and no raw markdown table markers.

Implementation Notes (Option 2 Sketch)
- Introduce a markdown library dependency in the backend (e.g. a safe, FOSS markdown parser with table support).
- Configure the parser to:
  - Escape or ignore raw HTML input from teachers.
  - Enable a limited feature set (headings, strong/emphasis, paragraphs, line breaks, tables).
  - Optionally post-process the generated HTML through a small sanitizer that whitelists allowed tags and attributes.
- Replace the internals of `render_markdown_safe` to call the library while keeping the function signature and call sites unchanged.
- Keep the existing tests for headings and emphasis green while extending them with table coverage.

Risks / Security
- Introducing a markdown library must not weaken XSS protection; we continue to treat teacher-authored markdown as untrusted and only allow a small, whitelisted HTML subset.
- Any new tags (e.g. table-related) must be included in sanitising and CSS updates to ensure consistent styling and accessibility.

Out of Scope (for this iteration)
- Advanced markdown features such as nested tables, column spans, or interactive components.
- Dedicated UI components for authoring tables (Option 3).
- Changes to the Learning API or database schema.

