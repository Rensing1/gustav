---
name: gustav-pr-review
description: Review a GUSTAV branch against master and persist prioritized findings with code references.
---

## Purpose
Produce a risk-focused review that prioritizes bugs, security gaps, regressions, architecture violations, and missing tests.

## Trigger
Use this skill when the task asks for a PR review, branch review, review against master, or review findings.

## Allowed Actions
- Inspect diffs, tests, docs, and affected contracts.
- Write prioritized findings with file and line references.
- Note missing verification and residual risk.

## Prohibited Actions
- Do not change code while reviewing.
- Do not invent findings without evidence.
- Do not focus on style unless it creates practical risk.

## Stop and Escalation Criteria
Escalate unclear product intent, privacy tradeoffs, breaking API changes, DB/RLS changes, and security decisions.

## Verification
Run targeted read-only checks where useful and report commands that were not run.

## Eval Status
manual forward-tested in `docs/harness/SKILL_EVALS.md`.

## Review Date
2026-08-02

## Risk and Tool Access Notes
Review-only workflow. No production mutation, migrations, destructive actions, or secret handling.
