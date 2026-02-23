# Ticket: Registrierung/Verifizierung springt intermittierend auf Keycloak-Fehlerseite mit Sprachwahl (ohne GUSTAV-Theme)

Status: abgeschlossen  
Priorität: hoch  
Betroffene Umgebung: Produktion (`app.gustav.example`, `id.gustav.example`)  
Erstellt am: 17. Februar 2026  
Bezug: `docs/tickets/keycloak-registration-verify-email-pages-fallback-with-language-overlay-2026-02-10.md` (Happy-Path-Templates ergänzt)

Abschluss-Hinweis (2026-02-23): `error.ftl` und `login-page-expired.ftl` wurden im GUSTAV-Theme ergänzt, inklusive dezentem Locale-Footer, robusten CTA-Fallbacks und i18n-Keys (DE/EN). Die Theme-Tests wurden erweitert und laufen grün (`backend/tests/test_keycloak_theme_files.py`).

## Kontext

- IdP: Keycloak 24.x, Realm `gustav`, Login-Theme `gustav`, Internationalisierung aktiv (DE/EN).
- Im GUSTAV-Login-Theme existieren inzwischen Verify-/Info-Templates (`login-verify-email.ftl`, `info.ftl`), sodass der Happy-Path nach Registrierung/Verifizierung gebrandet sein sollte.

## Problem

In bestimmten Fällen landen Nutzer im Registrierungs-/E-Mail-Verifizierungsflow auf einer Keycloak-Fehlerseite mit dominanter Sprachwahl (Deutsch/English) und Standard-Keycloak-Markup. Diese Seite wirkt „unbranded“/kaputt und enthält keine klare Handlungsanweisung.

Beobachtet:
- nach Klick auf „Registrieren“ (insbesondere nach Submit des Formulars)
- nach Klick auf den Link in der Verifizierungs-E-Mail

## Beobachtete UI/Signaturen (sanitized)

- Seite enthält Locale-Dropdown (`id="kc-locale"`) und Standard-Layout (PatternFly / `login-pf`).
- Typische Fehltexte:
  - „Cookie konnte nicht gefunden werden. Bitte stellen Sie sicher, dass Cookies in Ihrem Browser aktiviert sind.“
  - „Ungültiger Code, bitte melden Sie sich erneut über die Applikation an.“
  - (teilweise) „Token is not active“ / `expired_code` (bei Action-Token-Links)

## Erwartetes Verhalten

- Auch Fehler-/Edge-Cases im Auth-Flow bleiben optisch konsistent im GUSTAV-Look.
- Nutzer erhalten klare nächste Schritte, z. B.:
  - „Bitte Cookies aktivieren oder in einem normalen Browser öffnen.“
  - „Bitte Registrierung/Login erneut über die App starten.“
  - Optional: Link zurück zur App (Login/Register).

## Technische Analyse (Root Cause)

Die verbleibenden Fälle sind sehr wahrscheinlich keine reinen Template-Lücken im Happy-Path (VERIFY_EMAIL/Info), sondern Error-Pages, die Keycloak bei fehlendem Flow-Context rendert:

1. **`cookie_not_found`**
   - Keycloak kann den Login-/Registrierungs-Flow nicht fortsetzen, weil das Flow-Cookie nicht vorhanden ist (Cookies deaktiviert/gebockt, strikte Privacy-Settings, In-App-WebView/Browser-Kontextwechsel).

2. **Ungültige/abgelaufene Action-Token (Verify-Email-Link)**
   - Verifizierungslink ist ungültig/abgelaufen oder wurde vorab durch Preview/Scanner geöffnet; beim eigentlichen Klick ist das Token dann nicht mehr aktiv (`expired_code`).

Für diese Fehlerfälle nutzt Keycloak eigene Templates (u. a. `error.ftl`, `login-page-expired.ftl`). Diese fehlen im `gustav`-Theme; wegen `parent=keycloak` fällt Keycloak daher auf Parent-Theme-Rendering zurück → Standard-Layout mit dominanter Sprachwahl.

## Reproduktion (sanitized)

1) **Cookie-Not-Found**
- Cookies im Browser deaktivieren (oder sehr strikte Tracking-Protection aktivieren).
- Registrierung über `GET /auth/register` starten und Formular absenden.
- Erwartet: Fehlerseite „Cookie konnte nicht gefunden werden…“ mit Sprachwahl.

2) **Action-Token ungültig/abgelaufen**
- Verifizierungslink aus der E-Mail mehrfach öffnen oder verzögert öffnen; optional: Link durch E-Mail-Preview/Scanner „vor-klicken“ lassen.
- Erwartet: Fehlerseite „Ungültiger Code…“ bzw. `expired_code`.

## Hinweise für die Umsetzung

1) **Theme ergänzen (Login Theme)**
- `keycloak/themes/gustav/login/error.ftl`
- `keycloak/themes/gustav/login/login-page-expired.ftl`
- Beide Templates sollten das gleiche kompakte Layout wie `login.ftl` nutzen (`kc-gustav`, `kc-card`) und die gleichen CSS-Assets laden (`app-gustav-base.css`, `gustav.css`).
- Inhalt/CTAs:
  - kurzer, ruhiger Titel („Anmeldung nicht möglich“ / „Link abgelaufen“),
  - klare Handlungsanweisung (Cookies aktivieren / Flow neu starten),
  - Links: „Zurück zur App“, „Erneut versuchen“ (Login/Register).

2) **Optional: Locale UI entschärfen**
- Falls Sprachumschaltung auch auf Error-Pages benötigt wird: als unaufdringliche Links (Footer) statt dominantem Dropdown.

3) **Tests erweitern**
- `backend/tests/test_keycloak_theme_files.py`: Presence-/Hook-Checks für `error.ftl` und `login-page-expired.ftl`.

## Akzeptanzkriterien

- `cookie_not_found`-/Action-Token-Fehlerseiten erscheinen im GUSTAV-Look (kein Default-Keycloak-Bruch).
- Seite erklärt nächste Schritte eindeutig und role-agnostisch.
- Theme-Tests decken die neuen Templates ab und laufen grün.

## Abgrenzung

- Keine Änderungen an Cookie-Policy/Reverse-Proxy/Realm-Flows im Rahmen dieses Tickets; Ziel ist primär UX-Konsistenz + Guidance in Fehlerfällen.
