# Mailanforderung: Countdown und aktuelle Fehlermeldungen

## Plan und vorab entworfene Prüffälle

- Auf echte Sperrfristantwort: verbleibende Sekunden herunterzählen und Versandbutton sperren; nach Fristablauf Meldung entfernen und Button freigeben. Serverseitige Sperrfrist bleibt maßgeblich.
- Vor jeder neuen Anforderung alte Fehler-/Erfolgsmeldungen entfernen.
- Tatsächlicher SMTP-Fehler nach Sperrfrist: nur aktuelle Fehlermeldung in Du-Anrede, keine falsche Erfolgsmeldung, erneute Anforderung möglich.
- Desktop und mobil manuell über echte Registrierung und lokalen Mail-Empfänger prüfen. Keine automatisierten Tests gemäß Auftrag.
- Keine hart codierte Sperrdauer: Sekunden ausschließlich aus der erwarteten lokalisierten Servermeldung übernehmen. Andere Serverfehler werden nicht als Sperrfrist interpretiert. Ohne JavaScript bleibt die Sperre serverseitig wirksam.

## Ergebnis

Countdown mit echter Server-Sperrfrist manuell geprüft: auf Desktop 10 Sekunden mit deaktiviertem Button; mobil neuer Countdown von 29 auf 5 Sekunden, Button weiterhin deaktiviert. Nach Ablauf: Button aktiv, keine alte Sperrmeldung mehr im DOM. Maileingang nach zulässiger erneuter Anforderung: zwei Mails insgesamt; gesperrte Anforderung erzeugt keine weitere Mail.

Anschließend echten SMTP-Verbindungsfehler über ausschließlich lokalen unerreichbaren Empfänger ausgelöst. Nur aktuelle Fehlermeldung in Du-Anrede sichtbar; keine alte Sperrfrist und keine Erfolgsbehauptung. Maileingang unverändert. Desktop 1113 × 720 und mobil 390 × 720 visuell geprüft; Aktionen erreichbar.

Build erfolgreich. Keine automatisierten Tests. SMTP-Konfiguration wiederhergestellt, Prüfkonto deaktiviert, Empfänger gestoppt und temporäre Zugangsdaten/Mails entfernt. Ohne-JavaScript-Fallback und Hintergrundtab-Timer wurden nicht gesondert manuell geprüft.
