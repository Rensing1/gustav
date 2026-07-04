---
name: gustav-pr-fix
description: Read an existing PR-fix plan, verify open findings, design tests first, and implement minimal fixes.
---

## Purpose
Turn actionable review findings into small, verified repairs while preserving TDD and Clean Architecture boundaries.

## Trigger
Use this skill when the task mentions PR-fix plans, review feedback fixes, or addressing actionable PR findings.

## Allowed Actions
- Read the relevant PR-fix plan and affected source files.
- Verify that each finding still applies.
- Write failing tests before implementation.
- Make minimal scoped fixes after the red test is confirmed.

## Prohibited Actions
- Do not implement without a failing test unless the product owner explicitly grants an exception.
- Do not revert unrelated changes.
- Do not broaden scope beyond the reviewed finding.

## Stop and Escalation Criteria
Stop when a finding is ambiguous, product-facing, privacy-relevant, security-exception-related, or requires a migration or breaking API change.

## Verification
Run the targeted regression tests first, then the affected harness or verify gate.

## Eval Status
manual forward-tested in `docs/harness/SKILL_EVALS.md`.

## Review Date
2026-08-02

## Risk and Tool Access Notes
May guide code changes only under TDD and human review. No autonomous migrations, production mutation, or destructive actions.
