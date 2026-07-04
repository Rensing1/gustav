---
name: gustav-route-map
description: Classify web/API routes, identify retired legacy UI paths, and prepare route-map updates.
---

## Purpose
Make route ownership and legacy status visible before monolith splits or HTML/HTMX removal.

## Trigger
Use this skill when the task mentions route map, route-surface classification, legacy routes, retired UI, FastAPI HTML, or SvelteKit parity.

## Allowed Actions
- Inventory routes and classify their surface.
- Identify missing tests for retired or active routes.
- Propose route-map entries and removal order.

## Prohibited Actions
- Do not delete routes without characterization tests.
- Do not remove auth bridge, health, H5P, BFF/internal, or public API behavior accidentally.
- Do not decide SvelteKit parity without evidence.

## Stop and Escalation Criteria
Escalate active UI ownership, compatibility behavior, API behavior, auth behavior, and any uncertain retirement decision to the product owner.

## Verification
Run `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py` for governance updates and targeted route tests for behavior changes.

## Eval Status
manual forward-tested in `docs/harness/SKILL_EVALS.md`.

## Review Date
2026-08-02

## Risk and Tool Access Notes
Route analysis workflow. No production mutation, migrations, destructive actions, or route deletion without tests.
