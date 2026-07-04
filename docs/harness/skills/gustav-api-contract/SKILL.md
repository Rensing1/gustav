---
name: gustav-api-contract
description: Enforce OpenAPI-first API work, route-surface classification, contract tests, and breaking-change decisions.
---

## Purpose
Protect `api/openapi.yml` as the source of truth for public API behavior.

## Trigger
Use this skill when the task mentions OpenAPI, API contract, response shape, route-surface classification, or breaking API behavior.

## Allowed Actions
- Inspect OpenAPI entries and API contract tests.
- Classify routes as public API, BFF/internal, H5P service, auth bridge, health/ops, active UI, or retired UI.
- Require decision entries for breaking changes.

## Prohibited Actions
- Do not approve breaking API changes.
- Do not treat BFF or legacy UI drift as invisible.
- Do not change API behavior without tests.

## Stop and Escalation Criteria
Escalate breaking changes, role-model changes, privacy changes, and any unclear public API semantics to the product owner.

## Verification
Run `.venv/bin/pytest -q backend/tests/test_openapi_no_null_type.py backend/tests/test_openapi_security_headers.py backend/tests/test_openapi_internal_flags.py` and any affected contract tests.

## Eval Status
manual forward-tested in `docs/harness/SKILL_EVALS.md`.

## Review Date
2026-08-02

## Risk and Tool Access Notes
Contract guidance only. No migrations, production mutation, destructive actions, or autonomous product decisions.
