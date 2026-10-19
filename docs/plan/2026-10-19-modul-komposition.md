# Modulseite: Hierarchie und Lesefluss

## User Story
Als Schüler erkenne ich Modul, Material und Aufgabe eindeutig und finde die zum Bearbeitungsstand passende Aktion auch auf einem schmalen Bildschirm.

## Prüffälle vor Umsetzung
- Gegeben mehrere offene Module: Beim Scrollen folgt der Kontext dem sichtbaren Modul, ohne einen neuen History-Eintrag oder einen Sprung auszulösen.
- Gegeben finale Abgabe und neuerer Entwurf: Aufgabenkennung, Entwurfsstatus und genau eine Fortsetzen-Aktion stehen zusammen; die finale Abgabe bleibt darunter sichtbar.
- Gegeben nur Entwurf, nur Abgabe oder unbearbeitete Aufgabe: passende Aktion und Vorschau bleiben erhalten.
- Gegeben 390 px Breite: Materialtitel und Pfeil stehen in einer Zeile, Texte sind linksbündig, Modulverwaltung verdrängt den Titel nicht.
- Layout-Menü, Materialfaltung und Modulschließen bleiben erreichbar; keine Daten werden verändert.

## Umsetzung und Prüfung
Abstände und Typografie auf die Modulansicht begrenzen; Layout-Menü in den ersten Modulkopf integrieren. Bestehende Scrollbeobachtung für Kontext verwenden. Keine API-, Schema- oder Authoring-Änderung. Spätere Testzuordnung: LearnerContentWorkspace/LearningTaskCard Komponentenprüfungen und learner-reference-workspace Feature-Spec. Auf ausdrücklichen Nutzerwunsch jetzt ausschließlich manuelle Desktop-/Mobilprüfung, keine automatisierten Tests.

## Ergebnis der manuellen Sichtprüfung
Frontend erfolgreich gebaut. Desktop 1280 × 720 und schmale Ansicht 390 × 720 betrachtet. Materialfaltung geöffnet/geschlossen und wiederhergestellt; Layout-Menü erreichbar. Beim Scrollen zu Materialien analysieren wechseln Kontextleiste und mobile Inhaltsanzeige passend, ohne History-Eintrag. Finale Abgabe plus neuerer Entwurf zeigt Status und eine Fortsetzen-Aktion gemeinsam, die gespeicherte Abgabe folgt in separater dezenter Fläche. Screenshots: /tmp/modul-komposition-desktop.png, /tmp/modul-komposition-mobil.png, /tmp/modul-komposition-aktion-mobil.png. Keine automatisierten Tests, keine Abgaben ausgeführt. Benutzer-Sichtprüfung steht aus.
