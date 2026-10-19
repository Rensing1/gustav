# Kontextleiste als Gestaltungsprobe

User Story: Als Schüler möchte ich meinen Arbeitskontext und den direkten Rückweg in einer einzigen Kopfzeile erkennen.

Umsetzung: Im Lernbereich ersetzt eine gemeinsame Kontextleiste die globale Linkreihe plus separate Breadcrumb-Zeile. Desktop zeigt Marke, Rückweg, aufklappbaren Bereichsnamen und Konto. Mobil bleibt Rückpfeil, Bereichsname und Konto. Hierarchie, Lernraum und Üben bleiben im Kontextmenü erreichbar, Kummerkasten im Kontomenü. Bestehende URL-/Entwurfslogik und Lehrkraftnavigation bleiben erhalten.

Prüffälle vor Änderung (Given–When–Then):
- Kurs geöffnet → Bereichsmenü öffnen → Kurs, Lernraum und Üben erreichbar.
- Aufgabe geöffnet → Rückweg wählen → zugehöriges Modul öffnet, Entwurf erhalten.
- Modul intern wechseln → Kontextname aktualisiert sich.
- Schmale Ansicht und langer Name → Name darf umbrechen, Konto und Rückweg überlappen nicht.
- Menü geöffnet → Escape oder Außenklick → Menü schließt.

Spätere automatisierte Zuordnung: AppHeader-/Kontextleisten-Komponentenprüfungen sowie authentifizierter Feature-Test learner-reference-workspace. Auf Nutzerwunsch jetzt ausschließlich Build und manuelle Sichtprüfung; keine automatisierten Tests, kein Commit. Keine API- oder Schemaänderungen.

Beim Sichtcheck sichtbar geworden: Nach einem direkten Modulrücksprung können mehrere wiederhergestellte Module vor dem eigentlichen Ziel stehen. Ergänzter Prüffall: Given mehrere gespeicherte offene Module, when Rücksprung zur Modulebene, then Zielmodul wird nach asynchroner Wiederherstellung fokussiert und unterhalb der fixierten Kontextleiste sichtbar. Offener Befund: Ein einmaliger Scrollsprung reicht wegen nachgeladener Inhalte nicht zuverlässig aus. Kein zusätzlicher Eingriff in die Scrolllogik Bestandteil dieser Gestaltungsprobe.

Sichtprüfung: Kurs und Textaufgabe bei 1280px und 390px, langer Modulname bei 320px, Hierarchiemenü und Escape. Frontend-Build erfolgreich, keine automatisierten Tests. Vorhandener Textentwurf weiterhin sichtbar.
