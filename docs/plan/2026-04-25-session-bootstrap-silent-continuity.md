# Session bootstrap silent continuity

## User Story

Als angemeldete Lehrkraft oder lernende Person möchte ich eine geschützte GUSTAV-Seite hart neu laden können, ohne sichtbar zur Login-Seite geschickt zu werden, solange meine Keycloak-SSO-Sitzung noch aktiv ist und die App-Sitzung sicher validiert werden kann.

## BDD-Szenarien

- Given eine gültige App-Session und eine aktive Keycloak-SSO-Session, When der BFF-Bootstrap auf einem geschützten Page-Load fehlt, Then startet GUSTAV einen `prompt=none` Continuity-Flow und kehrt ohne Login-Eingabe zur ursprünglichen Seite zurück.
- Given eine gültige App-Session, aber keine aktive Keycloak-SSO-Session, When der Silent-Flow mit `login_required` zurückkommt, Then landet der Nutzer kontrolliert auf der normalen Login-Einstiegsseite mit Return-To.
- Given keine gültige App-Session, When der Bootstrap fehlt, Then bleibt das bisherige Login-Redirect-Verhalten unverändert.
- Given ein Bearer-only Backend-Endpunkt, When nur `gustav_session` vorhanden ist, Then authentifiziert dieser Endpunkt weiterhin nicht per Cookie-Fallback.

## Contract-First-Entwurf

- `GET /auth/continue` wird als öffentliche Browser-BFF-Route dokumentiert.
- Die Route akzeptiert optional `redirect` als sichere In-App-Pfadangabe.
- Sie erzeugt einen normalen Authorization-Code-Flow mit PKCE, aber setzt `prompt=none`.
- `/auth/callback` dokumentiert zusätzlich Keycloak-Error-Callbacks aus Silent-Flows.

## Umsetzung

- SvelteKit `+layout.server.ts` validiert bei fehlendem Bootstrap die bestehende App-Session über `/api/me`, indem nur `gustav_session` gezielt an den Backend-Internal-Host weitergereicht wird.
- Geschützte Page-Guards leiten bei `bootstrap == null` und `appSessionActive == true` auf `/auth/continue?redirect=<currentPath>` um.
- `backend-auth.ts` bekommt `startContinuationFlow()` und markiert Flow-Cookies mit `mode: "silent-continuity"`.
- `handleAuthCallback()` behandelt Silent-Errors kontrolliert und benutzt für Silent-Erfolg denselben Session-Setup-Pfad wie der normale Login.

## Tests

- OpenAPI-Vertrag für `/auth/continue`.
- Auth-Helper-Tests für `prompt=none`, sicheren Redirect, erfolgreichen Silent-Callback und `login_required`.
- Layout-/Guard-Contract gegen sichtbaren Login-Bounce bei validierter App-Session.
- Regression: `session-bootstrap` bleibt Bearer-only.
