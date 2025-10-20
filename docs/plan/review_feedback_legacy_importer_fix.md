# Plan: Close review findings from feature/legacy-importer

## Hintergrund
Der aktuelle PR führt eine persistente Session-Storage-Lösung, einen Legacy-Importer und mehrere Auth-Hardening-Schritte ein. Im Review haben wir konkrete Probleme gefunden (Inkonsistenzen, fehlende Tests, API-Vertrag). Ziel ist es, diese Findings gezielt zu adressieren, ohne zusätzlichen Scope aufzumachen.

## Ziele
1. Datensatz `LegacyUserRow` korrekt modellieren (fehlende Namen als `None` repräsentieren).
2. Keycloak-Admin-Client im Importer mit Timeouts absichern.
3. Defensive Fehlerpfade bei `/api/me` (Session-Store schlägt fehl) durch Tests abdecken.
4. OpenAPI-Vertrag mit realem Verhalten (nullable `expires_at`) synchronisieren.
5. Doppelten Fake-PSYCOPG-Testcode in Hilfsmodul auslagern.

## Schritte
1. Tests red schreiben:
   - `test_legacy_user_importer` erweitert, damit fehlende Namen `None` ergeben.
   - Neuer Test für Timeouts im Keycloak-Admin-Client.
   - Neuer Test in `test_auth_hardening` (oder eigenem Modul), der Session-Store-Fehler bei `/api/me` abdeckt.
   - Anpassung/Erweiterung der OpenAPI-Tests, um nullable `expires_at` einzufordern.
   - Helper-Test für ausgelagerten Fake-PSYCOPG.
2. Implementierungen minimal anpassen, bis die Tests grün sind:
   - Legacy-Importer Query/Postprocessing.
   - Keycloak-Admin-Client Timeout-Unterstützung.
   - `/api/me` evtl. Logging/Fehlerpfad überprüfen (Logik ist vorhanden, nur Test sichern).
   - OpenAPI `expires_at` nullable setzen.
   - Fake-PSYCOPG-Helper in `backend/tests/utils/fake_psycopg.py` o. Ä. extrahieren und Tests anpassen.
3. Refactor/Nacharbeiten:
   - Doppelte Fake-PSYCOPG-Logik konsolidieren.
   - Überflüssige Kommentare/Imports bereinigen.
4. Abschließende Selbstkontrolle:
   - `pytest` relevante Suites laufen lassen (Unit + betroffene Module).
   - `git diff` prüfen, keine versehentlichen Artefakte (z. B. .pyc).
   - Dokumentation/Kommentare final checken.
5. Review-Notizen für Felix vorbereiten.

