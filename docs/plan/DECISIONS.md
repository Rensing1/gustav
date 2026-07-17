# Decisions

Status: Draft
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: Keine anbietergebundene CI erforderlich; die lokalen Make-Ziele sind maßgeblich
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich während des Harness-Refactors

## Zweck
Dieses Dokument ist ein leichtgewichtiges Entscheidungslog, bis ein vollständiger ADR-Prozess eingeführt ist.

## Entscheidungen
| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-07-02 | PR 1 darf direkt auf `master` umgesetzt werden. | Der Produktverantwortliche hat dies im Arbeitsverlauf ausdrücklich freigegeben. |
| 2026-07-02 | `make harness-signals` ist zunächst warning-only. | PR 1 soll Sichtbarkeit schaffen, ohne noch instabile Struktur- und Runtime-Signale hart zu blockieren. |
| 2026-07-02 | `make verify` bleibt deterministisches Hard-Gate; echte Supabase-/OpenAI-/Browser-E2E-Smokes laufen über `make test-full-prod-like`. | Green hard gates sollen warning-clean und lokal reproduzierbar sein. Ein nicht gestarteter LLM-Endpunkt ist eine opt-in-Umgebungsabhängigkeit, kein Code-Warning. |
