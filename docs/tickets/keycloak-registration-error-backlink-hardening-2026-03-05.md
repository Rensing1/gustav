# Ticket: Keycloak Registrierung/Verify - Ruecksprungziele auf Error/Info-Seiten haerten

Status: offen  
Prioritaet: hoch  
Umgebung: Produktion (`app.gustav-lernplattform.de`, `id.gustav-lernplattform.de`)  
Erstellt am: 05. Maerz 2026

## Kontext

- Im Registrierungs-/Verify-Flow treten weiterhin intermittente Fehlerpfade auf (z. B. Cookie-Kontextverlust, bereits verifizierte E-Mail).
- Die Seiten sind inzwischen meist gethemt, aber der Rueckweg ist in diesen Error/Info-Pfaden nicht durchgaengig nutzerfuehrend.

## Problem

Auf Verify-/Error-Pfaden landen Nutzer teils auf Seiten mit unpassendem Ruecksprungziel (praktisch kein sauberer Weg zur App-Loginstrecke).

Beobachtetes Muster:
- Wiederholte Events im Incident-Fenster mit `VERIFY_EMAIL_ERROR` und
  `redirect_uri=https://id.gustav-lernplattform.de/realms/gustav/account/`.
- Das Ziel `id.../account/` wird von Nutzern als fehlerhafter Backlink wahrgenommen, wenn sie eigentlich zur App zurueck muessen.

## Erwartetes Verhalten

- Error-/Info-Seiten im Auth-Flow geben immer einen klaren, robusten Rueckweg in die App.
- "Zurueck zur App" soll auf ein App-Ziel zeigen (z. B. Login/Start), nicht auf ein nicht hilfreiches IdP-Kontoziel.
- Verify-/Error-Faelle bleiben visuell konsistent im GUSTAV-Theme.

## Technische Hypothese

Die aktuelle Priorisierung der Linkziele (`pageRedirectUri`, `client.baseUrl`, `url.loginUrl`) ist in einzelnen Error/Verify-Pfaden nicht robust genug; dadurch kann ein aus UX-Sicht falsches Ziel bevorzugt werden.

## Gewuenschte Umsetzung

1. Link-Priorisierung in den Keycloak-Templates haerten:
- `keycloak/themes/gustav/login/info.ftl`
- `keycloak/themes/gustav/login/error.ftl`
- `keycloak/themes/gustav/login/login-page-expired.ftl`
- `keycloak/themes/gustav/login/_gustav_error_components.ftl`

2. Zielregeln:
- Primaer App-Ziel fuer "Zurueck zur App" (app-domain-basierte Rueckkehr).
- `id.../realms/.../account/` nicht als Default-"Back to App"-Ziel verwenden.
- Fallbacks fuer Login/Register weiter anbieten.

3. Tests erweitern:
- `backend/tests/test_keycloak_theme_files.py`
- Contract-Test fuer Link-Prioritaet und Ausschluss des unpassenden IdP-Kontoziels als primarer App-Backlink.

## Akzeptanzkriterien

- Bei `VERIFY_EMAIL_ERROR` und vergleichbaren Error-Pfaden zeigt der Haupt-CTA zur App.
- Keine regressiven Theme-Brueche auf Error-/Info-Seiten.
- Testsuite deckt die Linkziel-Prioritaet ab und laeuft gruen.

## Nicht Ziel dieses Tickets

- Keine Aenderung an Cookie-Policy/Browser-Tracking-Policies.
- Keine infra-/ops-spezifischen Runbook- oder Compose-Aenderungen.
