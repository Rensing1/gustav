# Einheitliches Meldungssystem für GUSTAV

## User Story

Als Lehrkraft oder lernende Person möchte ich nach einer Aktion eine gut sichtbare, verständliche und barrierefrei angekündigte Meldung erhalten, damit ich sofort weiß, ob GUSTAV noch arbeitet, die Aktion erfolgreich war oder ich etwas korrigieren muss, ohne dass erledigte Hinweise die Arbeitsfläche unnötig belegen.

## BDD-Szenarien

- **Komponentenvarianten:** Gegeben eine Erfolgs-, Fehler-, Warn-, Informations- oder Fortschrittsmeldung, wenn sie erscheint, dann besitzt sie ein eindeutiges Symbol, eine Überschrift, eine Beschreibung, die passende semantische Ankündigung und eine kontrastreiche Darstellung in Hell- und Dunkelmodus.
- **Transiente Erfolge:** Gegeben eine Erfolgsmeldung, wenn sechs sichtbare Sekunden vergangen sind, dann verschwindet sie; während Dokument, Maus oder Fokus die Meldung pausieren, läuft die Frist nicht weiter.
- **Persistente Zustände:** Gegeben eine laufende Verarbeitung oder einen Fehler, wenn Zeit vergeht, dann bleibt die Meldung sichtbar, bis sich der Fachzustand ändert oder der Fehler geschlossen beziehungsweise behoben wird.
- **Formularfehler:** Gegeben ein ungültiges Formular, wenn die Aktion fehlschlägt, dann erscheint die Fehlermeldung vor dem Formularinhalt, wird fokussiert oder mit dem ersten ungültigen Feld verknüpft und ins Blickfeld gebracht.
- **Simulation:** Gegeben eine Simulation mit externen Verweisen, wenn eine Lehrkraft sie finalisiert, dann bleiben Titel und Orientierung erhalten, die abgelehnte Datei wird entfernt und die Meldung erklärt Ursache sowie notwendige erneute Dateiauswahl.
- **Feedback läuft:** Gegeben eine Schülerabgabe mit angeforderter Rückmeldung, wenn die Analyse läuft, dann steht genau eine Fortschrittsmeldung in der aktiven Aufgabe und der dauerhafte Aufgabenstatus bleibt auch nach Verlassen der Bearbeitung erkennbar.
- **Feedback dauert:** Gegeben eine mindestens 60 Sekunden laufende Analyse, dann wechselt dieselbe Meldung ohne Positionssprung zu „Die Rückmeldung dauert länger als üblich …“.
- **Feedback fertig:** Gegeben eine fertige Entwurfsrückmeldung, dann erscheint sechs sichtbare Sekunden „Rückmeldung ist bereit“ mit „Ansehen“, ohne die Ansicht automatisch zu wechseln; der Aufgabenstatus bleibt danach erhalten.
- **Endabgabe fertig:** Gegeben eine endgültige Abgabe, wenn Verarbeitung und Auswertung abgeschlossen sind, dann öffnet GUSTAV wie bisher die Ergebnisansicht und bestätigt dort sechs sichtbare Sekunden „Aufgabe abgegeben“.
- **Verarbeitung fehlgeschlagen:** Gegeben eine fehlgeschlagene Analyse, dann bleibt ein als Alarm angekündigter Fehler sichtbar und der vorhandene Weg zur erneuten Bearbeitung oder Abgabe ist wieder benutzbar.

## Technischer Entwurf

- `StatusMessage.svelte` bildet `success`, `error`, `warning`, `info` und `progress` mit zentral abgeleiteten Rollen, Symbolen, Aktionen und optionaler Sechs-Sekunden-Lebensdauer ab.
- `FieldError.svelte` rendert feldnahe Fehler; Eingaben setzen `aria-invalid` und `aria-describedby`.
- Ein kleiner Fokushelfer fokussiert neu erschienene Aktionsfehler mit `tabindex="-1"` und scrollt sie in den sichtbaren Bereich.
- Semantische Meldungsfarben und Bewegungsregeln liegen in den gemeinsamen UI-Primitives. Ein globaler Store und app-weite Meldungen werden nicht eingeführt.
- Die Lernendenansicht besitzt pro aktiver Aufgabe genau eine Meldungsregion. Polling verändert deren Inhalt, erzeugt aber keine neue Live-Region. Nach Abschluss bleibt der Fachzustand in Aufgabenstatus und Ergebnisbereich erhalten.
- API, Worker, Pollingintervalle und Datenbank bleiben unverändert. OpenAPI- und Migrationsänderungen sind nicht erforderlich.

## Einführung und Tests

1. Komponenten- und Timer-Tests rot schreiben, anschließend gemeinsame Komponenten und Styles implementieren.
2. Materialeditor einschließlich kompakter Simulationsorientierung und fokussierter Fehlermeldung migrieren.
3. Lernenden-Feedbackfluss, Endabgabe und Verarbeitungsfehler migrieren.
4. Übrige Lehrer-, Lern-, Profil-, Kummerkasten-, H5P-, Live- und Exportmeldungen auf die gemeinsamen Bausteine umstellen; alte visuelle Varianten entfernen, sobald keine Nutzung verbleibt.
5. Einen mit `@feature-acceptance` markierten Browsertest für Simulationsablehnung und Schülerabgabe ergänzen; Hell-/Dunkelmodus, kleine Viewports und reduzierte Bewegung prüfen.
6. Vor dem Commit lokale CA und Dev-Accounts prüfen, gezielte Tests ausführen und `make verify-feature` erfolgreich abschließen.

## Festgelegte Grenzen

- Erfolgsmeldungen verschwinden nach sechs sichtbaren Sekunden; der Timer pausiert bei verborgenem Dokument sowie bei Hover oder Fokus innerhalb der Meldung.
- Fortschritt bleibt bis zum Zustandswechsel sichtbar, Fehler bis zur Behebung oder zum Schließen.
- Eine fertige Entwurfsrückmeldung wird nicht automatisch geöffnet; eine fertige Endabgabe öffnet weiterhin automatisch die Ergebnisansicht.
- Toasts bleiben folgenlosen Kurzbestätigungen vorbehalten und sind nicht Teil dieser ersten Migration.
