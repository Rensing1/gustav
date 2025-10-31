---
title: "Auth Cache Headers & CSRF Guard Hardening"
date: 2025-10-31
owner: Felix
contributors:
  - Codex (assistant)
status: in_progress
context:
  summary: >
    Align authentication cache headers across code and documentation, remove
    redundant CSRF guard invocations, and reinforce security posture for file
    download endpoints. Work follows prior review findings.
  related_prs:
    - TBD
  references:
    - ../references/security_checklist.md
    - ../plan/2025-10-30-teaching-csrf-cache-contract.md
tasks:
  - id: tests-red
    description: >
      Extend FastAPI route tests to assert consistent Cache-Control headers
      (private, no-store) and to ensure CSRF guard call count is minimal.
    status: completed
  - id: impl-green
    description: >
      Update teaching/auth routes to standardize cache headers, deduplicate
      CSRF guard checks, and adjust supporting utilities (auth middleware,
      directory adapter efficiency).
    status: completed
  - id: docs-sync
    description: >
      Synchronise OpenAPI security notes and documentation with the updated
      behaviour; document cache policy and login rate-limiting requirements.
    status: completed
validation:
  tests_planned:
    - .venv/bin/pytest backend/tests/test_auth_cache_headers.py
    - .venv/bin/pytest backend/tests/test_teaching_materials_files_api.py::test_finalize_and_download_flow_enforces_checks
    - .venv/bin/pytest backend/tests/test_teaching_csrf_other_writes.py
    - .venv/bin/pytest backend/tests/test_learning_submissions_idempotency_header.py
    - .venv/bin/pytest backend/tests/test_openapi_write_security.py
  data_migrations: none
  rollback_plan: >
    Revert the commit touching FastAPI routes and specs; restore original cache
    semantics by applying git revert on the final commit if regressions are
    observed.
risks:
  - description: Inconsistent cache headers may break existing tests relying on exact strings.
    mitigation: Update affected assertions alongside implementation.
  - description: Removing redundant CSRF checks might accidentally drop required validation.
    mitigation: Ensure tests cover rejection paths before refactoring.
---
Plan drafted to satisfy governance requirement before implementation.
