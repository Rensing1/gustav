# Countdown: Neuladen, Hintergrundtab und JavaScript-Fallback

## Manueller Prüfplan

Echte Registrierung und lokaler Mail-Empfänger. Laufenden Countdown neu laden, serverseitige Sperre kontrollieren. Hintergrundunterbrechung prüfen. JavaScript nur im separaten Prüftab deaktivieren und echten nativen Formularversand durchführen. Keine automatisierten Tests und keine Änderungen am Produktcode. SMTP anschließend wiederherstellen, Prüfkonto deaktivieren und temporäre Daten entfernen.

## Laufende Befunde

- Neuladen bei 21 Sekunden Restzeit entfernt die Countdown-Anzeige und aktiviert den Button vorzeitig. Erneuter Klick liefert die noch bestehende Serversperre mit 14 Sekunden. Die serverseitige Schutzwirkung bleibt bestehen; die lokale Darstellung verliert ihren Zustand.
- In-App-Browser behandelt den Prüftab auch bei Anzeige eines anderen Tabs weiterhin als `visible`. Deshalb tatsächliche Hintergrunddrosselung nicht allein durch Tabwechsel nachweisbar. Zusätzlich Browser-Lifecycle des Prüftabs während des Countdowns eingefroren, um eine Timerunterbrechung manuell zu simulieren.

## Abschluss

- Während einer neuen Sperrfrist den Browser-Lifecycle bei 29 Sekunden auf `frozen` gestellt und nach Ablauf auf `active` zurückgesetzt. Nach Rückkehr keine Sperrmeldung und Button freigegeben. Die absolute Fristberechnung übersteht die simulierte Timerpause. Echter Visibility-Wechsel im In-App-Browser nicht darstellbar; diese Einschränkung bleibt ausdrücklich bestehen.
- JavaScript mit Browser-Emulation vollständig deaktiviert, Seite neu geladen und das native POST-Formular über einen nativen Klick abgesendet. Maileingang vorher 2, danach 3. Antwortseite bleibt erreichbar. Ohne JavaScript keine zusätzliche Wiederholungsbestätigung und kein laufender Countdown.
- JavaScript-Einstellung wieder aktiviert. Ursprüngliche Mail-Konfiguration wiederhergestellt, Empfänger gestoppt, Prüfkonto deaktiviert, temporäre Zugangsdaten/Mails entfernt.
- Keine automatisierten Tests und keine Produktänderungen.

Offener Fehler: Countdownzustand überlebt Neuladen nicht. Eine auf die konkrete Auth-Sitzung begrenzte Wiederherstellung der bekannten Frist wäre erforderlich; der Server muss weiterhin maßgeblich bleiben.
