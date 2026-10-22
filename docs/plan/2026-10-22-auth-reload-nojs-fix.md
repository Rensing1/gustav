# Countdown beim Neuladen und Versandbestätigung ohne JavaScript

## Vorab entworfene Prüffälle

- Bekannte Serversperrfrist bleibt nach Neuladen im selben Auth-Vorgang erhalten; Sekunden werden nicht zurückgesetzt, Button bleibt gesperrt.
- Nach Ablauf verschwindet der gespeicherte Zeitpunkt. Ein neuer Auth-Vorgang verwendet einen eigenen Schlüssel.
- Gespeichert wird nur die absolute Frist in sessionStorage, begrenzt durch Realm, Client und Keycloak-Tab-ID. Keine E-Mail-Adresse, Zugangsdaten oder Aktionscodes im Speicher.
- Ohne JavaScript: Nach erfolgreichem nativen Versand zeigt die serverseitige Seite eine Bestätigung, nur wenn Keycloak den Versandstatus bereitstellt und kein Fehler vorliegt. Fehler/Sperrfrist dürfen keine Erfolgsbestätigung enthalten.
- Manuelle Prüfung auf Desktop und mobil mit echtem lokalem Maileingang. Keine automatisierten Tests gemäß Auftrag. Temporären Mailaufbau anschließend zurückbauen.

## Umsetzung und manuelle Sichtprüfung

- Absolute Sperrfrist im selben Auth-Vorgang wird nach Neuladen wiederhergestellt; abgelaufene Fristen werden verworfen. Bei blockiertem Browserspeicher bleibt das normale Formular verwendbar.
- Native Versandbestätigung ohne JavaScript ergänzt, getrennt vom dynamischen Statusbereich.
- Im echten Browser blieb der Button nach zwei Reloads gesperrt; die Restzeit lief von 14 auf 9 und anschließend 4 Sekunden weiter. Desktop (1113 × 720) und mobil (390 × 720) visuell geprüft.
- JavaScript im Browser deaktiviert und das native Formular erneut abgeschickt: lokale Mailanzahl stieg von 2 auf 3, Versandbestätigung auf Desktop und mobil sichtbar.
- Keycloak neu gebaut; keine automatisierten Tests ausgeführt.
- Ursprüngliche SMTP-Konfiguration wiederhergestellt, separates Prüfkonto deaktiviert, temporären Empfänger und lokale Zugangsdaten entfernt. JavaScript wieder aktiviert.
