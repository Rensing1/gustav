# Live-Ansicht

GUSTAV-Version: 0.0.4
Zuletzt geprüft: 2026-10-23
[English version](live-view.en.md)

## Zweck

Die Live-Ansicht unterstützt die Lehrkraft während einer laufenden Unterrichtsphase. Sie zeigt den aktuellen Arbeitsstand einer ausgewählten Lerneinheit und ermöglicht den schnellen Wechsel von der Klassenübersicht zur letzten Abgabe einer einzelnen Person.

![Live-Ansicht mit Klassenübersicht und Schülerdetail](assets/live-view.jpg)

## Voraussetzungen

- Du bist die besitzende Lehrkraft des Kurses.
- Der Kurs ist vorhanden und ihm ist mindestens eine Lerneinheit zugeordnet.
- Mitglieder und Aufgaben existieren; aussagekräftige Detaildaten entstehen erst durch Abgaben.

## Schritt für Schritt

1. Öffne **„Unterrichten“** oder direkt **„Live“**.
2. Wähle unter **„Kurs“** den gewünschten Kurs und anschließend unter **„Lerneinheit“** die aktuelle Einheit.
3. Wähle **„Live öffnen“**. Die Matrix ordnet Lernaufgaben nach Modul beziehungsweise Abschnitt. **„Stand“** zeigt abgegebene Aufgaben und Durchschnitt; **„Üben“** zählt neue/fällige und aktuell sichere Übungsaufgaben.
4. Wechsle bei Bedarf zwischen **„Aufgaben“** und **„Üben“**. Auf schmalen Bildschirmen begrenzt die Modulauswahl die sichtbaren Spalten.
5. Wähle eine Aufgaben- oder Übungszelle. Unter der Tabelle erscheinen Aufgabenleiste und Detailansicht. Die nummerierten Aufgabenflächen erlauben den Wechsel innerhalb des Lernendenkontexts.
6. Öffne **„Abgabe“**, **„Rückmeldung“** oder **„Auswertung“**. Aufgabenstellung und Antwort stehen untereinander; bei Dialogaufgaben ist auch der berechtigungsgeprüfte Verlauf erreichbar.
7. Lass die Ansicht während der Arbeitsphase geöffnet; neue Zustände werden regelmäßig nachgeladen.

## Lernendensicht

Lernende sehen nicht die Klassenmatrix. Sie arbeiten weiter im Lernraum und erhalten dort ihre eigene Rückmeldung. Die Live-Ansicht ist eine getrennte Lehrkraftprojektion und erlaubt keinen Zugriff auf Arbeiten aus fremden Kursen.

## So funktioniert es

Die Übersicht liest gezielt vorbereitete Daten für genau einen Kurs und eine Lerneinheit. Sie aktualisiert veränderte Zeilen und Detailzustände regelmäßig, ohne die komplette Seite für jede Änderung neu aufzubauen. Die Detailansicht zeigt die letzte berechtigte Abgabe zur gewählten Aufgabe sowie vorhandene Rückmeldung.

Durchschnitt und Fortschritt dienen der Orientierung im Unterricht. Sie fassen vorhandene Aufgabenstände zusammen und sollen auffällige Unterstützungsbedarfe sichtbar machen.

## Grenzen

- Live zeigt einen aktuellen Ausschnitt und ist keine langfristige Lernverlaufsanalyse.
- Die Detailfläche konzentriert sich auf die letzte Abgabe; sie ersetzt keine vollständige Abgabehistorie.
- Ein Durchschnitt ist keine automatisch erzeugte Note und darf nicht ohne fachliche Einordnung verwendet werden.
- Ohne zugeordnete Lerneinheit oder Abgaben bleibt die Ansicht leer beziehungsweise zeigt **„Noch keine Abgabe“**.
- Übungszustände erscheinen getrennt von Lernaufgaben; sie fließen nicht in Fortschritt und Durchschnitt der Lernaufgaben ein.
- Aktualisierung erfolgt regelmäßig, aber nicht als garantierte sekundengenaue Echtzeitübertragung.

## Typische Probleme

- **„Keine Lerneinheiten verfügbar“:** Ordne dem Kurs zuerst eine Lerneinheit zu.
- **„Noch keine Kurse für den Live-Raum verfügbar“:** Lege einen eigenen Kurs an beziehungsweise prüfe seinen Status.
- **„Noch keine Abgabe“:** Die gewählte Person hat für diese Aufgabe noch keine sichtbare Abgabe gespeichert.
- **Rückmeldung fehlt:** Die Analyse kann noch laufen oder fehlgeschlagen sein; die gespeicherte Abgabe kann trotzdem vorhanden sein.
- **Werte ändern sich nicht sofort:** Warte auf die nächste Aktualisierung oder lade die Ansicht neu.

## Verwandte Kapitel

- [Kurse und Mitglieder](courses-and-members.de.md)
- [Abgaben und Rückmeldung](submissions-and-feedback.de.md)
- [Diagnostik](diagnostics.de.md)

Technische Details: [Live-Referenz](../references/teaching_live.md).
