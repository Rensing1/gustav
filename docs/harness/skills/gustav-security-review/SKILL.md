---
name: gustav-security-review
description: Review authn/authz, RLS, CSRF, uploads, privacy logging, unsafe defaults, and PII/secret risks.
---

## Purpose
Make security and privacy risks explicit before a change is treated as safe.

## Trigger
Use this skill when the task mentions security review, authz, RLS, CSRF, uploads, privacy logging, secrets, PII, or unsafe defaults.

## Allowed Actions
- Inspect security-sensitive code and tests.
- Require positive and negative tests for security behavior.
- Identify missing security gates and residual risks.

## Prohibited Actions
- Do not authorize weaker guards.
- Do not handle real secrets or personal data.
- Do not decide privacy, retention, deletion, or export policy.

## Stop and Escalation Criteria
Escalate any security exception, privacy tradeoff, cross-tenant risk, migration/RLS change, or production-impacting behavior to the product owner.

## Verification
Run `.venv/bin/pytest -q backend/tests/test_config_security.py backend/tests/test_privacy_logging_contract.py` plus targeted security tests for the affected flow.

## Eval Status
manual forward-tested in `docs/harness/SKILL_EVALS.md`.

## Review Date
2026-08-02

## Risk and Tool Access Notes
Security review workflow. No secret access, production mutation, migrations, destructive actions, or unreviewed network access.
