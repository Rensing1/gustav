# `/teaching/units`: Ansichts-Tabs entfernen

Status: abgeschlossen

## Ziel

Die Ansichts-Tabs in der Lehrkraft-Katalogansicht `/teaching/units` werden
vollständig entfernt. Die Seite zeigt nur noch Such- und Sortierwerkzeuge sowie
die Bestandsliste.

## Umsetzung

1. Vertrags- und Komponententests auf die reduzierte Toolbar umstellen.
2. `TeacherUnitsCatalogToolbar` von der View-Navigation befreien.
3. Die Route von `catalog.views` als Toolbar-Eingabe entkoppeln.
4. Frontend-Tests, `svelte-check` und Frontend-Container-Neubau ausführen.
