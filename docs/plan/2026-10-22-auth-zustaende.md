# Auth: Abmeldung und Zustände

## Ziel und Umsetzung

Als Nutzer möchte ich erkennen, ob eine Anmeldung, Abmeldung oder Bestätigung gelungen ist und welche Aktion jetzt sinnvoll ist. Abmeldebestätigung erhält den Auth-Rahmen ohne Produktslogan, einen gestalteten POST-Button und eine nachrangige Abbrechen-Aktion. App-Fehler erhalten zustandsabhängige Überschriften. Keycloak-Meldungen werden nicht doppelt ausgegeben; abgelaufene Vorgänge erhalten einen allgemeinen, passenden Hinweis. Kein leeres mobiles Menü. Keine Änderung an Cookies, Sitzungslogik, Redirect-Prüfungen oder Berechtigungen.

## Vorab entworfene Prüffälle

- Abmeldebestätigung: ein Titel, klare Hauptaktion, Abbrechen führt zurück; GET meldet nicht ab.
- Nicht bestätigte Abmeldung und nicht verfügbare Anmeldung haben unterschiedliche Überschriften und passende Aktionen.
- Unbekannter Fehlergrund fällt auf einen verständlichen Neustart der Anmeldung zurück.
- Erfolgsansicht zeigt eine kurze Bestätigung und erneute Anmeldung.
- Mobile Breite und Dunkelmodus: Aktionen erreichbar, kein Überlauf und kein leeres Menü.
- Keycloak-Information zeigt identischen Titel/Meldungstext nicht doppelt; Link-Prüfungen bleiben bestehen.

Manuelle Sichtprüfung der erreichbaren Seiten. Erfolgsseite wird als reine Darstellung geöffnet, ohne tatsächliche Abmeldung zu behaupten. Keine automatisierten Tests gemäß Auftrag. Später gezielt bestehende Auth-Problem-/Logout-Komponententests und authentifizierten Logout-Feature-Test ergänzen/ausführen. E-Mail- und tokengebundene Zustände können ohne ausgelösten Vorgang nur im Template geprüft werden.

## Umsetzung und manuelle Sichtprüfung

- Gemeinsame Aktionszeile im AuthFrame: Abmelden und Abbrechen nebeneinander auf Desktop, volle Breite untereinander mobil.
- Frontend und Keycloak erfolgreich gebaut und lokal bereitgestellt; keine automatisierten Tests ausgeführt.
- Abmeldebestätigung, nicht bestätigte Abmeldung und Erfolgsdarstellung bei 1113 × 720 und 390 × 720 visuell geprüft. Keine abgeschnittenen Aktionen oder horizontalen Überläufe sichtbar.
- Mobile Abmeldebestätigung und nicht verfügbare Anmeldung zusätzlich im Dunkelmodus geprüft; anschließend helle Darstellung wiederhergestellt.
- Unbekannter Fehlergrund zeigt den vorgesehenen Fallback. Erfolgsseite nur direkt zur Sichtprüfung geöffnet: keine tatsächliche Abmeldung ausgelöst.
- E-Mail- und tokengebundene Keycloak-Zustände nur anhand der Vorlagen geprüft; deren reale Darstellung bleibt noch offen. Keine E-Mail versendet, keine Zugangsdaten geändert.
