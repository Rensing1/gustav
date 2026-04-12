# Plan: Auth-Härtung nach `svelte-refactor`

## User Story

Als Lernende oder Lehrkraft
möchte ich nach dem Login über eine normale Unterrichtsdauer und typische Nachbereitung hinweg stabil angemeldet bleiben,
damit ich nicht durch ablaufende Zwischen-Sessions, fragile Redirects oder fehlerhafte Keycloak-Error-Flows aus dem Arbeitsfluss gerissen werde.

## BDD-Szenarien

### BFF-Session-Lebensdauer

1. Given eine gültige BFF-Session mit abgelaufenem Access-Token, When das Frontend einen geschützten Backend-Read startet, Then versucht die Session-Brücke zuerst einen Refresh statt die Session sofort zu verwerfen.
2. Given eine BFF-Session, deren fachliche Session-Lebensdauer abgelaufen ist, When das Frontend die Session liest, Then wird sie als ungültig behandelt und serverseitig bereinigt.
3. Given die Standardkonfiguration, When Login und Session-Bridge erfolgreich sind, Then sind App-Session und BFF-Session standardmäßig 24 Stunden gültig.

### Interner BFF-Store

1. Given ein Request ohne internen Shared-Secret-Header, When `/backend-internal/app/bff-session` aufgerufen wird, Then antwortet der Server mit API-Semantik (`401`) und niemals mit Browser-Redirect.
2. Given ein Request mit gültigem Shared-Secret, When `PUT/GET/PATCH/DELETE /backend-internal/app/bff-session` aufgerufen werden, Then funktioniert der Maschinen-CRUD weiter.

### OIDC-Callback und Redirects

1. Given zwei parallele Login-Flows, When der erste Callback zurückkommt, Then wird genau der passende Flow per `state` konsumiert und der andere bleibt gültig.
2. Given ein erfolgreicher SvelteKit-Callback, When die Tokens gegen App- und BFF-Session synchronisiert werden, Then setzt die Antwort sowohl `gustav_bff_session` als auch `gustav_session` und leitet auf das gespeicherte In-App-Ziel um.
3. Given fehlende oder ungültige Callback-Daten, When `/auth/callback` antwortet, Then liefert die Route `400` plus `Cache-Control: private, no-store`.

### Lernraum-Loader

1. Given eine abgelaufene oder fehlende Session, When Lernkurs- oder Lerneinheit-Loader laufen, Then bleibt der Guard-Redirect erhalten und wird nicht in `500` oder `fail(400)` umgewandelt.
2. Given eine Action im Lernraum ohne gültige Session, When der Guard einen Redirect auslöst, Then wird dieser Redirect weitergeworfen statt als generischer Formularfehler maskiert.

### Keycloak-Fehlerseiten

1. Given ein Keycloak-Error-/Expired-/Info-Kontext ohne `pageRedirectUri`, When das Theme rendert, Then entsteht keine FreeMarker-Ausnahme.
2. Given fehlende optionale Kontextdaten wie `client.baseUrl` oder `url.registrationUrl`, When eine Recovery-Seite rendert, Then bleibt die Seite benutzbar und zeigt nur sichere Links.

## Vertrags- und Interface-Änderungen

- `api/openapi.yml`
  - `/auth/callback` beschreibt die reale SvelteKit-Frontdoor inklusive beider Cookies.
  - Fehlerantworten für `400` und `502` werden explizit beschrieben.
  - Cookie- und TTL-Beschreibungen werden auf die 24h-Policy aktualisiert.
- Neue ENV-Variablen:
  - `BFF_SESSION_TTL_SECONDS`
  - `BFF_INTERNAL_SHARED_SECRET`
- Persistenz:
  - `public.bff_sessions` trennt `access_token_expires_at` und `session_expires_at`.

## Technische Leitentscheidungen

- Standard-TTL für App-Session und BFF-Session: `86400` Sekunden.
- `Angemeldet bleiben` bleibt IdP-seitig; die App-Session erhält keine checkbox-spezifische Sonderlogik.
- Der bestehende Hotfix-Ansatz wird nicht direkt übernommen, sondern in ein sauberes Zwei-Zeiten-Modell überführt.
- Der interne BFF-Store wird durch Shared Secret und API-Semantik abgesichert, nicht nur durch Routing.
