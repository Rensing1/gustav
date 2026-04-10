# Verify-Regressions und Test-Stabilisierung

## Zusammenfassung
- `make verify` zeigte sechs Fehler, aber auf dem aktuellen Branch reproduzieren sich nur drei davon stabil.
- Die drei echten Regressionen betreffen:
  - den DB-Preflight-Contract,
  - den SvelteKit-Entry-Contract für `/`,
  - den Worker-Regressionstest für Transaktionsgrenzen.
- Zusätzlich werden die Tests gegen globale Zustandslecks gehärtet, damit Learning-/Teaching-Storage-Adapter und Directory-Warnungen nicht mehr andere Suites beeinflussen.

## Geplante Änderungen
- Den Preflight-Erfolgstest an den aktuellen Contract anpassen: Erfolg setzt jetzt auch den Bulk-Aggregate-Helper voraus.
- Den veralteten Root-Route-Packaging-Test auf den heutigen Loader-Contract umstellen:
  - `parent()` statt erneutem Session-Bootstrap-Fetch,
  - Redirect bei vorhandenem `bootstrap`,
  - kein `readTypedJsonOrNull`.
- Den Worker-Regressionstest an die aktuelle Bild-Upload-Pipeline anpassen:
  - Blockade in `analyze_visual(...)` statt im Vision-Adapter,
  - Assertions zu `leased` und `not idle in transaction` bleiben unverändert.
- Neue `autouse`-Fixture in `backend/tests/conftest.py`:
  - setzt Learning-/Teaching-Storage-Adapter vor jedem Test auf den Null-Adapter zurück.
- Live-Summary-Fallback-Tests härten:
  - Login-Label-Auflösung mocken,
  - Logprüfung enger auf die Teaching-Fallback-Warnung begrenzen.

## Verifikation
- Gezielte Tests:
  - `backend/tests/migration/test_verify_db_preflight.py`
  - `backend/tests/packaging/test_sveltekit_entry_routing_contract.py`
  - `backend/tests/test_learning_worker_transaction_boundaries.py`
  - `backend/tests/test_teaching_live_unit_summary_api.py`
- Danach Stichprobe mit:
  - `backend/tests/test_learning_api_contract.py`
- Abschließend:
  - `.venv/bin/pytest -q ...` für die betroffene Zielmenge
  - wenn Frontend-Dateien angefasst wurden: `docker compose up -d --build frontend`

## Annahmen
- Der kanonische `/`-Loader nutzt `parent()` und nicht mehr den direkten Bootstrap-Fetch.
- Native Bild-Uploads laufen produktiv über `visual_direct`; der Regressionstest muss diese Realität abbilden.
- Die drei übrigen Fehler aus dem ursprünglichen Lauf sind derzeit am ehesten Test-Isolationsprobleme, keine neuen Produktfehler.
