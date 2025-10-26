# Plan: UI error handling for unit editing & sections

## Context
- Code Review (8ced582) identified missing error propagation in the teacher UI.
- Edit form redirects even when the API PATCH fails (e.g., validation).
- Section create/delete/reorder fall back to silent success despite API errors.

## Goals
1. Surface backend errors to teachers in the SSR UI (no silent success).
2. Extend coverage to assert CSRF + API error handling.
3. Update documentation (Architecture + Changelog) to reflect the behavior.

## Steps (TDD)
1. Add failing tests:
   - Unit edit POST returns 400/error fragment when API rejects payload.
   - Section create/delete/reorder bubble up API failure (expects 4xx).
2. Implement minimal changes:
   - Capture upstream response codes; render error messages.
   - Ensure sortable JS handles HX error triggers gracefully.
3. Update documentation and notes for the new behavior.
4. Run `.venv/bin/pytest -q backend/tests/test_teaching_units_ui_prefill.py backend/tests/test_teaching_sections_ui.py`.

## Acceptance
- Tests in step 4 pass.
- Teachers receive meaningful feedback on API errors without stale redirects.
