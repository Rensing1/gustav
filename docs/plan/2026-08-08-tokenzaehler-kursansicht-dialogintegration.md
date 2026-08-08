# Tokenzähler: vollständige Kurs-Nutzungsansicht

## User Story

Als Lehrkraft möchte ich in einem Kurs die gesamte LLM-Nutzung aller Lernenden als getrennte Input-, Output- und Gesamt-Tokens sehen, aufgeschlüsselt nach Modell und Nutzungsart, damit ich den technischen Verbrauch nachvollziehen und bei Bedarf extern in Kosten umrechnen kann.

## BDD-Szenarien

- **Gesamtnutzung:** Gegeben sind Abgaben-, OCR-, Feedback- und Dialogereignisse eines Kurses, wenn die Kursbesitzerin die KI-Nutzung öffnet, dann sieht sie deren gemeinsame Input-, Output- und Gesamtsumme.
- **Breakdown:** Gegeben sind Ereignisse verschiedener Modelle und Nutzungsarten, dann zeigt die Tabelle je Modell und Nutzungsart genau eine Zeile mit den getrennten Tokenwerten.
- **Dialoge:** Dialogstart, Dialogantwort und abschließende Dialogbewertung werden erfasst; Lehrkraft-Previews werden nicht in einen Kurs eingerechnet.
- **Zeitraum:** Von-/Bis-Datum gelten als vollständige Kalendertage in `Europe/Berlin`; das Von-Datum ist inklusiv und der Bis-Tag wird über die exklusive Grenze des Folgetags abgebildet.
- **Lerneinheit:** Ein Lerneinheitenfilter beschränkt Summen und Breakdown; Aufgaben- und Schülerfilter bleiben nur in der API.
- **Unbekannte Nutzung:** Fehlende Provider-Telemetrie verändert bekannte Tokensummen nicht und erscheint als Anzahl unbekannter Aufrufe.
- **Leerer Kurs:** Ohne Ereignisse erscheint ein verständlicher Leerzustand mit Nullwerten.
- **Löschung:** Beim Löschen einer Abgabe oder eines Dialogs werden die zugehörigen Ereignisse mitgelöscht; die Kurssumme sinkt entsprechend.
- **Berechtigung:** Nur die Kursbesitzerin darf die Auswertung lesen; andere Lehrkräfte und Lernende erhalten keine Daten.
- **Archivierte Kurse:** Die schreibgeschützte Auswertung bleibt erreichbar.
- **API-Pagination:** Kurssummen bleiben vollständig, Lernendenzeilen werden paginiert und ein Schülerfilter liefert nur den passenden Kurslernenden.
- **Fehlerfälle:** Ungültige Zeiträume, `limit` außerhalb 1–200 und negatives `offset` liefern `422`; fremde Filterkennungen liefern leere Ergebnisse ohne Existenzinformationen.

## Contract und Datenfluss

- `GET /api/teaching/views/courses/{course_id}/ai-usage` bleibt die öffentliche Schnittstelle.
- Die Breakdown-Dimensionen werden um `initial_starters`, `reply` und `dialog_generation` erweitert.
- Die Teaching-Abfrage vereinigt `ai_usage_events` mit kursgebundenen Schülerereignissen aus `dialog_ai_usage_events` und aggregiert bereits in PostgreSQL.
- Die abschließende Dialogbewertung nutzt die zentrale DSPy-Usage-Erfassung und transportiert Ereignisse auch durch nachgelagerte Fehlerpfade.
- Bestehende RLS-Grenzen, `Cache-Control: private, no-store` und die inhaltsfreie Telemetrie bleiben erhalten.
- Es ist keine Migration erforderlich: Tabellen, Fremdschlüssel, RLS und Kurs-/Zeitindizes bestehen bereits.

## Oberfläche

- Neue Unterseite `/teaching/courses/{courseId}/ai-usage`, erreichbar über die Kursdetailseite.
- Drei Kennzahlen zeigen Input-, Output- und Gesamt-Tokens.
- Eine responsive Tabelle zeigt Modell, Nutzungsart und Tokens. Technische API-Gruppen nach Modalität oder Aufruftyp werden je Modell und Nutzungsart zusammengefasst.
- Die Anzahl unbekannter Aufrufe erscheint nur ab einem unbekannten Aufruf als kleiner Hinweis oberhalb der Tabelle.
- Die Oberfläche zeigt keine Lernendennamen und keine Geldbeträge.
- GET-Filter: Von-Datum, Bis-Datum und Lerneinheit; Standard ist der gesamte gespeicherte Kurszeitraum.

## TDD und Verifikation

1. OpenAPI- und Backendtests rot schreiben.
2. Minimale Backendimplementierung grün machen.
3. Frontend- und Page-Server-Tests rot schreiben.
4. Minimale Oberfläche grün machen und anschließend verständlich refaktorieren.
5. Einen authentifizierten, mit `@feature-acceptance` markierten Playwright-Test über Oberfläche, Backend und lokale Datenbank ergänzen.
6. Fokussierte pytest-, Vitest- und Playwright-Prüfungen ausführen.
7. Vor Fertigmeldung `make verify-feature` erfolgreich ausführen.

## Nachträgliche UI-Vereinfachung

Nach Sichtung der realen Kursansicht wird das sichtbare Breakdown bewusst gröber als die technische API:

- Die BFF fasst API-Gruppen für die Tabelle nach Modell und Nutzungsart zusammen. Modalität und Aufruftyp bleiben im API-Vertrag erhalten, erzeugen in der Oberfläche aber keine scheinbar doppelten Zeilen.
- Die Spalten „Bekannt“ und „Unbekannt“ entfallen.
- Die Anzahl unbekannter Aufrufe erscheint nur ab einem unbekannten Aufruf und wird als kleiner, unaufdringlicher Hinweis gestaltet.
- Ein Regressionstest belegt die Zusammenfassung zweier technisch verschiedener API-Zeilen zu einer sichtbaren Tabellenzeile.

## Abgrenzung

- Keine Eurobeträge oder Tarife.
- Keine Lehrkraft-Previews in Kurssummen.
- Keine plattformweite Auswertung und kein CSV-Export.
- Keine Schätzung oder UI-Kennzeichnung historisch nicht erfasster Dialogbewertungen.
