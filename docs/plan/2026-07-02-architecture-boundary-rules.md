# Architecture Boundary Rules

Status: Implemented as first PR 12 slice in working tree
Owner: Produktverantwortlicher
Local checks: `make test-architecture-boundaries`, `.venv/bin/pytest -q backend/tests/test_architecture_boundary_gate_contract.py`
CI status: `make verify` führt `make test-architecture-boundaries` als hartes Gate aus; `make harness-minimum` prüft den Contract-Test.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/harness/ARCHITECTURE_RULES.md`
Review cadence: nach jedem Architektur- oder Web-Adapter-Refactor

## Zweck
PR 12 macht ausgewählte Clean-Architecture-Regeln ausführbar. Use Cases und Services dürfen FastAPI nicht importieren. Direkte DB- und Supabase-Client-Zugriffe aus Web-Adaptern werden als bestehende Schuld gezählt und dürfen nicht wachsen.

## User Story
Als Produktverantwortlicher will ich, dass Architekturgrenzen nicht nur in Dokumenten stehen, sondern bei Refactorings automatisch geprüft werden, damit neue Web-/DB- und Framework-Kopplungen früh sichtbar werden.

## BDD-Szenarien
- Given ein Use Case importiert `fastapi`, when `make test-architecture-boundaries` läuft, then schlägt das Gate fehl.
- Given ein Service importiert `fastapi`, when das Gate läuft, then schlägt es fehl.
- Given ein Web-Adapter fügt einen neuen direkten `psycopg.connect`-Zugriff hinzu, when das Gate läuft, then wächst `web_direct_db_connects` über die Baseline und das Gate schlägt fehl.
- Given ein Web-Adapter erzeugt einen weiteren Supabase-Client direkt, when das Gate läuft, then wächst `web_direct_supabase_client_creates` über die Baseline und das Gate schlägt fehl.

## Teststrategie
- Rot: `backend/tests/test_architecture_boundary_gate_contract.py` forderte Make-Target, Scanner, Baseline und dokumentierte Regeln.
- Grün: `backend/tools/architecture_boundary_scan.py` scannt Python-ASTs, setzt harte Nullgrenzen für FastAPI-Imports in Use Cases/Services und vergleicht bestehende Web-DB-/Supabase-Schuld gegen `docs/harness/ARCHITECTURE_BOUNDARY_BASELINE.json`.
- Refactor: `docs/harness/ARCHITECTURE_RULES.md`, `QUALITY_GATES.md` und `TEST_PORTFOLIO.md` dokumentieren das Gate.

## Evidenz
- Rot: `.venv/bin/pytest -q backend/tests/test_architecture_boundary_gate_contract.py` → 5 failed, weil Target, Scanner, Baseline und Doku fehlten.
- Grün: `.venv/bin/pytest -q backend/tests/test_architecture_boundary_gate_contract.py` → 5 passed.
- Grün: `make test-architecture-boundaries` → `architecture-boundary-scan-ok`.
- Grün: `make harness-minimum` → 98 passed; Docker-Compose-Konfiguration valide.

## Offene Arbeit
- Bestehende direkte DB-Zugriffe aus Web-Adaptern schrittweise in Repositories, Query-Services oder zentrale Infrastruktur verschieben und Baseline senken.
- Security Guards aus großen Route-Dateien extrahieren.
- Serialisierung/Read Models so trennen, dass Route-Helper nicht als private Domain-Abhängigkeit verwendet werden.
