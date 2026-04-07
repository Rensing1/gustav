# Lernaufgabe: Review-First-Komposition mit task-lokaler Abgabe

Status: abgeschlossen

## Ziel

Die Aufgabenkarte wird auf ein klares Zwei-Aktionen-Modell umgebaut:

- ohne Einreichung: nur `Aufgabe bearbeiten`
- mit Einreichung: `Meine Abgabe` und `Erneut bearbeiten`

`Meine Abgabe` ist ein auf- und zuklappbarer Review-Bereich mit den Ansichten `Abgabe`, `Rückmeldung` und `Auswertung`.

Gleichzeitig wird der Verdrahtungsfehler behoben, bei dem jede Aufgabe die globale Historie der zuletzt bearbeiteten Aufgabe anzeigt.

## Entscheidungen

- `Meine Abgabe` zeigt immer die neueste Submission insgesamt.
- `Meine Abgabe` startet geschlossen.
- Wenn eine neue Rückmeldung fertig wird, öffnet sich `Meine Abgabe` automatisch.
- Nach finaler Abgabe bleibt `Meine Abgabe` geschlossen.
- `Meine Abgabe` und der Inline-Editor dürfen gleichzeitig sichtbar sein.
- Ältere Versuche sind in dieser Iteration nicht Teil der sichtbaren Haupt-UX.

## Umsetzung

- `LearningTaskCard` erhält eine neue Aktionszeile:
  - ohne Submission: `Aufgabe bearbeiten`
  - mit Submission: `Meine Abgabe`, `Erneut bearbeiten`
- Der bisherige Block `Letzter Versuch` mit `Weitere Versuche` entfällt.
- Die Review-Fläche wird nur nach Klick auf `Meine Abgabe` gerendert.
- Die Lernraum-Route verwaltet Submission-Historien task-lokal statt global und aktualisiert nur noch den betroffenen Task beim Polling.
- `has_submission` aus dem bestehenden Read-Model wird für die Button-Logik genutzt.

## Tests

- `LearningTaskCard.test.ts`
  - ohne Submission: nur `Aufgabe bearbeiten`
  - mit Submission: `Meine Abgabe` und `Erneut bearbeiten`
  - `Meine Abgabe` öffnet den Review-Bereich mit `Abgabe`, `Rückmeldung`, `Auswertung`
  - kein `Weitere Versuche`
- `LearningUnitContentWorkspace.test.ts`
  - nur die Aufgabe mit Historie zeigt den Review-Einstieg
- `page-contract.test.ts`
  - task-lokale History-Struktur statt globaler Einzelhistorie in der Route
