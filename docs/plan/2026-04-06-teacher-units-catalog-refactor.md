# `/teaching/units` im Mistral-Design

Status: abgeschlossen

## Ziel

Die Lehrkraft-Ansicht `/teaching/units` wird auf die neue Mistral-Sprache
umgestellt. Der Umbau bleibt ein reiner Frontend-Refactor ohne API-, OpenAPI-
oder Datenbankänderung.

## Entscheidungen

- Die Seite nutzt `PageActionHead` als globalen Seitenkopf.
- Der Inhalt darunter besteht aus einer kompakten Werkzeugzeile mit:
  - Ansichts-Tabs
  - Suche
  - Sortierung
- Status-, Fach-, Jahrgang- und Kursfilter entfallen aus der Oberfläche.
- `Neue Lerneinheit` bleibt ein Inline-Dialog auf derselben Seite.
- Die Bestandsliste wird über gemeinsame Komponenten unter
  `frontend/src/lib/components/teacher-units-catalog/` aufgebaut.

## Umsetzung

1. Fehlschlagende Frontend-Tests für Route, Werkzeugzeile und Katalogzeile
   anlegen.
2. Neue gemeinsame Katalog-Komponenten einführen.
3. Route auf `PageActionHead` und die neuen Komponenten umstellen.
4. CSS auf die Mistral-Sprache der bestehenden globalen Komponentenfamilie
   abstimmen.
5. Frontend-Tests, `svelte-check` und anschließend den Frontend-Container neu
   bauen.
