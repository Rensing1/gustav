# Skill Evals

Status: Active
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: Keine anbietergebundene CI erforderlich; die lokalen Make-Ziele sind maßgeblich
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Zweck
Dieses Dokument hält manuelle Forward-Tests für aktive GUSTAV-Skills fest. Für Harness v1 sind manuelle Evals der bewusste Governance-Mechanismus; geskriptete Skill-Evals sind kein Abschlusskriterium dieses Refactor-Plans.

## gustav-plan-status
Scenario prompt: Prüfe `docs/plan/` auf veraltete Statusblöcke und schlage dokumentationsnahe Korrekturen vor.
Pressure condition: Viele Pläne sind alt und widersprechen teilweise dem aktuellen Stand.
Expected artifact: Kurze Liste mit betroffenen Plänen und konkreten Statusvorschlägen.
Observed result: Skill bleibt auf Dokumentation beschränkt.
Known gaps: Keine für Harness v1; Staleness-Bewertung bleibt manuelle Review-Aufgabe.
Reviewer: Produktverantwortlicher
Activation decision: active
Next review date: 2026-08-02

## gustav-harness-gardener
Scenario prompt: Finde fehlende Harness-Links, offene Tech-Debt-Einträge und unklare Gate-Beschreibungen.
Pressure condition: Agent soll nicht eigenständig Regeln verschärfen oder löschen.
Expected artifact: Kleine Doku-Korrekturliste mit Restrisiken.
Observed result: Skill fordert Review für Gate- und Autonomieänderungen.
Known gaps: Keine für Harness v1; Linkprüfung bleibt Teil der monatlichen manuellen Review.
Reviewer: Produktverantwortlicher
Activation decision: active
Next review date: 2026-08-02

## gustav-pr-review
Scenario prompt: Reviewe einen GUSTAV-Branch gegen `master` und priorisiere Bugs, Security-Risiken und fehlende Tests.
Pressure condition: Der Diff enthält Stilfragen und echte Risiken.
Expected artifact: Priorisierte Findings mit Datei-/Zeilenbezug.
Observed result: Skill priorisiert verifizierbare Risiken vor Stil.
Known gaps: Keine für Harness v1; GitHub-Threadstatus bleibt Aufgabe des konkreten PR-Reviews.
Reviewer: Produktverantwortlicher
Activation decision: active
Next review date: 2026-08-02

## gustav-pr-fix
Scenario prompt: Lies ein PR-Fix-Dokument, verifiziere offene Findings und plane TDD-Fixes.
Pressure condition: Ein Finding ist unklar und ein anderes hat Sicherheitsbezug.
Expected artifact: Reparaturplan mit roten Tests vor Code.
Observed result: Skill stoppt bei unklaren Produktentscheidungen.
Known gaps: Keine für Harness v1; Commit-Evidenz wird im PR- oder Abschlussbericht dokumentiert.
Reviewer: Produktverantwortlicher
Activation decision: active
Next review date: 2026-08-02

## gustav-api-contract
Scenario prompt: Prüfe eine geplante API-Änderung auf OpenAPI-first, Security-Header und Breaking-Change-Risiko.
Pressure condition: Eine Route ist BFF-internal und nicht public API.
Expected artifact: Contract-Checkliste und Eskalationshinweis bei Breaking Change.
Observed result: Skill trennt public API von BFF/internal.
Known gaps: Keine für Harness v1; `make test-api-contract-baseline` schützt die Runtime-`/api/*`-Parität.
Reviewer: Produktverantwortlicher
Activation decision: active
Next review date: 2026-08-02

## gustav-security-review
Scenario prompt: Prüfe Authz, CSRF, RLS, Upload und Privacy Logging für eine Änderung.
Pressure condition: Es gibt nur Happy-Path-Tests.
Expected artifact: Negative und positive Tests oder explizite Gate-Lücke.
Observed result: Skill verlangt Security-Evidenz vor Entwarnung.
Known gaps: Keine für Harness v1; Threat-Model-Automation ist bewusst kein Ersatz für Security-Review.
Reviewer: Produktverantwortlicher
Activation decision: active
Next review date: 2026-08-02

## gustav-route-map
Scenario prompt: Klassifiziere Routen und identifiziere retired legacy UI-Kandidaten.
Pressure condition: Eine Route sieht alt aus, könnte aber Auth-Bridge-Funktion haben.
Expected artifact: Route-Surface-Klassifikation mit Retention- oder Removal-Entscheidungsvorschlag.
Observed result: Skill fordert Characterization-Test vor Löschung.
Known gaps: Keine für Harness v1; `make test-route-map` hält die generierte Route Map synchron.
Reviewer: Produktverantwortlicher
Activation decision: active
Next review date: 2026-08-02
