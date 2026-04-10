# H5P Snapshot Import Bind-Mount Fix

## Problem

Nach `make import-snapshot` oeffnet sich der H5P-Editor in der Lehreransicht nicht mehr, obwohl H5P-Aufgaben erfolgreich angelegt werden. Die Ursache liegt nicht im Formular-Flow, sondern im Snapshot-Import fuer den H5P-Dateispeicher:

- `supabase/storage/h5p` ist als Bind-Mount nach `/data/h5p` in den H5P-Container eingebunden.
- Der Import loescht dieses Zielverzeichnis aktuell komplett und legt es neu an.
- Ein laufender Container behaelt dadurch den alten Mount-Inode und sieht danach ein leeres Verzeichnis.
- Der H5P-Service wird `unhealthy`, weil `/data/h5p/tmp` aus seiner Sicht fehlt bzw. nicht schreibbar ist.

## Ziel

Der Snapshot-Import soll den Inhalt des H5P-Storage in-place ersetzen, ohne das Wurzelverzeichnis selbst zu entfernen. Dadurch bleibt der Bind-Mount fuer laufende Container stabil.

## Umsetzung

1. Regressionstest fuer `_restore_h5p_storage_tar(...)` ergaenzen:
   - bestehendes Zielverzeichnis bleibt erhalten
   - alte Kinder werden entfernt
   - neue Archivdaten werden korrekt entpackt
2. Import-Tool minimal anpassen:
   - neue Helper-Funktion zum Leeren eines Verzeichnisses ohne `rmtree(dest)`
   - `_restore_h5p_storage_tar(...)` verwendet diese Helper-Funktion
3. Betroffene Tests ausfuehren:
   - gezielter Pytest-Lauf fuer `backend/tests/migration/test_import_snapshot_backup.py`

## Akzeptanzkriterien

- Der neue Test faellt vor dem Fix und ist danach gruen.
- Der vorhandene H5P-Restore-Test bleibt gruen.
- Der Import ersetzt H5P-Dateien, ohne das Root-Verzeichnis auszutauschen.
- Bestehende H5P-Konsistenzpruefungen bleiben unveraendert aktiv.
