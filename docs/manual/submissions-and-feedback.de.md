# Abgaben und Rückmeldung

GUSTAV-Version: 0.0.4
Zuletzt geprüft: 2026-08-20
[English version](submissions-and-feedback.en.md)

![Formative Rückmeldung im Lernraum](../assets/readme/formative-feedback.jpg)

## Zweck

GUSTAV trennt formative Rückmeldung von der endgültigen Abgabe. Lernende können eine Fassung prüfen lassen, die Rückmeldung reflektieren und überarbeiten, bevor sie genau diese Fassung endgültig abgeben.

## Voraussetzungen

- Die Aufgabe ist für die lernende Person zugänglich.
- Der Aufgabentyp unterstützt die vorgesehene Text- oder Dateibearbeitung.
- Bei KI-Rückmeldung sind Analyse- und Feedbackdienst betriebsbereit.
- Für eine endgültige Abgabe wurde zur aktuellen Fassung bereits Rückmeldung eingeholt.

## Schritt für Schritt

1. Die lernende Person verfasst eine Antwort oder wählt eine passende Datei aus.
2. Mit **„Rückmeldung einholen“** wird die aktuelle Fassung als unveränderlicher Versuch gespeichert und zur Auswertung vorgemerkt.
3. Während der Verarbeitung zeigt GUSTAV einen laufenden Zustand. Nach Abschluss erscheinen **„Auswertung“** und **„Rückmeldung“**.
4. Die lernende Person liest die Rückmeldung und bearbeitet ihren Entwurf weiter. Eine geänderte Fassung benötigt erneut Rückmeldung.
5. Nur wenn der aktuelle Entwurf genau der zuletzt geprüften Fassung entspricht, wird **„Endgültig abgeben“** ermöglicht.
6. Nach der endgültigen Abgabe bleibt der gespeicherte Versuch erhalten. Abhängig von der Aufgabe kann anschließend eine weitere Bearbeitung möglich sein oder ein Versuchslimit greifen.

## Lernendensicht

Die Oberfläche unterscheidet den bearbeitbaren Entwurf von gespeicherten Versuchen. Frühere Abgaben lassen sich mit ihrer Auswertung und Rückmeldung öffnen. Bei Dateiaufgaben werden Dateiname, Typ und verfügbare Vorschau angezeigt. Bei KI-Dialogen beendet die endgültige Abgabe den Dialog und löst die Abschlussauswertung aus.

## So funktioniert es

Jede an den Server gesendete Fassung wird als unveränderlicher Versuch gespeichert. Doppelte Übertragungen werden durch wiederholbare Anfragen abgefangen. Datei-Uploads werden vor der Analyse auf Größe, Typ, Signatur und Aufgabenbindung geprüft.

Die Verarbeitung läuft im Hintergrund. GUSTAV veröffentlicht erst eine vollständig validierte Auswertung und Rückmeldung. Ein technischer Fehler verändert eine gespeicherte Antwort nicht; die Oberfläche zeigt stattdessen einen bereinigten Fehlerzustand.

KI-Rückmeldung ist formativ. Sie soll zur Überarbeitung anregen und ist weder eine Note noch ein unanfechtbares fachliches Urteil.

## Grenzen

- Ein ungesendeter Editorentwurf ist nur im aktuellen Browsertab verfügbar.
- Eine endgültige Abgabe ist nur für die zuletzt zur Rückmeldung gespeicherte, unveränderte Fassung möglich.
- Teilweise KI-Ergebnisse werden nicht angezeigt. Bei einem Verarbeitungsfehler kann die Rückmeldung fehlen, obwohl die Antwort sicher gespeichert ist.
- Zulässige Dateiformate und Größen hängen vom Aufgabentyp ab; eine umbenannte unpassende Datei wird nicht allein wegen ihrer Endung akzeptiert.
- Versuchslimits gelten serverseitig und können nicht durch Neuladen oder einen zweiten Tab umgangen werden.
- Die KI darf keine abschließende pädagogische Entscheidung anstelle der Lehrkraft treffen.

## Typische Probleme

- **„Für diese Fassung zuerst Rückmeldung einholen“:** Der Entwurf wurde nach der letzten Rückmeldung verändert.
- **Auswertung bleibt aus:** Warte zunächst auf den laufenden Zustand. Bei einem stabilen Fehler kann die Fassung erneut zur Rückmeldung eingereicht werden.
- **Datei wird abgelehnt:** Verwende das für den Aufgabentyp erwartete Originalformat und wähle die Datei erneut aus.
- **Doppelklick erzeugt keine zweite Abgabe:** Das ist beabsichtigter Schutz vor doppelten Versuchen.
- **Sitzung ist abgelaufen:** Melde dich erneut an. GUSTAV versucht, den sicheren Arbeitskontext wiederherzustellen; prüfe den Entwurf trotzdem vor dem erneuten Senden.

## Verwandte Kapitel

- [Materialien und Aufgaben](materials-and-tasks.de.md)
- [Lernraum](learner-workspace.de.md)
- [Live-Ansicht](live-view.de.md)
- [Diagnostik](diagnostics.de.md)

Technische Details: [Learning-Referenz](../references/learning.md) und [Learning-AI-Referenz](../references/learning_ai.md).
