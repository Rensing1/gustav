Title: Auto-refresh student history when vision/feedback completes

Context
- Problem: After submitting an upload, the UI shows a success banner but the history does not update automatically once the vision model extracts text or when feedback is generated.
- Goal: Automatically update the student’s submission history to reveal extracted text and later feedback without manual reload.

User Story
- As a student, after I submit an answer (text or upload), I want the history to update automatically as soon as the system extracts text and again when the feedback is ready, so I can see results without reloading the page.

BDD Scenarios
- Given a pending latest submission, when the history fragment loads, then it should include auto-polling and refresh every 2 seconds until the status is no longer pending.
- Given a latest submission with analysis_status completed, when the history fragment loads, then it must not include auto-polling attributes.
- Given a PRG back to the unit page right after submission and the latest is pending, when the page renders, then it should embed a polling history placeholder that refreshes into the final history fragment.

Design
- Use KISS polling with HTMX (hx-get + hx-trigger="every 2s") rather than SSE/WebSockets.
- Endpoint: Reuse existing HTML fragment GET /learning/courses/{course_id}/tasks/{task_id}/history.
  - The fragment wrapper gains data-pending="true|false".
  - While pending, the wrapper includes hx-get/hx-trigger/hx-target/hx-swap for self-refresh.
- Unit page: If the latest attempt (when show_history_for is active) is pending, render a polling placeholder instead of static entries.

API Contract
- No changes to api/openapi.yml (HTML SSR fragment only, existing Learning API already exposes analysis_status/feedback).

DB/Migrations
- No changes.

Tests (TDD)
- backend/tests/test_learning_ui_auto_refresh.py
  - test_history_fragment_autopolls_when_pending
  - test_history_fragment_stops_polling_when_completed
  - test_unit_page_embeds_autopoll_when_latest_pending

Risks / Follow-ups
- Consider UX signal while polling (spinner or subtle indicator).
- Optional: switch to teacher-like delta polling endpoint in the future to reduce payload size.

