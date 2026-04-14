# Plan: `/live` auf schnellen Summary-/Detail-Pfad umstellen

## Ziel

Die kanonische `/live`-Seite soll bei Schüler- und Aufgabenwechseln schnell reagieren,
ohne dabei die komplette Dashboard-Aggregation neu aufzubauen.

## Ansatz

- `/live` nutzt für den SSR-Start nur noch die schlanke Unit-Zusammenfassung plus optionales Detail-Sheet.
- Interaktive Klicks laden:
  - bei Schülerwechsel nur das Detail-Sheet für die Standardaufgabe
  - bei Aufgabenwechsel nur das Detail-Sheet
- Polling arbeitet gegen den Delta-Endpunkt und zieht die Summary nach, statt das vollständige Dashboard-Read-Model zu reconstruieren.
- Die Namensauflösung wird im Hot Path vereinheitlicht:
  - `Vorname Nachname`
  - Fallback `Mail-/Username-Localpart`
  - Final `"Unbekannt"`

## Umsetzung

- Neue BFF-GET-Routen für `/live/.../summary` und `/live/.../detail-sheet`
- Neuer lokaler Controller-State für Summary, Detail und Auswahl
- Dashboard-UI lokal aus Summary + Detail ableiten
- Teuren Keycloak-per-user-Token-Pfad aus dem Live-Hot-Path entfernen

## Verifikation

- Frontend-Interaktionstests für schnellen Schüler-/Aufgabenwechsel
- BFF-Tests für Summary- und Detail-Proxy
- Backend-Tests für konsistente Live-Namensauflösung in Summary und Detail-Sheet
