# Plan: Live-Dashboard-Redesign für `/live`

Status: in Umsetzung
Datum: 2026-04-09

## Ziel
- `/live` wird zur einseitigen Lehrkraft-Konsole für eine Kurs-Lerneinheit-Kombination.
- Die Seite bietet oben die Auswahl von `Kurs` und `Lerneinheit`.
- Darunter zeigt sie pro Schüler eine kompakte Übersicht mit Bearbeitungsquote, Durchschnittsbewertung und letzter Abgabe.
- Ein Klick auf eine Schülerzeile öffnet ein Detailpanel mit Mini-Matrix und letzter Abgabe.

## Produktentscheidungen
- `/live` ist die kanonische Einstiegseite; die Auswahl erfolgt direkt dort.
- Die Primäransicht ist eine Tabelle, keine Aufgabenmatrix.
- Standardsortierung ist alphabetisch.
- `Bearbeitet %` bedeutet: Anteil der Aufgaben mit mindestens einer Abgabe.
- Das Detailpanel öffnet über die ganze Zeile und startet mit einer Mini-Matrix des Schülers.

## API und Daten
- Neuer Read-Model-Endpunkt: `GET /api/live/views/courses/{course_id}/units/{unit_id}/dashboard`
- Neuer Contract:
  - `LiveUnitDashboardView`
  - `LiveUnitDashboardSummary`
  - `LiveUnitDashboardRow`
  - `LiveDashboardLatestSubmission`
  - `LiveStudentPanelView`
- V1 nutzt vorhandene Live-Zusammenfassungen weiter und ergänzt serverseitig die fehlenden Aggregationen für die Tabellenzeilen.

## UI
- Kopfbereich mit zwei Comboboxen für Kurs und Lerneinheit.
- Kompakter Summary-Block mit Klassenkennzahlen.
- Tabelle mit Spalten:
  - `Schüler`
  - `Bearbeitet`
  - `Ø Bewertung`
  - `Letzte Abgabe`
- Rechtes Detailpanel mit:
  - Mini-Matrix aller Aufgaben der gewählten Lerneinheit für einen Schüler
  - hervorgehobener letzter Abgabe
  - Detailkarte der letzten Abgabe

## Tests
- OpenAPI-Contract-Test für den neuen Dashboard-Endpunkt und die neuen Schemas.
- API-Test für den Dashboard-Endpunkt inklusive Zeilenkennzahlen und optionalem Detailpanel.
- Packaging-Test für die kanonische `/live`-Seite mit Dashboard-Loader.
- Nach Implementierung gezielte Ausführung der neuen Live-Tests.

## Nachtrag: Detailpanel-Sidecar
- Das Detailpanel wird auf eine aktive Aufgabenwahl mit `task_id` in der kanonischen `/live`-URL erweitert.
- Klick auf eine Schülerzeile soll automatisch die zuletzt bearbeitete Aufgabe dieses Schülers auswählen; das geschieht ohne zusätzliche Nutzeraktion.
- Das Panel zeigt nicht mehr starr nur die letzte Abgabe, sondern die aktuell gewählte Aufgabe.
- Die Darstellung orientiert sich an der Lernseite:
  - horizontale Aufgabenleiste mit kompakten Status-Rechtecken
  - Tabs `Abgabe`, `Bewertung`, `Rückmeldung`
  - Markdown- und Artefakt-Darstellung über Shared-Utilities statt über rohe `pre`-Blöcke
- Auf Desktop bleibt das Panel als rechte Sidecar-Fläche sticky sichtbar; auf kleineren Displays wandert es unter die Tabelle.
