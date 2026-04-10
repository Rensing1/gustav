# Lernaufgaben: einheitliche Upload-UX

## Ziel
- `Aufgabe beginnen` bleibt der einheitliche Einstieg für alle Nicht-H5P-Aufgaben.
- `native`-Aufgaben öffnen standardmäßig im Textmodus und erlauben einen Wechsel zu `Upload`.
- Upload-only-Aufgaben (`visual`, `scratch`, `calliope`) öffnen direkt im passenden Upload-Editor.
- In `Meine Abgabe` werden Bild- und PDF-Uploads als Vorschau gezeigt; andere Dateien erscheinen als kompakte Dateikarte.

## Umsetzung
- `LearningTaskCard` bekommt einen lokalen Editor-Modus `text | upload` und eine kompakte Dateikarte mit `Ersetzen` / `Entfernen`.
- Der Upload wird weiter erst beim Abschicken ausgelöst; die Dateiauswahl bleibt bis dahin lokal im Browser.
- Bestehende Upload-Abgaben werden im Review-Bereich reichhaltiger angezeigt, ohne API- oder Schemaänderung.

## Tests
- Komponententests für einheitlichen CTA, Moduswechsel, typspezifische Upload-Copy, Dateikarte und Review-Vorschau.
- Bestehende Route-/Servertests bleiben als Regressionsschutz für den Upload-Submit-Flow aktiv.
