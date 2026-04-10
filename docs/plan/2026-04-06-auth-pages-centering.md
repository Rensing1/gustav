# Plan: Auth-Seiten zentrieren und textlich straffen

## Ziel

- Die Auth-Seiten in Svelte und Keycloak sollen unter derselben Produktsprache erscheinen.
- Auf Auth-Routen bleibt die obere Markenleiste sichtbar, der normale Workspace-Seitenkopf jedoch nicht.
- Der eigentliche Auth-Kern wird sauber im verbleibenden Inhaltsbereich zentriert.
- Allgemeine Erklärtexte werden entfernt; übrig bleiben nur knappe Titel und notwendige Statushinweise.

## Umsetzung

- Auth-Routen in Svelte liefern Layout-Flags, damit der normale Seitenkopf ausgeblendet und ein eigener Auth-Inhaltsmodus aktiviert wird.
- `AuthFrame` wird so vereinfacht, dass `eyebrow` und `body` optional sind.
- `/`, `/register`, `/forgot-password` und `/auth/logout/success` werden textlich reduziert.
- Das Layout erhält einen Auth-Modus, der den Inhaltsbereich unterhalb der Markenleiste vertikal und horizontal zentriert.
- Die Keycloak-Templates behalten ihre Funktionalität, verlieren aber nicht notwendige Zusatztexte.

## Verifikation

- Frontend-Contract-Tests sichern die Route-Flags und die reduzierten Auth-Titel.
- Komponententests sichern, dass `AuthFrame` auch ohne Zusatzcopy korrekt rendert.
- Ein anschließender Frontend-Testlauf validiert die betroffenen Svelte-Komponenten und Route-Contracts.
