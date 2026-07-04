---
name: gustav-harness-gardener
description: Find stale harness, roadmap, tech-debt, source, and skill documents, then prepare small correction PRs.
---

## Purpose
Keep the GUSTAV harness coherent, findable, and aligned with executable checks.

## Trigger
Use this skill when the task mentions harness gardening, stale harness documents, tech debt cleanup, skill inventory cleanup, or gate documentation.

## Allowed Actions
- Read and compare harness documents.
- Find broken references, stale review dates, missing metadata, and unclear gate descriptions.
- Prepare small documentation updates.

## Prohibited Actions
- Do not weaken hard gates.
- Do not change autonomy rules without explicit review.
- Do not delete debt or decisions without product-owner review.

## Stop and Escalation Criteria
Stop when a correction changes a rule instead of clarifying it. Escalate gate status changes, autonomy changes, and accepted-debt removal.

## Verification
Run `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py` after changing harness governance documents.

## Eval Status
manual forward-tested in `docs/harness/SKILL_EVALS.md`.

## Review Date
2026-08-02

## Risk and Tool Access Notes
Documentation-only workflow. No network, secrets, migrations, production mutation, or destructive actions.
