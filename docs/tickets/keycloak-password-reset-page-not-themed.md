# Ticket: Keycloak Passwort-Reset-Seite nicht im GUSTAV-Theme

Status: offen  
Priorität: mittel  
Betroffene Umgebung: Produktion (`gustav-lernplattform.de`)

## Kontext

- IdP: Keycloak 24.0.5, Realm `gustav`, Login-Theme `gustav`, E-Mail-Theme `gustav`.
- Login- und Registrierungsseiten sind bereits mit dem `gustav`-Theme gebrandet (gemeinsames CSS, eigenes `login.ftl` / `register.ftl`).
- SMTP ist auf `info@gustav-lernplattform.de` umgestellt und Passwort-Reset-E-Mails werden korrekt versendet.
- Flow: `/auth/forgot` → Keycloak Reset-Credentials-Seite → E-Mail mit Reset-Link → Klick auf Link führt nun korrekt auf eine Seite zum Setzen eines neuen Passworts.

## Problem

Die Passwort-Reset-Seite, die nach Klick auf den Link in der E-Mail angezeigt wird, verwendet aktuell nicht das GUSTAV-Login-Theme, sondern das Standard-Keycloak-Layout. Dadurch entsteht ein Bruch in der User Experience:

- andere Farben/Typografie als Login/Registrierung,
- kein GUSTAV-Branding,
- potenziell verwirrend für Schüler*innen und Lehrkräfte („bin ich noch in GUSTAV?“).

Technisch funktioniert der Reset-Flow inzwischen (Required Action `UPDATE_PASSWORD` ist aktiviert, `Reset Password` im Flow auf `REQUIRED` gesetzt), es geht explizit um das visuelle Theme der Seite.

## Erwartetes Verhalten

- Alle auth-relevanten Seiten, inkl. „Neues Passwort setzen“, nutzen konsistent das `gustav`-Theme:
  - gemeinsames Layout wie `login.ftl`,
  - Buttons/Typografie analog zur Login-Seite,
  - GUSTAV-Branding klar erkennbar.
- Der Wechsel von E-Mail → Passwort-Reset-Seite fühlt sich wie ein nahtloser Teil der GUSTAV-Lernplattform an.

## Hinweise für die Umsetzung

- Prüfen, welche Templates/Fragmente Keycloak für den Schritt `Update Password` verwendet:
  - ggf. eigenes Template im Theme ergänzen (z. B. `keycloak/themes/gustav/login/update-password.ftl` oder analog zum Keycloak-Standardnamen),
  - sicherstellen, dass das Template das gleiche CSS wie `login.ftl` lädt (`app-gustav-base.css`, `gustav.css`).
- Verifizieren, dass der `gustav`-Login-Theme auch für die Reset-Credentials-Seite aktiv ist (Realm-Einstellung `loginTheme=gustav` ist bereits gesetzt, aber evtl. greifen zusätzliche Templates).
- Tests ergänzen/erweitern:
  - `backend/tests/test_keycloak_theme_files.py`: Presence-Checks für das neue Template,
  - optional Snapshot-/Markup-Tests, um das Reset-Formular (Input-Felder, Button, Titel) abzusichern.

## Akzeptanzkriterien

- Nach Klick auf den Passwort-Reset-Link aus der E-Mail:
  - erscheint eine Seite „Passwort zurücksetzen“ im GUSTAV-Look (Logo/Typografie/Buttons wie Login),
  - Nutzer können ein neues Passwort setzen und werden danach zurück zur App geleitet.
- Alle Theme-Dateien liegen weiterhin unter `keycloak/themes/gustav/...` und werden beim Container-Build sauber ins Image übernommen.
- CI-Tests für Theme/Realm-Config sind grün.

