# Auth-Formulare vereinheitlichen

## User Story und Umsetzung

Als Lernender möchte ich Anmeldung, Registrierung und Passwort-Hilfe als Teil derselben Plattform erkennen und ihre Aktionen leicht lesen können. Der gemeinsame Auth-Stylesheet steuert App und Keycloak: ruhiger Hintergrund, 8-px-Radien, dezente Rahmen ohne Schatten, Leseschrift, 16-px-Eingaben und normal geschriebene Labels/Aktionen. Keycloak erhält eine kompakte GUSTAV-Kennung neben dem Darstellungswechsel. Passwort-Hilfe benennt das Versenden eines Links ausdrücklich. Passwortregeln mit Wert null werden nicht angezeigt; aktive Regeln bleiben unverändert.

## Vorab entworfene Prüffälle

- Anmeldung, Registrierung und Passwort-Hilfe zeigen auf Desktop denselben Rahmen und dieselbe Typografie.
- Bei 390 px und 320 px bleiben alle Felder, Aktionen und Rückwege erreichbar, ohne horizontalen Überlauf.
- Hell-/Dunkelmodus erhalten lesbare Felder und erkennbare Fokusmarkierungen.
- Registrierung zeigt nur tatsächlich geforderte Passwortregeln; Labels und Fehlermeldungszuordnung bleiben erhalten.
- Passwort-Hilfe kündigt den Reset-Link an, ohne Änderungen am Ablauf oder automatisches Versenden.

Manuelle Sichtprüfung; keine automatisierten Tests gemäß Nutzerauftrag. Spätere gezielte Nachweise: bestehende Auth-Registrierungs- und Auth-UI-Komponententests. Kein API-/Datenbank-/Cookie-/Policy-Eingriff. Andere Fehlerzustände und Abmeldeaktionen sind nicht Gegenstand dieses Schritts; gemeinsame Styles wirken auch auf deren Rahmen.

## Ergebnis der Sichtprüfung

Frontend und Keycloak erfolgreich gebaut; keine automatisierten Tests ausgeführt. Im Browser Anmeldung und Passwort-Hilfe auf Desktop sowie Registrierung und Passwort-Hilfe mobil geprüft. Rückwege zwischen den drei Formularen funktionieren. Passwort-Hilfe zusätzlich in Dunkelansicht kontrolliert. Bei 320 px Registrierung: Eingaben berechnet 16 px, Dokumentbreite 305 px einschließlich verfügbarer Scrollleistenfläche, kein horizontaler Überlauf; Absenden und Rückweg durch normales Scrollen erreichbar. Null-Sonderzeichenregel entfällt sichtbar. Keine Formulare abgeschickt und keine Konten verändert. Die Sichtprüfung ersetzt keinen späteren funktionalen Auth-Nachweis.
