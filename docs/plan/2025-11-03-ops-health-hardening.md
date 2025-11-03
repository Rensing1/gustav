# Plan: Harden ops health + membership delete

Context
- Review identified two improvements:
  1) Service‑DSN fallback in teaching repo should be restricted to test/dev.
  2) OpenAPI for `GET /internal/health/learning-worker` should remove "metrics" wording and include examples.

Goals
- Security: Disallow accidental RLS bypass in prod/stage even when flag is set.
- API: Align contract text and provide client examples.
- Tests: Cover RLS delete policy and environment guard logic.

Changes
- Teaching repo: add `_service_fallback_allowed()`; require `ALLOW_SERVICE_DSN_FOR_TESTING=true` and `GUSTAV_ENV in {dev,test,local,ci}` or `PYTEST_CURRENT_TEST`.
- Add warning logs when fallback is used/blocked.
- OpenAPI description refined; examples for healthy/degraded added.
- Tests:
  - migration: owner vs non‑owner delete under RLS.
  - teaching: unit test matrix for fallback guard.
- Makefile: `.SILENT` now toggleable via `VERBOSE=1`.

Out of scope
- No behavior change to worker internals or job queue; health probe remains minimal.
