# Skills

Status: Draft
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich während des Harness-Refactors

## Zweck
Dieses Dokument inventarisiert repo-gesteuerte GUSTAV-Skills. Persönliche lokale Skills können beim Arbeiten helfen, sind aber keine autoritative GUSTAV-Quelle.

## Governance
Ein Skill darf nur Entscheidungen automatisieren, die durch `docs/harness/AUTONOMY_MATRIX.md` bereits erlaubt sind. Toolzugriff, Netzwerkzugriff, Secrets, Migrationen, Produktionsmutation und destruktive Aktionen müssen als Risiko sichtbar sein.

## Inventar
| Skill | Source path | Trigger phrases | Allowed actions/tools | Prohibited actions | Stop/escalation rules | Verification command(s) | Eval status | Activation status | Review cadence/date | Risk notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gustav-plan-status | `docs/harness/skills/gustav-plan-status/SKILL.md` | Planstatus, stale plan, docs/plan index | Dokumente lesen, Statusvorschläge machen, Dokumentationsupdates vorbereiten | Produktcode, Migrationen, Secrets, Löschungen | Unklare Produktentscheidung an den Produktverantwortlichen | `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py` | manual forward-tested | active | monatlich, 2026-08-02 | Kein Netzwerk, keine produktive Mutation |
| gustav-harness-gardener | `docs/harness/skills/gustav-harness-gardener/SKILL.md` | Harness-Gardening, stale harness, tech debt | Harness-Dokumente prüfen und kleine Doku-Korrekturen vorbereiten | Gates schwächen, historische Entscheidungen löschen | Gate- oder Autonomieänderungen eskalieren | `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py` | manual forward-tested | active | monatlich, 2026-08-02 | Kein Netzwerk, keine Secrets |
| gustav-pr-review | `docs/harness/skills/gustav-pr-review/SKILL.md` | PR review, branch review, Review gegen master | Diff lesen, Risiken priorisieren, Review-Dokument schreiben | Code ändern, Findings ohne Evidenz erfinden | Security/API/DB/Privacy-Funde markieren | `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py` | manual forward-tested | active | monatlich, 2026-08-02 | Nur Analyse; keine Mutation |
| gustav-pr-fix | `docs/harness/skills/gustav-pr-fix/SKILL.md` | PR-fix, review feedback fix | Bestehende Findings prüfen, Tests entwerfen, minimale Fixes planen | Blindes Umsetzen ohne roten Test, fremde Änderungen revertieren | Unklare Findings oder Produktentscheidungen eskalieren | `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py` | manual forward-tested | active | monatlich, 2026-08-02 | Codeänderungen nur nach TDD und Review |
| gustav-api-contract | `docs/harness/skills/gustav-api-contract/SKILL.md` | OpenAPI, API contract, breaking change | OpenAPI und Contract-Tests prüfen, Route-Surface planen | Breaking Changes entscheiden | Breaking API an den Produktverantwortlichen eskalieren | `.venv/bin/pytest -q backend/tests/test_openapi_no_null_type.py backend/tests/test_openapi_security_headers.py backend/tests/test_openapi_internal_flags.py` | manual forward-tested | active | monatlich, 2026-08-02 | Keine Migrationen, keine Produktentscheidung |
| gustav-security-review | `docs/harness/skills/gustav-security-review/SKILL.md` | security review, CSRF, RLS, authz, privacy | Sicherheitsrisiken prüfen, negative und positive Tests fordern | Security-Ausnahmen autorisieren, Secrets lesen oder schreiben | Security-Tradeoffs an den Produktverantwortlichen eskalieren | `.venv/bin/pytest -q backend/tests/test_config_security.py backend/tests/test_privacy_logging_contract.py` | manual forward-tested | active | monatlich, 2026-08-02 | Keine Secrets, kein Netzwerk |
| gustav-route-map | `docs/harness/skills/gustav-route-map/SKILL.md` | route map, legacy route, retired UI | Routen klassifizieren, Legacy-Exit planen | Routen löschen ohne Characterization-Test | Aktive UI- oder API-Entscheidungen eskalieren | `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py` | manual forward-tested | active | monatlich, 2026-08-02 | Keine Laufzeitmutation |
