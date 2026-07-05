# Architecture Rules

Status: Active
Owner: Produktverantwortlicher
Local checks: `make test-import-boundaries`, `make test-architecture-boundaries`, `make harness-minimum`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`; `make verify` führt Import- und Architekturgrenzen als harte Gates aus.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/plan/2026-07-02-import-inventory-boundaries.md`, `docs/plan/2026-07-02-architecture-boundary-rules.md`
Review cadence: monatlich

## Zweck
Diese Regeln beschreiben die Zielrichtung für Import- und Architekturgrenzen. Die ausführbaren Gates blockieren neues Wachstum in Import- und Architektur-Schulden.

## Importregeln
- Der Docker-Ist-Zustand startet package-orientiert mit `backend.web.main:app`.
- Produktiver Web-Code importiert eigene Web-Module über `backend.web.*`; flache `routes.*`, `components` und `main`-Runtime-Starts sind keine erlaubte neue Architektur.
- Dockerfile und Compose dürfen das Backend nicht an mehrere Python-Package-Orte kopieren oder mounten. Der Backend-Code liegt unter `/app/backend`.
- Tests dürfen keine lokalen `sys.path`-Manipulationen hinzufügen.
- Bounded Contexts bleiben explizit: Web-Adapter dürfen Use Cases und Repositories nutzen; Use Cases kennen FastAPI, Request, Response und Router nicht.
- FastAPI-App-Aufbau gehört in kleine Composition-Module. `backend/web/main.py` bleibt der Runtime-Entrypoint; neue App-Shell-, Static- und Router-Wiring-Logik soll nicht weiter als lokale Sonderlogik in diese Datei wachsen.

## Ausführbare Architekturgrenzen
`make test-architecture-boundaries` führt `backend.tools.architecture_boundary_scan` gegen `docs/harness/ARCHITECTURE_BOUNDARY_BASELINE.json` aus.

- Use Cases und Services dürfen FastAPI nicht importieren.
- Direkte DB-Zugriffe aus Web-Adaptern sind nicht erlaubt; `backend/web/db_cursor.py` ist die genehmigte Infrastrukturgrenze.
- Direkte Supabase-Client-Erzeugung aus Web-Adaptern ist nicht erlaubt; `backend/web/storage_wiring.py` ist die genehmigte Storage-Wiring-Grenze.
- Security Guards sollen in zentralen Guard-/Adaptermodulen landen; Rollenprüfungen liegen in `backend/web/security/guards.py`, neue Routen sollen keine neuen privaten Authz-Sonderfälle ausprägen.
- Serialisierung soll über Read Models, DTOs oder klar benannte Mapper laufen; Serializer dürfen keine privaten Route-Helper importieren.

## Gate-Regel
`make test-import-boundaries` vergleicht die aktuelle Import-Schuld mit `docs/harness/IMPORT_BOUNDARY_BASELINE.json`. `make test-architecture-boundaries` vergleicht Clean-Architecture-Schuld mit `docs/harness/ARCHITECTURE_BOUNDARY_BASELINE.json`. Ein Anstieg bedeutet: neue Schuld wurde eingeführt oder eine genehmigte Infrastrukturgrenze wurde nicht im Scanner modelliert.

## Aktueller Null-Baseline-Stand
- `flat_routes_imports`: 0
- `flat_components_imports`: 0
- `backend_web_routes_imports`: 0
- `sys_path_mutations`: 0
- `usecase_fastapi_imports`: 0
- `service_fastapi_imports`: 0
- `web_direct_db_connects`: 0
- `web_direct_supabase_client_creates`: 0
