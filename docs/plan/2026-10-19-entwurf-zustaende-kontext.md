# Entwurf, Abgabezustände und Aufgabenkontext

## User Story
Als Schüler möchte ich meinen gespeicherten Entwurf direkt bearbeiten, den nächsten Abgabeschritt erkennen und Materialien der aktuellen Aufgabe zuverlässig finden.

## Vorgehen und vorab entworfene Prüffälle
1. Editor-Hydrierung und lokale Wiederherstellung prüfen: Given gespeicherter Text, When Editor asynchron startet, Then bleibt der Text sichtbar; Statuswechsel dürfen kein Bearbeitungsereignis erzeugen. Lokale echte Änderungen einschließlich bewusst geleerter Texte bleiben erhalten. Zuordnung: MarkdownWysiwygEditor.interaction.test.ts und LearningTaskCard-Komponentenprüfungen.
2. Given unveränderter geprüfter Entwurf, Then ist Abgeben die Hauptaktion; When Text/Datei geändert wird, Then zuerst neue Rückmeldung und keine Abgabe der alten Fassung. Leerer Text darf keine Rückmeldung anfordern. Entwurf/Abgabe werden korrekt bezeichnet. Zuordnung: LearningTaskCard-Komponentenprüfungen.
3. Given Material aus Modul A ausgewählt, When Aufgabe in Modul B geöffnet wird, Then keine alte Materialmarkierung und Modul B aufgeklappt. Zuordnung: WorkspaceOutline-/LearnerTaskContext-Komponentenprüfungen und authentifizierte learner-reference-workspace.spec.ts.
4. Desktop und 390px im echten Browser visuell prüfen, ohne Antworten abzugeben. Automatisierte Tests ausdrücklich erst nach Sichtfreigabe, kein Testlauf für diese Dokumentation.

Keine API-, Datenbank- oder Berechtigungsänderung; vorhandenen Abgabevertrag mit geprüfter Versions-ID beibehalten.

Sichtprüfung: Im vorhandenen Browser bleibt ein leerer lokaler Entwurf gegenüber der Serverfassung priorisiert. Ein leerer lokaler Text kann auch bewusst entstanden sein; deshalb wird er nicht still überschrieben. Bei leerem Schreibfeld und vorhandener geprüfter Textfassung wird eine explizite Wiederherstellungsaktion angeboten. Zusätzlicher Prüffall: Übernehmen stellt die Serverfassung im Editor her und speichert sie lokal; ohne Übernehmen bleibt der lokale Inhalt unangetastet. Keine zusätzliche Rückmeldung oder Abgabe wird erzeugt.

Ursache beim weiteren Navigieren bestätigt: Auch reine Vorschaukarten registrieren pagehide/Unmount-Persistierung und schrieben ihren nie bearbeiteten leeren draftText in denselben Sitzungsschlüssel. Persistierung ist deshalb jetzt auf tatsächliche Bearbeitungen begrenzt. Zusätzlicher Prüffall: Modulvorschau öffnen und verlassen darf einen bereits vorhandenen lokalen Entwurf nicht überschreiben; bewusstes Leeren im Editor muss weiterhin gespeichert werden.

## Ergebnis der manuellen Sichtprüfung
Frontend erfolgreich gebaut. Vorhandene Serverfassung über die sichtbare Wiederherstellungsaktion übernommen, danach Neuladen sowie Editor → Modulübersicht → Entwurf weiterbearbeiten geprüft: Text bleibt erhalten. Probeergänzung zeigt neue Rückmeldung statt Abgeben; Rückgängigmachen stellt Abgeben wieder her. Probeergänzung vollständig entfernt, keine Abgabe oder Auswertung ausgelöst. Wechsel von Textaufgabe mit ausgewähltem Material zur H5P-Aufgabe öffnet das aktuelle Modul ohne alte Materialmarkierung. Desktop 1280px und schmale Ansicht 390px geprüft. Automatisierte Prüfungen und Commit bleiben aus; Sichtfreigabe steht aus.
