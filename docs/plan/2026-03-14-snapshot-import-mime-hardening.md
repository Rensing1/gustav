# Plan: Snapshot Import MIME Hardening

Status: umgesetzt (2026-03-14; Dry-Run verifiziert)

## Abschluss 2026-03-14
- `backend/tools/import_snapshot_backup.py` erkennt `.sb3` und `.hex` jetzt
  deterministisch vor dem generischen `mimetypes`-Fallback.
- `backend/tests/migration/test_import_snapshot_backup.py` deckt beide
  Spezial-Endungen explizit ab.
- Verifiziert mit:
  - `backend/tests/migration/test_import_snapshot_backup.py -k 'sb3 or hex or mime'`
    -> `2 passed`
  - `make import-snapshot-dry SNAPSHOT=.tmp/snapshot_backup_2026-03-14_020001.tar.gz`
    -> Dry-Run erfolgreich, Report unter
    `.tmp/snapshot_import_run/run_20260314_131020/report.json`

Hinweis:
- Der destruktive Voll-Import wurde in diesem Batch bewusst nicht automatisch
  ausgefuehrt.

## Hintergrund
Der lokale Workflow zum Testen mit production-nahen Daten basiert auf
`make import-snapshot`. Neuere Snapshots enthalten Storage-Objekte mit den
Endungen `.sb3` und `.hex`. Der aktuelle Importer erkennt diese MIME-Typen
nicht zuverlässig und faellt auf `application/octet-stream` zurueck. Dadurch
scheitert der Storage-Import, obwohl DB und Keycloak bereits restauriert wurden.

## Ziel
- Der Snapshot-Importer erkennt `.sb3` und `.hex` deterministisch.
- Der aktuelle Snapshot aus `.tmp` laesst sich lokal wieder erfolgreich
  importieren.
- Der bestehende Login- und UI-Test-Workflow bleibt unveraendert.

## Scope
- Test in `backend/tests/migration/test_import_snapshot_backup.py`
- Minimaler Code-Fix in `backend/tools/import_snapshot_backup.py`
- Re-Import des aktuellen Snapshots zur Verifikation

## Non-goals
- Keine Aenderung an Auth-Flows, Keycloak-Themes oder Passwoertern
- Keine API- oder Schema-Aenderungen
- Kein Umbau des gesamten Snapshot-Workflows

## Red-Green-Refactor
1. RED:
   - Test ergaenzen, der fuer `.sb3` und `.hex` die erwarteten MIME-Typen
     fordert.
2. GREEN:
   - Importer minimal erweitern, sodass bekannte Spezial-Endungen vor dem
     generischen `mimetypes`-Fallback aufgeloest werden.
3. REFACTOR:
   - Logik klein und lesbar halten; keine weiteren Verhaltensaenderungen.

## Verifikation
1. Gezielten `pytest`-Lauf fuer `test_import_snapshot_backup.py` ausfuehren.
2. Optionaler Operator-Schritt:
   `make import-snapshot SNAPSHOT=/home/felix/gustav-alpha2/.tmp/snapshot_backup_2026-03-14_020001.tar.gz`
   manuell starten.
3. Danach normal ueber die Login-Maske mit dem bekannten Snapshot-Account
   anmelden und Kurse/Lerneinheiten pruefen.
