# Live Dashboard Missing Scores

## Problem
In `/live` not all learners reliably show their latest evaluation in the class
overview. The backend summary currently pages helper rows by submission cells,
while the HTTP API pages by learners.

## Decision
Keep the public API unchanged and fix the data source. Introduce a bulk
teacher-owned helper that returns latest submission aggregates for the exact
learner page requested by the summary endpoint.

## TDD
1. Add a DB-backed regression test with more submission cells than the helper
   limit so a later learner would previously lose scores.
2. Add the helper + backend integration with the minimum code to make the test
   pass.
3. Re-run the targeted regression test and the nearby live-summary tests.
