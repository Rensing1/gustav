# API Contracts

Status: Active
Owner: Produktverantwortlicher
Local checks: `make test-api-contract-baseline`, `make harness-minimum`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`; `make verify` führt `make test-api-contract-baseline` als hartes Gate aus.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Zweck
Dieses Dokument hält fest, dass `api/openapi.yml` die Quelle der Wahrheit für öffentliche API-Verträge ist. PR 10 macht diese Aussage ausführbar: `make test-api-contract-baseline` vergleicht die registrierten Runtime-`/api/*`-Routen mit `api/openapi.yml`.

## Route-Surfaces
Routen werden als public API, BFF/internal, H5P service, auth bridge, health/ops, active legacy UI oder retired legacy UI klassifiziert. Nicht-OpenAPI-Flächen werden nicht ignoriert, sondern in `docs/harness/ROUTE_MAP.md` geführt.

## Regeln
- API-Änderungen starten im OpenAPI-Vertrag.
- Undocumented `/api/*` runtime routes are gate failures; undocumented `/api/*` meint hier jede Runtime-Operation, die nicht in `api/openapi.yml` steht.
- Stale `/api/*`-Einträge in `api/openapi.yml`, die nicht mehr in der Runtime-App registriert sind, sind Gate-Fehler.
- Breaking Changes brauchen einen Eintrag in `docs/plan/DECISIONS.md`.
- Sicherheits- und Cache-Control-Header bleiben durch Contract-Tests sichtbar.
