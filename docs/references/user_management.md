# Benutzerverwaltung (Identity & Access) — Referenz

Ziel: Übersicht über Authentifizierung, Session-Handling und den UserContextDTO, damit nachgelagerte Kontexte (z. B. „Unterrichten“) Nutzer stabil und datenschutzfreundlich adressieren.

## Überblick
- IdP: Keycloak (Realm `gustav`), OIDC Authorization Code Flow mit PKCE.
- App-Session: httpOnly-Cookie `gustav_session` (opaque), Session-Daten serverseitig.
- Cookie-Flags: DEV `SameSite=lax`, PROD `Secure; SameSite=strict`; immer `HttpOnly`.
- Anzeigename: Bei Registrierung optionales Feld „Wie möchtest du genannt werden?“ → Keycloak User-Attribut `display_name` → Token-Claim `gustav_display_name`.

## API
- `GET /auth/login` → Redirect zu IdP.
- `GET /auth/callback` → Code-Exchange, ID-Token verifizieren (JWKS, iss, aud, exp), Session anlegen.
- `GET /auth/logout` → App-Session löschen, Redirect zu IdP End-Session (`id_token_hint` wenn vorhanden).
- `GET /auth/forgot`/`/auth/register` → Redirects zu IdP.
- `GET /api/me` → 200 `{ sub, roles, name, expires_at }` oder 401 `{ error }` (mit `Cache-Control: no-store`).

## UserContextDTO
Minimaler, kontextübergreifender Nutzerdatensatz:
- `sub`: Stabile, opake Benutzer-ID aus dem ID-Token (nicht die E-Mail).
- `roles`: Realm-Rollen (`student|teacher|admin`, gefiltert).
- `name`: Anzeigename (Prio: `gustav_display_name` > `name` > lokaler Teil der E‑Mail).

E-Mail wird bewusst nicht im DTO ausgegeben (Privacy by Design, geringere Koppelung).

## Token-Claims (Keycloak)
- Pflicht: `sub`, `aud`, `iss`, `exp` (OIDC Standard)
- Rollen: `realm_access.roles`
- Optional: `gustav_display_name` (User-Attribut `display_name`, als OIDC Protocol‑Mapper im Client `gustav-web` konfiguriert)

## Session-Speicher
- DEV: In‑Memory (schnell, aber flüchtig)
- PROD: Postgres/Supabase (Tabelle `public.app_sessions`)
  - Spalten: `session_id` (PK), `sub`, `roles` (JSONB), `name`, `id_token`, `expires_at`
  - RLS aktiviert; Zugriffe nur mit Service‑Rolle (Clients greifen nicht direkt zu)
  - Migration: `supabase/migrations/20251019_create_app_sessions.sql`

## Sicherheit
- Signaturprüfung ID‑Token über JWKS; Fehlerfälle mit 400 und `Cache-Control: no-store`.
- `state` und `nonce` im Login‑Flow; `nonce` wird gegen ID‑Token geprüft.
- Cookies httpOnly; in PROD mit `Secure` + `SameSite=strict` und `Max-Age`.
- Open Redirects verhindert: In‑App‑Pfadprüfung für Redirect‑Parameter.

## Integration in UI
- Sidebar zeigt den Anzeigenamen (`name`) und die primäre Rolle (Priorität: admin > teacher > student).
- HTMX: Unauthentisierte Teil‑Requests → `401` mit `HX-Redirect: /auth/login`.

## Erweiterungen (Ausblick)
- Persistente Sessions aktivieren via `SESSIONS_BACKEND=db` und DSN (psycopg3).
- IServ‑Anbindung (OIDC/SAML) und Account‑Linking über `sub`/E‑Mail.
- Rollen‑Guards als wiederverwendbare Policies für „Unterrichten“.

