# Mailanforderung: Sperrfrist und Versandfehler

Manuelle Prüfung über echte Registrierung und erneuten Versand: kurzfristig wiederholte Anforderung muss die serverseitige Sperrfrist anzeigen und darf keine zusätzliche Mail auslösen. Nach Ablauf wird der ausschließlich lokale SMTP-Empfänger vorübergehend unerreichbar gemacht; die UI darf dann keinen Erfolg behaupten. Beide Zustände auf Desktop und mobil festhalten. SMTP-Konfiguration und gegebenenfalls die erforderliche Aktion vorher sichern und anschließend wiederherstellen, Prüfkonto deaktivieren. Keine automatisierten Tests.

## Ergebnis

Echte Registrierung angelegt, anschließend kurzfristig mehrfach über den Versandbutton angefordert. Keycloak lieferte die Sperrfrist („Bitte warte 7 Sekunden …“). Der lokale Maileingang blieb bei einer Mail. Die erforderliche Aktion und ihre Sperrfrist-Konfiguration wurden nicht verändert.

Nach Ablauf der Sperrfrist nur den SMTP-Port des lokalen Empfängers vorübergehend auf einen nicht erreichbaren Port gestellt. Erneute Anforderung liefert tatsächlich „Die E-Mail konnte nicht versendet werden. Bitte versuchen Sie es später noch einmal.“ Keine Erfolgsmeldung, Maileingang weiterhin eine Mail.

Beide Zustände bei 1113 × 720 und 390 × 720 manuell angesehen und Screenshots festgehalten. Inhalte und Aktionen sind erreichbar.

Offene UI-Befunde:
- Sekundenangabe ist statisch; Button bleibt während der Sperrfrist aktiv. Serverseitig wird dennoch korrekt blockiert.
- Die alte Sperrfristmeldung bleibt nach Ablauf beim anschließenden SMTP-Fehler sichtbar. Vor einer neuen Anforderung bzw. bei neuer Rückmeldung sollte der alte Fehler entfernt werden.
- SMTP-Fehlermeldung verwendet noch Sie-Anrede; konsistente Du-Anrede erforderlich.

Keine automatisierten Tests und keine Produktänderungen in diesem Durchgang. Ursprüngliche SMTP-Konfiguration wiederhergestellt, Empfänger gestoppt, Prüfkonto deaktiviert, temporäre Mail- und Zugangsdaten entfernt.
