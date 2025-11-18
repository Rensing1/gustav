# Benutzerverwaltung (Identity & Access) — Referenz

Ziel: Übersicht über Authentifizierung, Session-Handling und den UserContextDTO, damit nachgelagerte Kontexte (z. B. „Unterrichten“) Nutzer stabil und datenschutzfreundlich adressieren.

## Überblick
- IdP: Keycloak (Realm `gustav`), OIDC Authorization Code Flow mit PKCE.
- App-Session: httpOnly-Cookie `gustav_session` (opaque), Session-Daten serverseitig.
- Cookie-Flags: Immer `HttpOnly; Secure; SameSite=lax` (host‑only, kein `Domain=`).
- Anzeigename: Bei Registrierung optionales Feld „Wie möchtest du genannt werden?“ → Keycloak User-Attribut `display_name` → Token-Claim `gustav_display_name`.

## API
- `GET /auth/login` → Redirect zu IdP.
- `GET /auth/callback` → Code-Exchange, ID-Token verifizieren (JWKS, iss, aud, exp), Session anlegen.
- `GET /auth/logout` → App-Session löschen, Redirect zu IdP End-Session (`id_token_hint` wenn vorhanden).
- `GET /auth/forgot` → Redirect zur IdP-Passwort-Reset-Seite (Keycloak verschickt die E-Mails).
- `GET /auth/register` → Redirect zur IdP-Registrierung; Domain-Whitelist kann `login_hint` vorab validieren.
- `GET /api/me` → 200 `{ sub, roles, name, expires_at }` oder 401 `{ error }` (mit `Cache-Control: private, no-store`).

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
  - Migration: `supabase/migrations/20251019135804_persistent_app_sessions.sql`

## Sicherheit
- Signaturprüfung ID‑Token über JWKS; Fehlerfälle mit 400 und `Cache-Control: private, no-store`.
- `state` und `nonce` im Login‑Flow; `nonce` wird gegen ID‑Token geprüft.
- Cookies httpOnly; in PROD optional `Max-Age=<TTL>`; Flags bleiben `Secure; SameSite=lax` (host‑only).
- Open Redirects verhindert: In‑App‑Pfadprüfung für Redirect‑Parameter.

## Registrierung & Domain-Whitelist

- Registrierung findet ausschließlich bei Keycloak statt (`/auth/register` → Authorization-Endpunkt mit `kc_action=register`).
- Optionaler Query-Parameter `login_hint`:
  - Wird als vorausgefüllte E-Mail im Registrierungsformular verwendet.
  - Vor dem Redirect prüft GUSTAV optional die Domain:
    - Env-Variable `ALLOWED_REGISTRATION_DOMAINS` (kommagetrennt, z. B. `@gymalf.de`)
    - Bei erlaubter Domain → normaler Redirect (302/204, je nach HTMX).
    - Bei nicht erlaubter oder offensichtlich ungültiger E-Mail → `400` mit JSON `{ error: "invalid_email_domain", detail: "Die Registrierung ist nur mit deiner IServ-Adresse (@gymalf.de) möglich." }`.
- Die eigentliche, verbindliche Domain-Policy muss zusätzlich in Keycloak konfiguriert werden; GUSTAV ist eine vorgeschaltete, nutzerfreundliche Guardrail.

## E-Mail-Verifikation

- Keycloak-Realm `gustav`:
  - `verifyEmail=false`, `emailTheme=gustav` (branded Login- und E-Mail-Theme).
  - Keycloak verschickt Verifizierungs- und Passwort-Reset-E-Mails über SMTP (siehe unten), wenn diese Flows im IdP aktiviert sind.
- GUSTAVs Callback (`/auth/callback`):
  - Liest das Claim `email_verified` zwar aus dem ID-Token, erzwingt aber keinen eigenen Block basierend auf diesem Flag.
  - GUSTAV vertraut darauf, dass Keycloak nur solche Benutzer aktiviert/anmeldbar macht, die den schulischen Anforderungen entsprechen (z. B. über Admin-Workflows).
  - Fehlt das Claim `email_verified`, bleibt das Login-Verhalten unverändert (Backwards-Kompatibilität).

## Passwort-Reset-Flow

- „Passwort vergessen?“:
  - Self-Service-Reset per E-Mail ist im Realm `gustav` deaktiviert (`resetPasswordAllowed=false`), damit Passwörter kontrolliert über das Admin-Panel verwaltet werden können.
  - Der Endpunkt `/auth/forgot` existiert weiterhin als technischer Redirect-Helfer in GUSTAV, wird aber in der Standard-Login-UI nicht prominent verlinkt.
- Passwort-Resets für Schüler*innen/Lehrkräfte erfolgen in der Praxis über Keycloak-Admin-Aktionen (z. B. „Execute actions › UPDATE_PASSWORD“); GUSTAV sendet keine eigenen Passwort-Reset-E-Mails.

## SMTP & E-Mail-Theme (Keycloak)

### SMTP-Konfiguration (Umgebung)

Die Keycloak-Containerkonfiguration bezieht SMTP-Settings aus Env-Variablen (lokal = Prod, gleiche Namen):

- `KC_SMTP_HOST=gymalf.de`
- `KC_SMTP_PORT=587`
- `KC_SMTP_USER=hennecke`
- `KC_SMTP_PASSWORD=` (leer im Repo; nur in `.env` setzen)
- `KC_SMTP_FROM=hennecke@gymalf.de`
- `KC_SMTP_FROM_NAME=GUSTAV-Lernplattform`
- `KC_SMTP_AUTH=true`
- `KC_SMTP_STARTTLS=true`

Diese Werte werden in `docker-compose.yml` auf die Quarkus-/Keycloak-SMTP-Konfiguration gemappt:

- `KC_SPI_EMAIL_SENDER_DEFAULT_HOST`
- `KC_SPI_EMAIL_SENDER_DEFAULT_PORT`
- `KC_SPI_EMAIL_SENDER_DEFAULT_FROM`
- `KC_SPI_EMAIL_SENDER_DEFAULT_FROM_DISPLAY_NAME`
- `KC_SPI_EMAIL_SENDER_DEFAULT_USERNAME`
- `KC_SPI_EMAIL_SENDER_DEFAULT_PASSWORD`
- `KC_SPI_EMAIL_SENDER_DEFAULT_AUTH`
- `KC_SPI_EMAIL_SENDER_DEFAULT_STARTTLS`

### E-Mail-Theme

- Login-Theme `gustav`:
  - Gemeinsames CSS mit der App (Button-Stile, Typografie, Layout).
  - Deutsche und englische Message-Bundles (`messages_de.properties` / `messages_en.properties`).
- E-Mail-Theme `gustav`:
  - HTML-Templates:
    - `email-verification.ftl` (Betreff und Inhalt zur E-Mail-Bestätigung).
    - `password-reset.ftl` (Betreff und Inhalt zum Passwort-Reset).
  - Einheitliches Layout:
    - Logo/Branding „GUSTAV-Lernplattform“.
    - Klarer, minimalistischer Fließtext (Deutsch, freundlich-neutral, gleicher Text für Schüler*innen und Lehrkräfte).
    - Primärer Button mit Aufruf zum Handeln (E-Mail bestätigen / Passwort zurücksetzen).
    - Footer mit Support-Hinweis: „Bei Fragen melde dich unter: hennecke@gymalf.de“.

## Integration in UI
- Sidebar zeigt den Anzeigenamen (`name`) und die primäre Rolle (Priorität: admin > teacher > student).
- HTMX: Unauthentisierte Teil‑Requests → `401` mit `HX-Redirect: /auth/login`.

## Erweiterungen (Ausblick)
- Persistente Sessions aktivieren via `SESSIONS_BACKEND=db` und DSN (psycopg3).
- IServ‑Anbindung (OIDC/SAML) und Account‑Linking über `sub`/E‑Mail.
- Rollen‑Guards als wiederverwendbare Policies für „Unterrichten“.
