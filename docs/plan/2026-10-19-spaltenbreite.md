# Aufgabenbereich durch schmalere Seitenleiste vergrößern

User Story: Als Schüler möchte ich den Spaltentrenner nach links ziehen können, damit meine Aufgabe mehr Platz erhält.

Ursache: Die gemeinsame Einstellungslogik begrenzt die Kontextspalte auf mindestens 35 Prozent. Die bereits schmale Ausgangsposition ist deshalb zugleich die linke Grenze, obwohl nach rechts bis 65 Prozent möglich ist.

Prüffälle vor Änderung: Given Desktop-Dialog mit 35 Prozent Kontextbreite, when Trennlinie nach links gezogen wird, then kann die Seitenleiste bis 24 Prozent schrumpfen und der Aufgabenbereich wächst. Given minimale Breite, when nach rechts gezogen wird, then wird die Seitenleiste wieder breiter. Given Tastaturbedienung, when Home bzw. Pfeiltasten verwendet werden, then gelten dieselben Grenzen. Given gespeicherte neue Breite, when neu geladen wird, then bleibt diese erhalten. Given schmale Ansicht, then bleibt die bestehende Umschaltung ohne Spaltentrenner erhalten.

Spätere Tests: task-column-preference.test.ts für Grenzen und Speicherung, LearnerTaskSplitDivider-Komponentenprüfung für Maus/Tastatur, authentifizierter Feature-Test learner-reference-workspace für tatsächliche Breitenänderung. Jetzt auf ausdrücklichen Nutzerwunsch keine automatisierten Tests. Build und manuelle Browserprüfung. Keine API- oder Datenbankänderungen.

Umsetzung: gemeinsame Mindestbreite auf 24 Prozent senken; Maximum und bestehende gespeicherte Einstellungen bleiben gültig. Seitenleiste behält auch am Desktop-Breakpoint ungefähr 230 Pixel Platz.

Manuell geprüft: Mausziehen von 65 auf 24 Prozent und zurück auf 40 Prozent funktioniert im laufenden Dialog. Home setzt 24 Prozent; Neuladen erhält 24 Prozent. Screenshot zeigt breiten Aufgabenbereich bei lesbarer Seitenleiste. Frontend-Build erfolgreich. Keine automatisierten Tests ausgeführt. Schmale Ansicht und andere Aufgabentypen in diesem Durchlauf nicht erneut geprüft.
