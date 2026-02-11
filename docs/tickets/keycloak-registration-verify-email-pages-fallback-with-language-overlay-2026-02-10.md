# Ticket: Registrierung/Verifizierung landet auf Keycloak-Standardseiten mit dominanter Sprach-Auswahl

Status: offen  
Priorität: hoch  
Betroffene Umgebung: Produktion (`app.gustav.example`, `id.gustav.example`)  
Erstellt am: 10. Februar 2026

## Kontext

- Registrierung wird über `/auth/register` gestartet und läuft technisch erfolgreich durch (Account wird angelegt, Verifizierungs-E-Mail wird versendet).
- Im laufenden Realm ist `verifyEmail=true` aktiv, daher folgt nach dem Registrieren ein `VERIFY_EMAIL`-Schritt.
- Das GUSTAV-Theme enthält aktuell nur einen Teil der Login-Templates (`login.ftl`, `register.ftl`, `login-reset-password.ftl`, `login-update-password.ftl`, `update-password.ftl`).

## Problem

Nutzer landen im Registrierungs-/Verifizierungsworkflow mehrfach auf optisch „falschen“ bzw. kaputt wirkenden Seiten mit stark präsenter Sprach-Auswahl (Deutsch/Englisch), statt auf den konsistenten GUSTAV-Seiten.

Betroffen laut Beobachtung:
- Klick auf „Registrieren“
- Klick auf Verifizierungslink aus der E-Mail

## Beobachtete Evidenz

- Nach Submit der Registrierungsmaske folgt Redirect auf:
  - `/realms/gustav/login-actions/required-action?execution=VERIFY_EMAIL...`
- Die gerenderte Seite ist nicht das kompakte `kc-gustav`-Markup, sondern Standard-Keycloak-Layout (`login-pf`) mit Locale-Dropdown:
  - `id="kc-locale"`
  - Menü mit `Deutsch` / `English`
- Ursache passt zur Theme-Struktur:
  - `keycloak/themes/gustav/login/theme.properties` nutzt `parent=keycloak`
  - fehlende Templates fallen daher auf das Parent-Theme zurück

## Reproduktion

1. Registrierung über `https://app.gustav.example/auth/register` starten.
2. Im Keycloak-Flow auf „Registrieren“ klicken und Formular absenden.
3. Beobachten: Redirect auf `required-action?execution=VERIFY_EMAIL` zeigt Standard-Keycloak-Seite inkl. Sprachmenü.
4. Verifizierungslink aus E-Mail öffnen.
5. Beobachten: ebenfalls nicht durchgängig GUSTAV-Template, sondern teils Standard-Keycloak-Ansicht.

## Erwartetes Verhalten

- Alle Seiten im Registrierungs- und Verifizierungsflow sind visuell konsistent im GUSTAV-Stil.
- Sprachumschaltung darf vorhanden sein, aber nicht als dominantes/irritierendes Overlay wirken.
- Nutzer sehen keine abrupten Sprünge zwischen GUSTAV-UI und Default-Keycloak-UI.

## Technische Ursache (wahrscheinlich)

1. **Template-Fallback auf Parent-Theme**
   - Für `VERIFY_EMAIL`-/Info-/Action-Token-Seiten fehlen im `gustav`-Login-Theme spezifische Templates.
   - Keycloak rendert daher Parent (`keycloak`) mit Standardstruktur inkl. Locale-Komponenten.

2. **Zusatzproblem im Registrierungsformular (separat, aber relevant)**
   - Passwort-Hinweistext in `register.ftl` sagt „Keine Sonderzeichen erforderlich“.
   - Realm-Policy verlangt aber `specialChars(1)`.
   - Das erzeugt zusätzliche `invalid_registration`-Fehler und verstärkt den Eindruck eines „buggy“ Flows.

## Hinweise für die Umsetzung

- Theme um fehlende Templates für den kompletten Verify-Email-/Info-Flow ergänzen (z. B. entsprechende Login-Actions-/Info-Templates gemäß Keycloak 24).
- Locale-Bereich gezielt stylen, damit er nicht den Hauptfokus überdeckt.
- Vorhandene Theme-Tests erweitern:
  - Presence-Checks für die zusätzlichen Templates
  - Markup-Checks für konsistente `kc-gustav`-Struktur auf Verify-Email-/Info-Seiten
- Passwort-Hinweis in `register.ftl` an reale Policy angleichen (oder Policy an gewünschte UX).

## Akzeptanzkriterien

- Nach Registrierung wird eine GUSTAV-gestylte Verify-Email-Seite angezeigt (kein wahrnehmbarer Wechsel auf Default-Keycloak-Look).
- Nach Klick auf den Verifizierungslink erscheint ebenfalls eine konsistente GUSTAV-Seite.
- Sprachumschaltung ist funktional, aber nicht als störendes Vollbild-/Overlay-Element wahrnehmbar.
- Theme-/Contract-Tests decken die zusätzlichen Seiten ab und laufen grün.
- Dokumentation der Änderung in Runbook/Incident-Log ergänzt.
