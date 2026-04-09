# Verify-Round-2: Importpfade und Learning-Reload-Stabilität

## Zusammenfassung
- `backend/tests/conftest.py` darf den Teaching-Router nicht über `backend.web.routes.teaching` referenzieren, weil der bestehende Packaging-Contract genau diesen Alias verbietet.
- Der verbleibende Learning-Fail ist reihenfolgeabhängig: Reload-Tests können eine neue `routes.learning`-Instanz erzeugen, während ältere `main.app`-Routen noch auf die Globals der alten Modulinstanz zeigen.
- Der Fix bleibt klein: Teaching-Reset wieder auf den kanonischen Pfad zurückführen und `routes.learning.set_storage_adapter(...)` so härten, dass bereits registrierte Learning-Endpunkte in vorhandenen `main`-Apps synchronisiert werden.

## Umsetzung
- `backend/tests/conftest.py`
  - Teaching-Storage-Reset nur noch über `routes.teaching`.
  - Kein Vorkommen von `backend.web.routes.teaching`.
- `backend/tests/test_learning_api_contract.py`
  - Kleinen Regressionstest ergänzen, der einen frischen `routes.learning`-Import gegen eine bereits existierende `main.app`-Instanz simuliert.
  - Erwartung: `set_storage_adapter(...)` aktualisiert auch die `STORAGE_ADAPTER`-Globalbindung der bereits registrierten Learning-Route.
- `backend/web/routes/learning.py`
  - `set_storage_adapter(...)` erweitert sich um eine defensive Synchronisation für vorhandene `main`-/`backend.web.main`-Apps.
  - Es werden nur Learning-Routen mit `path.startswith("/api/learning")` und deren `STORAGE_ADAPTER`-Globalbinding aktualisiert.

## Tests
- Gezielt:
  - `backend/tests/packaging/test_import_paths_contract.py`
  - `backend/tests/test_learning_api_contract.py::test_set_storage_adapter_updates_existing_learning_route_globals_after_reload`
  - `backend/tests/test_learning_api_contract.py::test_finalize_latest_feedback_file_submission_returns_decorated_files`
- Repro-Kette:
  - `backend/tests/test_learning_lazy_storage_wiring.py`
  - `backend/tests/test_learning_api_contract.py::test_finalize_latest_feedback_file_submission_returns_decorated_files`
- Abschließend:
  - `make verify`

## Annahmen
- Öffentliche API, OpenAPI-Vertrag und Datenbankschema bleiben unverändert.
- Das Problem liegt in Test-/Importzustand, nicht im fachlichen Finalize-Verhalten.
