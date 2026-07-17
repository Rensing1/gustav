# Harness Minimum Implementation

Status: Implemented in working tree
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`, `make harness-minimum`
CI status: Keine anbietergebundene CI erforderlich; `make harness-minimum` ist der lokale Einstiegspunkt
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: nach Abschluss von PR 1

## Zweck
Dieser Plan dokumentiert die konkrete Umsetzung von PR 1 aus dem Harness-Engineering-Refactor.

## User Story
Als neuer GUSTAV-Agent oder Entwickler will ich innerhalb von fünf Minuten Regeln, Risiken, erlaubte Autonomie, Skills und lokale Checks finden, damit Refactors klein, testbar und reviewbar bleiben.

## BDD-Szenarien
- Given ein neuer Agent öffnet `docs/harness/INDEX.md`, when er PR-1-Regeln sucht, then findet er Read-Order, harte Gates, Warnsignale und Eskalationsregeln.
- Given ein Skill ist `active`, when der Harness geprüft wird, then existieren Source, Inventory und Manual-Forward-Test-Eintrag.
- Given ein Entwickler führt `make harness-minimum` aus, then laufen nur harte lokale PR-1-Safety-Checks.
- Given ein Entwickler führt `make harness-signals` aus, then werden Struktur-, Frontend-, H5P-, DB- und Docker-Signale sichtbar, aber PR 1 noch nicht blockiert.

## Umsetzung
- Rot: `backend/tests/test_harness_minimum_contract.py` beschreibt die fehlende Mindeststruktur.
- Grün: Dokumente, Skills, Plan-Memory und lokale Make-Ziele werden minimal ergänzt.
- Refactor: Nach Grün werden Redundanzen und Gate-Beschreibungen geglättet.

## Evidenz
Der erste Rotlauf zeigte erwartete Fehlschläge für fehlende Harness-Dokumente, Plan-Memory, Skill-Quellen, Skill-Inventar und lokale Make-Ziele. Die früher zusätzlich eingeführte anbietergebundene Automatisierung wurde später als nicht erforderliche Fehlannahme zurückgenommen.

Ausgeführte Checks:
- `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`: 8 passed.
- `.venv/bin/pytest -q backend/tests/test_harness_test_strategy_docs_contract.py backend/tests/test_makefile_targets.py backend/tests/test_harness_minimum_contract.py`: 12 passed.
- `make harness-minimum`: 63 passed und `docker compose config` OK.
- `make harness-signals`: Exitcode 0 mit Warnungen.
- `make -n harness-signals`: druckt den warning-only Shell-Block und führt keine Checks aus.

Warnungen aus `make harness-signals`:
- `verify-preflight-db` konnte die lokale DB nicht erreichen.
- `REQUIRE_DB_TESTS=1 pytest -q` scheiterte bei Collection, weil die lokale DB nicht erreichbar war.
- `frontend npm test` scheiterte mit `getaddrinfo EAI_AGAIN localhost`.
- `frontend npm run check`, H5P Node-Tests und `docker compose config` waren erfolgreich.

Privacy-Hinweis:
- Neu angelegte und berührte Harness-/Plan-Dateien wurden nach Klarnamen-Treffern durchsucht; die Suche fand keinen Treffer.

Review-Fixes:
- Für `docker compose config` wird lokal dieselbe `.env.example`-Struktur verwendet; ein externer Automatisierungsdienst ist dafür nicht erforderlich.
- `harness-minimum` und `harness-signals` vermeiden rekursive `$(MAKE)`-Aufrufe, damit `make -n` trocken bleibt.
- `SKILL_EVALS.md` wird im Contract-Test abschnittsbasiert geprüft statt über feste String-Fenster.
- `QUALITY_GATES.md` und die Dokumentköpfe beschreiben die lokalen Make-Targets nicht mehr als nur geplant.
