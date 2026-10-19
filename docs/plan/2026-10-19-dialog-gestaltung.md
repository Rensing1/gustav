# KI-Dialog: Gespräch und kompakte Abgabe

## User Story
Als Schüler möchte ich im laufenden Gespräch alle Beiträge lesen und nach der Abgabe meine Abschlussantwort sofort wiederfinden.

## Umsetzung
1. Gemeinsame Nachrichtendarstellung: Ada links ohne Farbbalken, eigene Antworten rechts mit dezenter neutraler Fläche und eindeutiger Beschriftung.
2. Abgabe: Abschlussantwort zuerst, Gesprächsverlauf als geschlossenes Details-Element. Rückmeldung und Auswertung bleiben separat aufklappbar. Referenzleser behält den vollständigen Verlauf.
3. Laufendes Gespräch bleibt vollständig ohne eingeklappte Beiträge. Bestehende Aktionen, Eingaben und Fehlerzustände bleiben erhalten.

Keine API-, Datenbank- oder Authoring-Änderungen.

## Prüffälle vor Implementierung
- Gegeben eine abgeschlossene Sitzung mit Abschlussantwort, wenn die Abgabe erscheint, dann ist die Antwort sichtbar und der Gesprächsverlauf geschlossen. Komponentenprüfung: LearningDialogTranscriptDocument.test.ts.
- Gegeben eine Sitzung ohne Abschlussantwort, dann bleibt der Gesprächsverlauf erreichbar, ohne leeren Antwortblock. Gleiche Komponentenprüfung.
- Gegeben ein nicht abrufbarer Verlauf, dann erscheint weiterhin der bestehende Fehlerzustand. Bestehende Komponentenprüfung.
- Gegeben einen laufenden Dialog mit mehreren Beiträgen, dann sind alle Beiträge ohne Aufklappen lesbar, Eingabe und Abschlussaktionen bleiben erreichbar. Bestehende Dialog-Komponentenprüfungen und gezielter authentifizierter Feature-Test in learner-reference-workspace.spec.ts ergänzen.
- Desktop und schmale Ansicht: keine horizontalen Überläufe, klare Rollen, verständliche Reihenfolge; zusätzlich Hell-/Dunkelmodus visuell prüfen.

## Reihenfolge
Erst Implementierung und eigene Browser-Sichtprüfung, anschließend Felix die echte Oberfläche vorlegen. Automatisierte Prüfungen ausdrücklich erst nach seiner Sichtfreigabe: betroffene Komponenten und `make verify-feature FEATURE=learner-reference-workspace`. Keine Gesamtsuite, kein Testlauf für Dokumentation.

## Stand der Sichtprüfung
Frontend erfolgreich gebaut. Kompakte echte Dev-Abgabe auf Desktop und bei 390px geprüft, Verlauf geöffnet und Kontrast im Dunkelmodus angesehen. Laufenden Gesprächsraum mit vorhandener Eröffnungsfrage auf Desktop und bei 390px angesehen; keine Antwort gesendet und keine neue Abgabe erzeugt. Mehrere laufende Runden noch nicht interaktiv durchgespielt. Automatisierte Prüfungen bleiben bis Felix' Sichtfreigabe ausgesetzt.

## Probe: verständlicher Übergang zur Abschlussaufgabe
Vor Änderung festgelegt: Der vorhandene optionale Abschlussauftrag bestimmt die Beschriftungen. Mit Auftrag zeigt der aktive Raum `Gespräch → Abschlussaufgabe → Abgabe`, die Wechselaktion heißt `Zur Abschlussaufgabe`. Ohne Auftrag führt `Zur Abgabe` direkt zur Bestätigung. In der Abschlussphase stehen Lehrerauftrag und Antwortfeld im Gesprächsraum; die finale Aktion benennt den Umfang der Abgabe. Gespeicherte Antworten zeigen den Auftrag aus dem Sitzungssnapshot gemeinsam mit `Deine Antwort`, ohne eine Zusammenfassung zu unterstellen.

Gezielt entworfene Prüffälle (keine Ausführung auf ausdrücklichen Nutzerwunsch):
- Mit Auftrag: Orientierung sichtbar, Gespräch vollständig, Wechsel zeigt vorhandenen Auftrag; Rückkehr erhält Entwurf.
- Ohne Auftrag: keine Abschlussaufgabe, kein zusätzliches Textfeld; Bestätigung gibt Gespräch ab.
- Gespeicherte Sitzung: Auftrag und Antwort gemeinsam sichtbar; ältere Antwort ohne Auftrag bleibt lesbar.
- Letzte Runde: passende Wechselaktion erreichbar, keine zusätzliche Gesprächseingabe.
- Fehler beim Abgeben: vorhandene Fehlermeldung und Eingabe bleiben erhalten.
Zuordnung: LearningDialogWorkspace.test.ts, LearningDialogTranscriptDocument.test.ts und bestehende authentifizierte Dialogstrecke. Erst eigene Sichtprüfung und Felix' Rückmeldung; keine Tests in diesem Schritt.
