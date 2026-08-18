# Benutzerverwaltung (Identity & Access) — Referenz

Stand: Version 0.0.4, zuletzt geprüft am 2026-08-16.

Ziel: Übersicht über Authentifizierung, Session-Handling und den UserContextDTO, damit nachgelagerte Kontexte (z. B. „Unterrichten“) Nutzer stabil und datenschutzfreundlich adressieren.

Für die kanonische technische Referenz zu Login-Flow, Cookies, BFF-Session,
App-Session und Fehlerbildern siehe:
`docs/references/auth_sessions_and_cookies.md`.

## Überblick
- IdP: Keycloak (Realm `gustav`), OIDC Authorization Code Flow mit PKCE.
- GUSTAV verwendet zusätzlich zum IdP eine Browser-BFF-Session und eine
  stabile App-Session.
- Die eigentlichen Auth- und Cookie-Details sind in
  `docs/references/auth_sessions_and_cookies.md` beschrieben.
- Anzeigename: Bei Registrierung optionales Feld „Wie möchtest du genannt werden?“ → Keycloak User-Attribut `display_name` → Token-Claim `gustav_display_name`.

## API
- `GET /auth/login` → Redirect zu IdP.
- `GET /auth/callback` → Code-Exchange, ID-Token verifizieren, BFF-Session und
  App-Session synchronisieren.
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

### Lehrkraftsichtbare Schülerbezeichnungen

Der allgemeine Anzeigename des eigenen Profils ist nicht die Bezeichnung, die
Lehrkräfte in Kurs-, Live-, Sorgenfach- und Diagnostikansichten sehen. Dort gilt
ein eigener, serverseitiger Vertrag:

1. Nur ein vollständig gepflegtes Paar aus `firstName` und `lastName` wird als
   `Vorname Nachname` ausgegeben.
2. Fehlt ein Namensteil, wird exakt der lokale Teil der E-Mail beziehungsweise
   eines E-Mail-artigen Benutzernamens verwendet.
3. Ohne sicheren Identifier erscheint `Unbekannt`.

Das frei gesetzte `display_name` und das opake OIDC-Subject werden in diesen
Lehrkraftansichten nie als Schülerbezeichnung ausgegeben. Die fertige
Bezeichnung entsteht im Identity-Adapter; Frontends formatieren sie nicht neu.

## Token-Claims (Keycloak)
- Pflicht: `sub`, `aud`, `iss`, `exp` (OIDC Standard)
- Rollen: `realm_access.roles`
- Optional: `gustav_display_name` (User-Attribut `display_name`, als OIDC Protocol‑Mapper im Client `gustav-web` konfiguriert)

## Session-Speicher
- App-Session:
  - DEV: In‑Memory (schnell, aber flüchtig)
  - PROD: Postgres/Supabase (Tabelle `public.app_sessions`)
  - Spalten: `session_id` (PK), `sub`, `roles` (JSONB), `name`, `id_token`, `expires_at`
  - RLS aktiviert; Zugriffe nur mit Service‑Rolle (Clients greifen nicht direkt zu)
  - Migration: `supabase/migrations/20251019135804_persistent_app_sessions.sql`
- BFF-Session:
  - speichert OIDC-Tokens serverseitig getrennt von der App-Session
  - Details zu TTL und Speichersemantik siehe
    `docs/references/auth_sessions_and_cookies.md`

## Sicherheit
- Signaturprüfung ID‑Token über JWKS; Fehlerfälle mit 400 und `Cache-Control: private, no-store`.
- `state` und `nonce` im Login‑Flow; `nonce` wird gegen ID‑Token geprüft.
- Cookies sind host-only und verwenden `HttpOnly; Secure; SameSite=lax`.
- Die genaue Rolle von `gustav_bff_oidc_flow`, `gustav_bff_session` und
  `gustav_session` ist in `docs/references/auth_sessions_and_cookies.md`
  beschrieben.
- Open Redirects verhindert: In‑App‑Pfadprüfung für Redirect‑Parameter.
- Keycloak-Client `gustav-web`:
  - `webOrigins` soll nur explizite Origins (z. B. `https://app.gustav.example`, `https://localhost/*`, `https://app.localhost/*`) enthalten – niemals `*`.
  - Das Plan-Dokument `docs/plan/2025-11-30-PR-fix.md` dokumentiert den Must-Fix, die Referenz-`realm-gustav.json` an dieser Stelle auf konkrete Origins umzustellen.

## Remember-me (IdP-Session vs. App-Session)

- Keycloak-Feature „Remember me“:
  - Wird im Realm `gustav` optional aktiviert und steuert eine verlängerte IdP-Session (Keycloak-Sitzung).
  - In der Referenzrealm `gustav` ist Remember-me aktuell aktiviert; andere Deployments können das Feature in Keycloak nach Bedarf ein- oder ausschalten.
  - Die GUSTAV-Login-Seite zeigt in diesem Fall eine Checkbox „Angemeldet bleiben“ unterhalb des Passwortfeldes.
  - Standardzustand: Die Checkbox ist nicht vorausgewählt, insbesondere um sichere Defaults auf gemeinsam genutzten Geräten zu wahren.
- Policy-Hinweis:
  - Empfehlung: Nur auf privaten Geräten aktivieren; auf Schul-/Shared-Geräten deaktiviert lassen.
  - Admins können das Feature im Realm abschalten, falls das Sicherheitskonzept kürzere Sitzungen erzwingt.
- Wirkung auf Sessions:
  - „Angemeldet bleiben“ verlängert ausschließlich die IdP-Session nach Keycloak-Konfiguration (z. B. `SSO Session Max` vs. `SSO Session Idle` mit Remember-me-Werten).
  - Die GUSTAV-BFF-Session und App-Session behalten ihre eigene TTL; sie können
    unabhängig von der IdP-Session auslaufen.
  - Praktisch bedeutet das: Auf privaten Geräten führt Remember-me dazu, dass der erneute Login seltener nötig ist; auf geteilten Geräten sollte die Option nicht genutzt werden.
- UX-Hinweis:
  - In der UI kann ein kurzer Text unter der Checkbox darauf hinweisen, dass „Angemeldet bleiben“ nur auf privaten Geräten verwendet werden sollte.
  - Lehrkräfte können diesen Unterschied (IdP-Session vs. App-Session) im Support-Kontext erklären, ohne technische Details zur Token-Lebensdauer kennen zu müssen.

## Registrierung & Domain-Whitelist

- Registrierung findet ausschließlich bei Keycloak statt (`/auth/register` → OIDC-Registrierungsendpunkt `/protocol/openid-connect/registrations`). GUSTAV ändert dabei nicht die Sicherheitsparameter des Authorization-Code-Flows: `state`, `nonce`, PKCE und die geprüfte Callback-URL bleiben erhalten.
- Optionaler Query-Parameter `login_hint`:
  - Wird als vorausgefüllte E-Mail im Registrierungsformular verwendet.
  - Vor dem Redirect prüft GUSTAV optional die Domain:
    - Env-Variable `ALLOWED_REGISTRATION_DOMAINS` (kommagetrennt, z. B. `@school.example`)
    - Bei erlaubter Domain → normaler OIDC-Registrierungsstart über den SvelteKit-Browser-BFF.
    - Bei nicht erlaubter oder offensichtlich ungültiger E-Mail → `400` mit JSON  
      `{ error: "invalid_email_domain", detail: "Die Registrierung ist nur mit einer Schul-E-Mail-Adresse erlaubt. Erlaubte Domains: <Liste aus ALLOWED_REGISTRATION_DOMAINS>" }`.
- Dieselbe Env-Variable steuert auch den Keycloak-Realm-Import beim Image-Build (`docker compose up -d --build`); damit lesen App, Browser-BFF und IdP dieselbe Quelle der Wahrheit.
- Wenn sich die Policy in einer bereits laufenden Installation ändert, muss der bestehende Realm anschließend gezielt neu importiert oder synchronisiert werden; der Importpfad ist weiterhin ein Bootstrap-Schritt.
- Die eigentliche, verbindliche Domain-Policy wird in Keycloak erzwungen; GUSTAV bleibt die vorgeschaltete, nutzerfreundliche Guardrail.

## E-Mail-Verifikation

- Keycloak-Realm `gustav`:
  - Die Referenzkonfiguration erzwingt `verifyEmail=true` und verwendet `emailTheme=gustav`.
  - Keycloak verschickt Verifizierungs- und Passwort-Reset-E-Mails über das konfigurierte SMTP-Relay (siehe unten).
- GUSTAVs Callback (`/auth/callback`):
  - Liest das Claim `email_verified` zwar aus dem ID-Token, erzwingt aber keinen eigenen Block basierend auf diesem Flag.
  - GUSTAV vertraut darauf, dass Keycloak nur solche Benutzer aktiviert/anmeldbar macht, die den schulischen Anforderungen entsprechen (z. B. über Admin-Workflows).
  - Fehlt das Claim `email_verified`, bleibt das Login-Verhalten unverändert (Backwards-Kompatibilität).

## Passwort-Reset-Flow

- „Passwort vergessen?“:
  - Self-Service-Reset per E-Mail ist im Realm `gustav` aktiviert (`resetPasswordAllowed=true`).
  - Der Endpunkt `/auth/forgot` leitet auf die Keycloak-Reset-Credentials-Seite; Keycloak verschickt die Passwort-Reset-E-Mail.
  - Der Link in der E-Mail führt auf die „Neues Passwort setzen“-Seite im GUSTAV-Login-Theme (Update-Password-Template).
- Zusätzlich können Admins bei Bedarf über Keycloak-Admin-Aktionen (z. B. „Execute actions › UPDATE_PASSWORD“) ein Reset erzwingen; Passwort-Reset-E-Mails bleiben ausschließlich bei Keycloak.

## SMTP & E-Mail-Theme (Keycloak)

### SMTP-Konfiguration (Umgebung)

Keycloak und der bestehende GUSTAV-Hintergrundworker beziehen ihre SMTP-Settings aus denselben Env-Variablen (lokal = Prod, gleiche Namen). Keycloak ist für Verifikation und Passwort-Reset zuständig; der Worker sendet Kurs-Einladungen. Es gibt keinen zusätzlichen Maildienst oder Container.
Im Repo werden neutrale Platzhalter verwendet; vor Produktivbetrieb müssen diese pro Schule angepasst werden:

- `KC_SMTP_HOST=smtp.school.example`
- `KC_SMTP_PORT=587`
- `KC_SMTP_USER=gustav-smtp-user`
- `KC_SMTP_PASSWORD=` (leer im Repo; nur in `.env` setzen)
- `KC_SMTP_FROM=noreply@school.example`
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

Der Worker akzeptiert für Kurs-Einladungen ausschließlich `KC_SMTP_STARTTLS=true` und erzwingt STARTTLS mit normaler Zertifikatsprüfung. Bei fehlender oder deaktivierter TLS-Konfiguration nimmt er keine Nachricht aus der Queue. Danach authentifiziert er sich mit `KC_SMTP_USER` und `KC_SMTP_PASSWORD`. Logs enthalten weder Empfängeradressen noch Klassenlinks oder Nachrichtentexte. Temporäre SMTP- und Netzfehler werden mit gedeckeltem Backoff bis zu fünf Zustellversuchen erneut verarbeitet; permanente Fehler bleiben endgültig und werden durch die manuelle Wiederholungsaktion nicht erneut versendet.

## Kurs-Einladung und automatische Mitgliedschaft

- Nur der Owner eines aktiven, vollständig konfigurierten Kurses kann unter „Mitglieder verwalten“ → „Klasse einladen“ einen Klassenlink erzeugen.
- Der gemeinsame Link ist fest 24 Stunden gültig. Ein neuer Link widerruft den bisherigen sofort; Archivierung widerruft ihn ebenfalls und eine spätere Wiederherstellung reaktiviert ihn nicht.
- Derselbe Link kann kopiert, als QR-Code heruntergeladen, im nativen Browser-Vollbild beziehungsweise im seitenfüllenden Fallback angezeigt und an bis zu 100 deduplizierte Schul-E-Mail-Adressen gesendet werden. Der Fallback sperrt den Hintergrund für Tastatur und assistive Bedienung, hält den Fokus auf der Schließen-Aktion und entfernt beim Schließen seinen eigenen Browser-History-Eintrag.
- Der Link trägt das Capability-Token ausschließlich im URL-Fragment. Die Einladungsseite entfernt es aus der Browserhistorie, prüft es per Request Body und speichert die akzeptierte Beitrittsabsicht in einem signierten Cookie mit `HttpOnly; Secure; SameSite=Lax`.
- Neue Lernende durchlaufen die normale Keycloak-Registrierung samt E-Mail-Bestätigung, bestehende Lernende den normalen Login. Nach dem Auth-Rücksprung löst GUSTAV die Einladung serverseitig ein. Läuft der Link vorher ab oder wird er widerrufen, entsteht keine Mitgliedschaft.
- Erneute Einlösung ist idempotent. Wurde ein über diesen Link beigetretenes Mitglied entfernt, blockiert derselbe Link den Wiedereintritt; erst eine bewusste Rotation durch die Lehrkraft erlaubt ihn wieder.

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
    - Footer mit Support-Hinweis: „Bei Fragen melde dich unter: support@school.example“.

## Integration in UI
- Die SvelteKit-Top-Bar zeigt den Anzeigenamen (`name`) und ausschließlich die für die aktuellen Rollen erlaubten Produkträume.
- Geschützte SvelteKit-Seiten lesen die gemeinsame Session-Projektion im Root-Layout. Fehlt oder verfällt die BFF-Session, wird der sichere OIDC-Wiederanmeldungsfluss gestartet.
- Der Browser spricht für komplexe Seiten primär mit SvelteKit. FastAPI bleibt Auth-Bridge und API-Adapter; ehemalige HTMX-Produktpfade sind nicht mehr aktiv.

## Aktueller Betriebsstand und Ausblick
- Das verbindliche Compose-Profil verwendet mit `SESSIONS_BACKEND=db` persistente App-Sessions. In-Memory-Stores sind explizite Test-Doubles und kein produktiver Fallback.
- Auch BFF-Sessions und CLI-Tokens werden im normalen Compose-Betrieb datenbankgestützt und fail-closed betrieben.
- Rollen- und Ownership-Guards sind als wiederverwendbare Policies beziehungsweise zentrale Adaptergrenzen etabliert.
- Eine IServ-Anbindung und ein dafür geprüftes Account-Linking sind weiterhin geplant.
