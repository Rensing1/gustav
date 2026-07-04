# Architecture Rules

Status: Draft
Owner: Produktverantwortlicher
Local checks: `make test-import-boundaries`, `make test-architecture-boundaries`, `make harness-minimum`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`; `make verify` führt Import- und Architekturgrenzen als harte Gates aus.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/plan/2026-07-02-import-inventory-boundaries.md`, `docs/plan/2026-07-02-architecture-boundary-rules.md`
Review cadence: monatlich während des Harness-Refactors

## Zweck
Diese Regeln beschreiben die Zielrichtung für Import- und Architekturgrenzen. Sie sind bewusst knapp und werden während der Refactor-PRs verschärft.

## Importregeln
- Der Docker-Ist-Zustand startet package-orientiert mit `backend.web.main:app`.
- Produktiver Web-Code importiert eigene Web-Module über `backend.web.*`; flache `routes.*`, `components` und `main`-Runtime-Starts sind keine erlaubte neue Architektur.
- Dockerfile und Compose dürfen das Backend nicht an mehrere Python-Package-Orte kopieren oder mounten. Der Backend-Code liegt unter `/app/backend`.
- Neue Tests sollen keine lokalen `sys.path`-Manipulationen hinzufügen, wenn bestehende zentrale Testkonfiguration ausreicht.
- Bounded Contexts bleiben explizit: Web-Adapter dürfen Use Cases und Repositories nutzen; Use Cases kennen FastAPI, Request, Response und Router nicht.
- FastAPI-App-Aufbau gehört in kleine Composition-Module. `backend/web/main.py` bleibt der Runtime-Entrypoint; neue App-Shell-, Static- und Router-Wiring-Logik soll nicht weiter als lokale Sonderlogik in diese Datei wachsen.

## Ausführbare Architekturgrenzen
`make test-architecture-boundaries` führt `backend.tools.architecture_boundary_scan` gegen `docs/harness/ARCHITECTURE_BOUNDARY_BASELINE.json` aus.

- Use Cases und Services dürfen FastAPI nicht importieren.
- Direkte DB-Zugriffe aus Web-Adaptern sind als bestehende Schuld inventarisiert und dürfen nicht wachsen.
- Direkte Supabase-Client-Erzeugung aus Web-Adaptern ist als bestehende Storage-Wiring-Schuld inventarisiert und darf nicht wachsen.
- Security Guards sollen in zentralen Guard-/Adaptermodulen landen; Rollenprüfungen liegen in `backend/web/security/guards.py`, neue Routen sollen keine neuen privaten Authz-Sonderfälle ausprägen.
- Serialisierung soll über Read Models, DTOs oder klar benannte Mapper laufen; Serializer dürfen keine privaten Route-Helper importieren.

## Warnsignal
`make test-import-boundaries` vergleicht die aktuelle Import-Schuld mit `docs/harness/IMPORT_BOUNDARY_BASELINE.json`. `make test-architecture-boundaries` vergleicht Clean-Architecture-Schuld mit `docs/harness/ARCHITECTURE_BOUNDARY_BASELINE.json`. Ein Anstieg bedeutet: neue Schuld wurde eingeführt oder die Baseline ist bewusst zu aktualisieren.

## Spätere Härtung
- PR 9 zentralisiert Test-Imports und senkt die Baseline für `flat_routes_imports`, `backend_web_routes_imports` außerhalb des Web-Adapters und `sys_path_mutations`.
