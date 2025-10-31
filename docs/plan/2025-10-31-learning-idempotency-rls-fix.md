# Plan: Learning submissions Idempotency + RLS fix

## Kontext
- Reported regression: Idempotent POSTs to `/api/learning/.../submissions` return 500 when the request races with itself.
- Root cause: `DBLearningRepo.create_submission` calls `conn.rollback()` on `UniqueViolation`, then reuses the existing submission. The rollback clears the session GUC `app.current_sub`, so the follow-up `SELECT` hits RLS and fails.
- Observed by automated review; reproducible with repeated POST carrying identical `Idempotency-Key`.

## Ziele
1. Preserve Row Level Security context after a rollback so the retry `SELECT` succeeds.
2. Provide automated regression coverage for idempotent retries.
3. Document the gotcha for future repo authors.

## Nicht-Ziele
- No broader refactor of the repo pattern.
- No change to public API contract (still returns 201 with existing submission).

## Umsetzung
1. Write regression test in `backend/tests/test_learning_submissions_idempotency_header.py` to POST twice with same token; expect 201 + same submission id.
2. Adjust `DBLearningRepo.create_submission` to re-run `_set_current_sub` after `conn.rollback()` and before querying for the existing row.
3. Update `docs/references/learning.md` (RLS section) with note about re-seeding `app.current_sub` after rollbacks.

## Risiken / Mitigation
- Missing test DB: keep dependency guard via `_require_db_or_skip`.
- Ensure we don't forget to commit transaction after re-query.

## Tests
- `.venv/bin/pytest -q backend/tests/test_learning_submissions_idempotency_header.py`
