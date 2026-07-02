# Quality Gates

Status: Draft
Owner: Felix
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_test_strategy_docs_contract.py`
CI status: geplant
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich während des Harness-Refactors

## Zweck
Dieses Dokument beschreibt die geplanten Gate-Profile für den Harness-Refactor. Die Profile sollen lokale Entwicklung und CI angleichen, ohne teure oder externe Suites versehentlich in schnelle Checks zu mischen.

## Profile

### fast
Zweck: schnelles Feedback für die meisten Code- und Dokumentationsänderungen.

Geplanter Inhalt:
- In-Process-pytest ohne externe Dienste
- Domain- und Use-Case-Tests
- Adaptertests mit Fakes oder Mocks
- OpenAPI-/Contract-Tests, soweit sie keine laufenden Dienste brauchen
- Harness-Dokumentationsverträge

Initialer lokaler Befehl:
- `.venv/bin/pytest -q backend/tests/test_harness_test_strategy_docs_contract.py`

Zielzustand:
- Ein eigener Make-Target wie `make test-fast`.

### db-security
Zweck: Datenbank-, RLS-, Authz-, CSRF- und Migration-Sicherheit sichtbar machen.

Geplanter Inhalt:
- RLS-Tests gegen lokale Supabase-Struktur
- Migration- und Helper-Tests
- CSRF-positive und CSRF-negative Tests
- Authz-negative Tests für Schüler, Lehrer und Admin-Funktionen
- DB-DSN- und Mutationssicherheitsguards

Zielzustand:
- Ein eigener Make-Target wie `make test-db-security`.
- Tests mit echter DB-Abhängigkeit sind markiert oder anderweitig eindeutig inventarisiert.

### frontend-h5p
Zweck: Frontend- und H5P-Qualität als First-Class-Gate behandeln.

Geplanter Inhalt:
- `npm run check` im Frontend
- Vitest im Frontend
- Node-Tests im H5P-Service
- H5P-Verträge, soweit sie ohne Compose laufen

Zielzustand:
- Ein eigener Make-Target wie `make test-frontend-h5p`.
- Spätestens vor größeren Backend/API-Refactors ist dieses Profil Teil von `make verify`.

### full-prod-like
Zweck: produktionsnahe Integrationen prüfen.

Geplanter Inhalt:
- Supabase-Integration
- OpenAI-kompatibler Endpoint-Smoke
- Docker/Compose-Smoke
- Keycloak/Caddy/Web/H5P-E2E
- wenige Playwright- oder pytest-E2E-Kernreisen

Zielzustand:
- Ein eigener Make-Target wie `make test-full-prod-like`.
- Dieses Profil bleibt teuer und bewusst opt-in oder CI-staged.

## Harte Regeln
- Sicherheits-, Privacy-, Secret- und API-Security-Contract-Fehler blockieren sofort.
- Struktur-, Hotspot-, Route-Surface-, Import- und Skill-Governance-Signale dürfen anfangs Warnungen sein, müssen aber einen Härtungstermin haben.
- Externe Suites brauchen explizite Marker und ENV-Flags.
- Kein Gate darf lokale Sonderpfade nutzen, die in Produktion nicht gelten.

## Offene Umsetzung
- Exakte Make-Targets werden in einem separaten PR eingeführt, nachdem das Testportfolio inventarisiert ist.
- `db_read` und `db_write` werden erst dann harte Marker, wenn ihr Einsatz im Portfolio überprüft wurde.
- CI startet mit dem kleinsten verlässlichen Profil und erweitert die Matrix schrittweise.
