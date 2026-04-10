# Lernaufgaben in der Inhaltsansicht neu aufbauen

Status: abgeschlossen

## Zusammenfassung

- Lernaufgaben in der Lernenden-Inhaltsansicht werden als Arbeitsauftrag dargestellt.
- Der separate Einstiegskasten `Nächster Schritt` entfällt.
- Unter der Aufgabenstellung folgt direkt die Interaktionszone.
- Ohne frühere Abgabe erscheint ein klarer Primär-CTA `Aufgabe bearbeiten`.
- Mit vorhandener Abgabe erscheint zuerst ein kompakter Verlaufsblock, darunter ein subtilerer CTA `Erneut bearbeiten`.
- Die Bearbeitung öffnet inline als mittlere Arbeitsfläche innerhalb derselben Karte.

## Wichtige Änderungen

- `LearningTaskCard` wird von der heutigen Startkarten-Logik auf eine direkte Aufgabenlogik umgestellt.
- Für vorhandene Abgaben wird ein kompakter Verlaufsblock mit Tabs `Abgabe`, `Rückmeldung`, `Auswertung` ergänzt.
- Ältere Versuche werden inline über `Weitere Versuche` sichtbar, statt sofort vollständig ausgerollt zu sein.
- H5P-Aufgaben erhalten ebenfalls einen CTA, aber keinen Verlaufsblock.
- Der Lernraum filtert beim offenen Editor nicht mehr das gesamte Pane auf einen einzelnen Eintrag.
- Es kann genau eine Aufgabe insgesamt im Bearbeitungsmodus sein; andere Inhalte bleiben sichtbar.
- Die bestehende Submission- und Redirect-Logik bleibt fachlich unverändert.

## Testplan

- `LearningTaskCard.test.ts`
  - ohne Abgabe: Aufgabenstellung plus Primär-CTA `Aufgabe bearbeiten`
  - mit Abgabe: Verlaufsblock vor CTA, CTA heißt `Erneut bearbeiten`
  - kein Text `Nächster Schritt` oder `Antwortstatus`
  - Klick auf CTA öffnet die Inline-Bearbeitung in derselben Karte
- Neuer Test für den Verlaufsblock
  - Tabs `Abgabe`, `Rückmeldung`, `Auswertung`
  - letzter Versuch sichtbar
  - ältere Versuche über `Weitere Versuche`
- H5P-Test
  - H5P zeigt CTA statt sofortiger Einbettung
- `npm run check`
- `docker compose up -d --build frontend`

## Annahmen

- `Aufgabe bearbeiten` bleibt der Primärtext beim ersten Versuch.
- Nach vorhandener Abgabe heißt der CTA `Erneut bearbeiten`.
- Die letzte Abgabe steht vor dem CTA.
- H5P verwendet denselben Einstiegsgedanken, aber ohne Verlauf.
