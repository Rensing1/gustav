# Keycloak Auth Theme Cache Busting

## Ziel

Änderungen am Keycloak-Auth-Theme sollen sofort im Browser sichtbar werden,
ohne dass Nutzer ihren Cache manuell löschen müssen.

## Problem

Keycloak liefert Theme-Ressourcen mit langem Browser-Cache aus. Wenn sich die
CSS-Datei ändert, aber die URL gleich bleibt, kann der Browser weiterhin die
alte Gestaltung verwenden.

## Entscheidung

- Das Theme behält cachbare Ressourcen.
- Sichtbare Theme-Dateien werden über eine explizite Theme-Version in
  `theme.properties` versioniert.
- Alle gebrandeten Login-/Register-/Reset-/Verify-/Info-/Error-Templates
  referenzieren `auth-theme.css` und `gustav.css` mit `?v=...`.

## Verifikation

- Contract-Test für `gustavThemeVersion` in `theme.properties`
- Contract-Test für versionierte Stylesheet-Links in allen relevanten
  Keycloak-Templates
- Laufzeitprüfung über `https://app.localhost/auth/login`
