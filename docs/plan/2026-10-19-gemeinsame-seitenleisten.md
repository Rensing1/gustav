# Gemeinsame Navigation in Modulansicht und Aufgabenraum

## User Story
Als Schüler möchte ich Materialien in Modulansicht, Text-, Datei- und Dialogaufgaben über dieselbe Navigation finden und lesen.

## Umsetzung
Die bestehende WorkspaceOutline wird direkt im gemeinsamen LearnerTaskContext verwendet. Erweiterungen bleiben optional: eingebettete Darstellung ohne zweite mobile Einklappung, initiales Modul und Rückruf zum Nachladen von Modulinhalt. Material- und Abgabezeilen öffnen den vorhandenen Referenzleser. Aufgabenstellung und Dialogfortschritt bleiben oberhalb der Navigation. Dialogspezifische Gestaltungsabweichungen entfallen; funktionale Breakpoints bleiben erhalten. Keine API- oder Datenbankänderung.

## Vorab entworfene Prüffälle
- Modulansicht: bisheriges Öffnen, aktive Zeile, mobile Einklappung bleiben erhalten (WorkspaceOutline.test.ts).
- Alle Aufgabenarten: identische Navigation; aktuelles Modul anfangs offen; andere Module lassen sich laden und öffnen (LearnerTaskContext-Komponentenprüfung).
- Materialklick: vorhandener Leser öffnet das richtige Material; Rückkehr erhält Aufgabenentwurf (learner-reference-workspace.spec.ts).
- Eigene Abgabe: öffnet vorhandenen Leser mit geladenem Verlauf, ohne neue Abgabe.
- Leere, ladende und fehlgeschlagene Module: verständlicher Status, keine erfundenen Inhalte.
- Desktop und 390px: Navigation und Leser erreichbar, kein horizontaler Überlauf.

Auf ausdrücklichen Wunsch keine Tests ausführen. Erst lokale Vorschau bauen, visuell prüfen und Felix vorlegen.

## Sichtprüfung
Die gemeinsame Navigation ist im Dialog-, Text- und Datei-Arbeitsraum sichtbar. Im Dialog Material geöffnet und zum erhaltenen Gespräch zurückgekehrt; weiteres Modul mit Materialien aufgeklappt. Schmale Navigation im Materialien-Bereich geprüft. Keine Antworten verändert, keine Dateien hochgeladen, keine Abgaben erzeugt, keine automatisierten Tests ausgeführt. Die bereits zuvor beobachtete leere Text-Editorfläche bei vorhandenem Entwurf besteht weiterhin und wird nicht als behoben gewertet.
