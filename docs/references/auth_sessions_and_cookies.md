# Auth, Sessions und Cookies — Referenz

Ziel: Eine kanonische technische Referenz für den aktuellen Auth-Stack von GUSTAV. Dieses Dokument erklärt Zuständigkeiten, Flows, Cookies, Session-TTLs, interne Grenzen und typische Fehlerbilder.

## Überblick

GUSTAV verwendet drei klar getrennte Schichten:

- Keycloak ist der Identity Provider (IdP) für Login, Registrierung, Passwort-Reset und Remember-me.
- SvelteKit in `frontend/` ist der Browser-BFF. Diese Schicht verarbeitet den öffentlichen `/auth/*`-Flow des Browsers und hält Token-Material vom Browser fern.
- FastAPI in `backend/web` mintet und validiert die stabile App-Session `gustav_session` für bestehende cookie-authentifizierte APIs und interne Server-Flows.

Wichtig: Der Browser arbeitet nicht direkt mit OIDC-Tokens. Er hält nur opake Cookies. Access- und Refresh-Token liegen serverseitig in der BFF-Session.

## Zuständigkeiten

- Keycloak:
  - zeigt Login-, Registrierungs- und Passwort-Reset-Seiten,
  - führt den Authorization-Code-Flow mit PKCE aus,
  - verwaltet IdP-Session und optional Remember-me.
- SvelteKit-BFF:
  - startet `/auth/login`, `/auth/register`, `/auth/password`, `/auth/forgot`,
  - verarbeitet `/auth/callback`,
  - speichert OIDC-Tokens serverseitig als BFF-Session,
  - synchronisiert nach erfolgreichem Callback die stabile App-Session im Backend.
- FastAPI:
  - mintet `gustav_session` über `/api/app/session-sync`,
  - validiert `gustav_session` für `/api/*`,
  - verwendet die App-Session für bestehende APIs, SSR-nahe Guards und H5P.

## Login-Flow

1. Browser ruft `GET /auth/login` auf `app.localhost` auf.
2. SvelteKit erzeugt PKCE-Daten, `state` und `nonce`.
3. SvelteKit speichert den Flow serverseitig über das Cookie `gustav_bff_oidc_flow`.
4. Browser wird zu Keycloak (`id.localhost`) umgeleitet.
5. Nach erfolgreichem Login ruft Keycloak `GET /auth/callback` auf `app.localhost` auf.
6. SvelteKit tauscht den Code gegen Tokens, prüft `iss`, `aud` und `nonce` und legt die BFF-Session an.
7. SvelteKit ruft `POST /api/app/session-sync` im Backend auf, damit FastAPI die stabile App-Session mintet.
8. Der Callback setzt zwei Cookies:
   - `gustav_bff_session`
   - `gustav_session`
9. Danach arbeitet der Browser nur noch mit diesen opaken Cookies.

## Logout-Flow

1. Browser ruft `GET /auth/logout` auf.
2. SvelteKit löscht zuerst die BFF-Session.
3. SvelteKit ruft das Backend-Logout an, damit `gustav_session` gelöscht wird.
4. Anschließend erfolgt die Weiterleitung zum Keycloak-End-Session-Endpoint.
5. Keycloak beendet die IdP-Session und leitet zurück zu `/auth/logout/success`.

Wenn verfügbar, wird `id_token_hint` genutzt. Das verbessert die Kompatibilität mit dem IdP-Logout und verhindert unnötige Fallbacks auf `client_id`-only.

## Cookies

### `gustav_bff_oidc_flow`

- Besitzer: SvelteKit-BFF
- Zweck: temporärer OIDC-Flow-Speicher für `state`, PKCE-`code_verifier`, `nonce` und sicheren Redirect-Pfad
- Lebensdauer: kurzlebig nur für den laufenden Login-/Register-/Password-Flow
- Flags: `HttpOnly; Secure; SameSite=lax`
- Sichtbarkeit: host-only auf `app.localhost`, Pfad `/auth`

Wichtig: Dieses Cookie ist kein Login-Cookie. Es dient nur dazu, den Redirect-basierten OIDC-Flow sicher zu korrelieren.

### `gustav_bff_session`

- Besitzer: SvelteKit-BFF
- Zweck: opaker Schlüssel auf serverseitig gespeicherte OIDC-Tokens
- Lebensdauer: BFF-Session-TTL
- Flags: `HttpOnly; Secure; SameSite=lax`
- Sichtbarkeit: host-only auf `app.localhost`

Die eigentlichen Tokens liegen serverseitig in `public.bff_sessions`.

### `gustav_session`

- Besitzer: FastAPI
- Zweck: stabile App-Session für bestehende cookie-authentifizierte APIs
- Lebensdauer: App-Session-TTL
- Flags: `HttpOnly; Secure; SameSite=lax`
- Sichtbarkeit: host-only auf `app.localhost`

Dieses Cookie ist die Quelle der Authentifizierung für `/api/me`, viele Teaching-/Learning-APIs und den H5P-Service.

## Warum gibt es zwei Sessions?

Die Trennung ist absichtlich:

- Die BFF-Session kapselt OIDC-Tokens und Refresh-Logik.
- Die App-Session hält die bestehende Backend- und API-Semantik stabil.

Dadurch kann GUSTAV browserseitig sichere Cookies behalten, ohne Access- oder Refresh-Token an den Browser auszugeben, und gleichzeitig bestehende cookie-authentifizierte Backend-Endpunkte weiterverwenden.

## Session-Speicher und TTLs

### BFF-Session

Die BFF-Session speichert zwei verschiedene Zeiten:

- `access_token_expires_at`
- `session_expires_at`

Das ist wichtig:

- Ein abgelaufener Access-Token bedeutet nicht automatisch Logout.
- Solange `session_expires_at` noch nicht erreicht ist, kann der BFF den Access-Token über den Refresh-Token erneuern.

Standardwerte:

- `BFF_SESSION_TTL_SECONDS` steuert die Lebensdauer der BFF-Session.
- Wenn nicht gesetzt, wird `APP_SESSION_TTL_SECONDS` als Fallback verwendet.
- In GUSTAV ist der aktuelle Default 24 Stunden.

### App-Session

Die App-Session lebt unabhängig von der OIDC-Access-Token-Lebensdauer.

- TTL-Quelle: `APP_SESSION_TTL_SECONDS`
- aktueller Default: 24 Stunden
- Speicherung:
  - DEV typischerweise In-Memory
  - prod-nah und PROD in `public.app_sessions`

### Remember-me

Remember-me in Keycloak verlängert nur die IdP-Session. Es verändert nicht die Semantik von `gustav_bff_session` oder `gustav_session`. In der Praxis kann eine verlängerte Keycloak-Session dazu führen, dass spätere Re-Authentifizierung weniger Reibung erzeugt, aber die App- und BFF-TTL bleiben eigenständige GUSTAV-Entscheidungen.

## Interne Grenzen

### `/backend-internal/app/bff-session`

Diese Route ist rein intern.

- Sie ist nicht Teil des öffentlichen Browser-Vertrags.
- Sie wird vom SvelteKit-BFF verwendet, um BFF-Sessions anzulegen, zu lesen, zu aktualisieren und zu löschen.
- Zugriffsschutz erfolgt über `BFF_INTERNAL_SHARED_SECRET`.

Wichtig: Diese Route darf nie auf Browser-Redirect- oder Public-Allowlist-Semantik angewiesen sein. Ein Request ohne Shared Secret muss API-artig fehlschlagen, nicht als HTML-Login-Redirect enden.

## Relevante ENV-Variablen

- `KC_BASE_URL`: interner Keycloak-Endpoint für Server-zu-Server-Aufrufe
- `KC_PUBLIC_BASE_URL`: browserseitiger Keycloak-Host
- `KC_REALM`
- `KC_CLIENT_ID`
- `WEB_BASE` / `ORIGIN`
- `FRONTEND_SESSION_SECRET`: Signatur für BFF-Flow-Cookies
- `BFF_INTERNAL_SHARED_SECRET`: Schutz der internen BFF-Session-Route
- `APP_SESSION_TTL_SECONDS`
- `BFF_SESSION_TTL_SECONDS`
- `FRONTEND_SESSION_COOKIE_NAME`

In prod-artigen Umgebungen müssen `FRONTEND_SESSION_SECRET` und `BFF_INTERNAL_SHARED_SECRET` gesetzt sein. Platzhalter oder leere Werte sind Konfigurationsfehler.

## Typische Fehlerbilder

### `400 invalid_code_or_state`

Typische Ursachen:

- abgelaufener oder fehlender Flow
- parallele Login-Flows mit ungültigem `state`
- beschädigtes oder ungültig signiertes Flow-Cookie

### `400 invalid_nonce` oder `400 invalid_id_token`

Typische Ursachen:

- `nonce`-Mismatch
- ungültiges ID-Token
- falscher IdP- oder Client-Kontext

### `502 session_setup_failed`

Typische Ursachen:

- BFF-Session konnte nicht angelegt werden
- `/api/app/session-sync` konnte keine App-Session minten
- fehlendes oder falsches `BFF_INTERNAL_SHARED_SECRET`
- Datenbankschema und Laufzeitmodell der BFF-Session sind nicht kompatibel

### `/api/me` liefert `401` direkt nach erfolgreichem Login

Typische Ursachen:

- `gustav_session` wurde im Callback nicht gesetzt
- der Callback war in Wahrheit ein `502 session_setup_failed`
- App-Session wurde nicht im Backend synchronisiert

### `/api/app/session-bootstrap` liefert `401`

Der öffentliche Backend-Vertrag bleibt beim Response-Body `{"error": "unauthenticated"}`. Für die Diagnose werden niedrig-kardinale Gründe ohne Token, Cookies, Session-IDs oder personenbezogene Daten dokumentiert: `session_bootstrap_missing_bearer`, `session_bootstrap_invalid_bearer`, `bff_session_missing`, `bff_session_read_empty`, `bff_session_token_refresh_failed` und `continuation_loop_guard_triggered`. Browser-Recovery ist nur erlaubt, wenn der Redirect ein lokaler In-App-Pfad aus dem aktuellen Pfad oder einem geprüften same-origin Referer ist. H5P-, Maschinen- und interne Routen ohne sicheren Browser-Kontext behalten ihre API-artige `401`-Semantik. Geschützte Browser-Routen probieren bei einem finalen `401` zuerst `/auth/continue`, damit eine noch aktive Keycloak-SSO-Sitzung die BFF- und App-Session ohne sichtbaren Login-Bounce reparieren kann. Wenn `/auth/continue` für denselben Redirect erneut gestartet würde, greift der Loop-Guard und fällt kontrolliert zum sichtbaren Login zurück.

### Logout endet ohne Redirect zum IdP

Typische Ursachen:

- Backend-Logout liefert keinen `location`-Header
- `id_token_hint` ist nicht mehr verfügbar und der Fallback ist defekt

## Debugging-Reihenfolge

Wenn Auth im prod-nahen Stack kaputt wirkt, ist die schnellste Prüfreihenfolge:

1. Kommt `/auth/callback` wirklich mit `302` zurück oder liefert es `400/502`?
2. Werden im Callback beide Cookies gesetzt?
3. Funktioniert `PUT /backend-internal/app/bff-session` intern mit Shared Secret?
4. Funktioniert `POST /api/app/session-sync`?
5. Liefert `/api/me` nach dem Callback `200`?

Bei E2E-Fehlern ist häufig nicht das Cookie-Transportverhalten kaputt, sondern ein früherer Callback-Fehler, der das Setzen von `gustav_session` verhindert.

## Source of truth

- Öffentlicher Vertrag: `api/openapi.yml`
- BFF-Implementierung: `frontend/src/lib/server/backend-auth.ts`
- BFF-Session-Verwaltung: `frontend/src/lib/server/session.ts`
- Backend-App-Session und interne BFF-Route: `backend/web/routes/app.py`
- Architekturelle Entscheidung für den Browser-BFF: `docs/adr/2026-03-23-sveltekit-browser-bff.md`

Diese Referenz erklärt den aktuellen Stand. Verhalten und Verträge werden letztlich durch Code, Tests und OpenAPI festgelegt.
