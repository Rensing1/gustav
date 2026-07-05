# Teststrategie

Status: Draft
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_test_strategy_docs_contract.py`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`; weitere Profile werden schrittweise ergänzt.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich während des Harness-Refactors

## Zweck
Diese Strategie beschreibt, welche Tests GUSTAV braucht und wofür sie zuständig sind. Das Ziel ist nicht maximale Testanzahl, sondern ein verständliches, schnelles und sicherheitsbewusstes Testportfolio.

Ein guter Test beantwortet mindestens eine dieser Fragen:
- Schützt er eine fachliche Regel?
- Schützt er einen öffentlichen Vertrag?
- Schützt er eine Sicherheits- oder Datenschutzgrenze?
- Schützt er eine produktionsnahe Integration, die niedrigere Ebenen nicht zuverlässig abdecken?

Wenn keine dieser Fragen klar mit ja beantwortet werden kann, ist der Test ein Kandidat für `merge`, `rewrite` oder `retire-later`.

## Grundregeln
- Neue Features starten mit BDD-Szenarien und API-Änderungen zuerst in `api/openapi.yml`.
- Neue Tests entstehen auf der niedrigsten sinnvollen Ebene.
- Refactors starten mit Characterization-Tests oder Contract-Tests, nicht mit großen Umbauschritten.
- Security-Tests brauchen positive und negative Fälle.
- E2E-Tests prüfen nur kritische Nutzerreisen, keine Detaillogik.
- Lokal bleibt prod-like: keine Dev-only-Testpfade, keine alternativen Schemas, keine lokalen Shortcuts.
- Tests dürfen keine echten personenbezogenen Daten, Secrets oder schulbezogenen Identifikatoren enthalten.

## Testebenen

### Domain- und Use-Case-Tests
Zweck: Fachliche Regeln schnell und ohne Web-Framework, Datenbank oder Docker prüfen.

Typische Inhalte:
- Freischaltung von Abschnitten
- Rollen- und Zustandslogik, soweit sie nicht direkt aus RLS kommt
- Feedback-Status, Upload-Validierung, Scoring-Normalisierung
- Parser, Sanitizer, Mapper und reine Hilfsfunktionen

Regel: Wenn eine fachliche Regel ohne HTTP und ohne DB testbar ist, gehört sie zuerst hierher.

### Adapter- und Contract-Tests
Zweck: Grenzen zu externen oder austauschbaren Komponenten absichern.

Typische Inhalte:
- Supabase Storage Adapter mit Fake-Client oder Mock-HTTP
- H5P-Service-Verträge
- OpenAI-/Ollama-/DSPy-Adapter ohne echte Modellabhängigkeit
- BFF-Proxy und Header-/Cookie-Weitergabe

Regel: Adapter-Tests prüfen die Übersetzung an der Grenze, nicht die vollständige Nutzerreise.

### OpenAPI- und API-Contract-Tests
Zweck: `api/openapi.yml` als öffentliche Wahrheit schützen.

Typische Inhalte:
- OpenAPI-Datei ist valide.
- Kritische Pfade, Methoden, Security-Schemes, Statuscodes und Cache-Header sind dokumentiert.
- `make test-api-contract-baseline` vergleicht Runtime-`/api/*`-Operationen mit `api/openapi.yml`.
- Runtime-Routen sind klassifiziert: public API, BFF/internal, H5P service, auth bridge, health/ops, active UI oder retired legacy UI.
- Breaking Changes brauchen einen Eintrag in `docs/plan/DECISIONS.md`.

Regel: Viele kleine YAML-Einzeltests sollen langfristig durch generische Contract-Gates ergänzt oder ersetzt werden, wo das Verhalten gleichartig ist.

### API-Integrationstests
Zweck: Öffentliches HTTP-Verhalten prüfen, wenn Request/Response, Middleware, Auth, Fehlerabbildung oder Serialisierung relevant sind.

Typische Inhalte:
- Happy Path je Workflow
- 401/403/404 und Validierungsfehler
- Cache-Control und CSRF-relevante Header
- Response-Shape gegen den dokumentierten Vertrag

Regel: Nicht jede interne Branch-Logik darf über HTTP getestet werden. Wenn der Test keine Web-Schicht braucht, gehört er tiefer.

### DB-, RLS- und Migrationstests
Zweck: Datenbankregeln, RLS, SECURITY DEFINER Helper, Constraints und Migrationen gegen die lokale Supabase-Struktur prüfen.

Typische Inhalte:
- Schüler A sieht keine Daten von Schüler B.
- Lehrer A sieht keine fremden Kurse.
- RLS schützt auch dann, wenn API-Filter falsch oder unvollständig wären.
- Migrationen setzen Constraints, Grants, Indizes und Helper-Rechte korrekt.

Regel: Diese Tests sind bewusst teurer, aber sicherheitskritisch. Sie müssen sauber markiert und isoliert sein. Marker wie `db_read` und `db_write` dürfen nicht nur in `pytest.ini` stehen, sondern müssen konsequent genutzt oder entfernt werden.

### Frontend-Tests
Zweck: SvelteKit-Routen, Komponenten, BFF-Loader und UI-Zustände prüfen, ohne Browser-E2E zu überladen.

Typische Inhalte:
- `svelte-check`
- Vitest-Komponententests
- Route-Contract-Tests
- Formularzustände, Fehlerzustände und BFF-Proxy-Verhalten

Regel: Frontend-Tests sind Teil der Hauptstrategie. Sie werden nicht erst nach Backend-Refactors betrachtet.

### H5P-Tests
Zweck: Den H5P-Sidecar, seine Auth-/Session-Grenzen und öffentliche H5P-Verträge schützen.

Typische Inhalte:
- Node-Test-Suite im H5P-Service
- Auth- und Cookie-Verhalten
- AJAX-/finishedData-Flüsse
- Import- und Asset-Auflösung

Regel: H5P hat eigene Laufzeitbedingungen und darf nicht nur durch allgemeine Backend-Tests abgesichert werden.

### E2E-Smokes
Zweck: Wenige produktionsnahe Kernreisen prüfen, die aus mehreren Diensten bestehen.

Kernreisen:
- Login, Logout und Session-Fortsetzung
- Lehrer erstellt oder öffnet eine Lerneinheit
- Lehrer schaltet einen Abschnitt frei
- Schüler lädt eine Lösung hoch
- Feedback erscheint
- Dashboard zeigt Fortschritt
- H5P-Roundtrip

Regel: E2E-Smokes sind teuer und fragil. Sie schützen Vertrauen in die Integration, nicht Detailabdeckung.

## Testprofile
- `fast`: In-Process-, Domain-, Adapter- und Contract-Tests ohne externe Dienste.
- `db-security`: echte DB-, RLS-, Migration-, Authz- und CSRF-relevante Tests.
- `upload-llm-boundaries`: servicefreie Upload-, Storage-, Signatur-, Feedback-/DSPy- und Privacy-Contracts; keine inhaltliche Vorprüfung oder Veränderung von Schüler-Submissions.
- `docker-image-smoke`: Web-Image ohne Compose-Bind-Mounts bauen, package-orientierten Start `backend.web.main:app` prüfen, kritische Imports prüfen und `/health` abfragen; Bestandteil von `make verify`.
- `import-boundaries`: AST-basierter Baseline-Scan für flache Web-Imports, gemischte `backend.web.routes.*`-Imports und verstreute `sys.path`-Manipulationen.
- `db-inventory`: generierte Übersicht in `docs/harness/DB_TEST_INVENTORY.md` für echte DB/RLS-Kandidaten, statische Migrationstests und Supabase-Storage-/Konfigurationsverträge; Bestandteil von `make verify` als Synchronitätscheck.
- `frontend-h5p`: `npm run check`, Vitest und H5P Node tests; Bestandteil von `make verify`.
- `full-prod-like`: Supabase, OpenAI-kompatibler Endpunkt, Docker/Compose und E2E-Smokes.

## Marker-Regeln
- `e2e`, `supabase_integration`, `openai_integration` und `legacy_migration` bleiben opt-in.
- `db_read` und `db_write` werden erst dann als Strategie-Marker akzeptiert, wenn die `missing-db-marker`-Einträge aus `docs/harness/DB_TEST_INVENTORY.md` geprüft und bereinigt wurden.
- Tests mit echten externen Diensten dürfen nicht durch zufällig gesetzte ENV-Variablen in der Standardsuite landen.
- Tests mit globalen DB-Mutationen brauchen ein eigenes Gate oder bleiben aus der Standardsuite ausgeschlossen.

## Lösch- und Bereinigungsregeln
- `keep`: Der Test schützt eine klare Regel, einen Vertrag oder eine Sicherheitsgrenze.
- `merge`: Der Test ist sinnvoll, aber redundant mit mehreren ähnlichen Tests.
- `rewrite`: Der Test prüft das Richtige, aber auf der falschen Ebene.
- `retire-later`: Der Test schützt Legacy-Verhalten oder Archivwissen und braucht eine bewusste spätere Entscheidung.

Keine Testdatei wird nur gelöscht, weil sie alt ist. Sie wird entfernt, wenn ihr Zweck anders besser geschützt ist oder der geschützte Pfad bewusst retired wurde.
