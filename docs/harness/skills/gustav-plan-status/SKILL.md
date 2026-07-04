---
name: gustav-plan-status
description: Inspect GUSTAV planning documents for stale or missing status blocks and prepare documentation-only status updates.
---

## Purpose
Keep `docs/plan/` useful as searchable project memory without changing product behavior.

## Trigger
Use this skill when the task mentions plan status, stale plans, plan index maintenance, or `docs/plan/` cleanup.

## Allowed Actions
- Read `docs/plan/` and related harness documents.
- Identify missing, stale, or contradictory status blocks.
- Propose or prepare documentation-only updates.

## Prohibited Actions
- Do not edit product code.
- Do not change API, database, security, privacy, or pedagogy decisions.
- Do not delete historical plans without human review.

## Stop and Escalation Criteria
Stop and escalate to the product owner when a status update would imply a product decision, privacy decision, migration decision, or removal of historical knowledge.

## Verification
Run `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py` after changing harness or plan status documents.

## Eval Status
manual forward-tested in `docs/harness/SKILL_EVALS.md`.

## Review Date
2026-08-02

## Risk and Tool Access Notes
Documentation-only workflow. No network, secrets, migrations, production mutation, or destructive actions.
