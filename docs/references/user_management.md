# Benutzerverwaltung (Identity & Access) — Referenz

Stand: gemeinsame Auth-Architektur, zuletzt geprüft am 2026-09-16.

Ziel: Übersicht über Authentifizierung, Session-Handling und den UserContextDTO, damit nachgelagerte Kontexte (z. B. „Unterrichten“) Nutzer stabil und datenschutzfreundlich adressieren.

Die technische Referenz zu OIDC, Cookies, Fristen und Fehlerzuständen steht in [Auth-Sitzungen und Cookies](auth_sessions_and_cookies.md).

## Überblick

- Keycloak verwaltet Passwörter, Verifikation, Rollen und SSO-Fristen.
- FastAPI verwaltet den vollständigen OIDC-Ablauf und die einzige GUSTAV-Sitzung. SvelteKit und H5P verwenden das gemeinsame Cookie.
- Der Anzeigename wird bei der Registrierung einmal erfasst und als Keycloak-Attribut `display_name` beziehungsweise Token-Claim `gustav_display_name` übertragen.

## API

- `GET /auth/login`, `/auth/register`, `/auth/forgot`, `/auth/password`: browsergebundener OIDC-Einstieg mit PKCE und Nonce.
- `GET /auth/continue`: begrenzte automatische Wiederanmeldung über bestehendes Keycloak-SSO.
- `GET /auth/callback`: einmalige State-Prüfung, Tokenprüfung und gemeinsame Sitzung.
- `GET /auth/logout`: Bestätigung ohne Abmeldung. `POST /auth/logout`: lokale Sitzung widerrufen und Keycloak-Abmeldung beginnen.
- `GET /auth/logout/callback`: browsergebundene Bestätigung der IdP-Abmeldung.
- `GET /api/me`: `{ sub, roles, name, expires_at }`, `401` bei fehlender Anmeldung oder `503` bei vorübergehender Nichtprüfbarkeit. Antworten bleiben `private, no-store`.

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

## Sitzung und Sicherheit

Lokal und produktiv verwendet FastAPI `public.app_sessions` und `public.auth_flows`. Zufällige Sitzungs-, State- und Browserbindungsschlüssel werden nur als Hash gespeichert. Tokens und PKCE-Verifier bleiben serverseitig; RLS und Tabellenrechte sperren Browserrollen aus. In-Memory-Sitzungen dienen ausschließlich als Test-Doubles für isolierte Fachtests.

ID-Tokens benötigen die Audience `gustav-web`, Access-Tokens die ausdrückliche Audience `gustav-api`. Signatur, Issuer, zeitliche Gültigkeit, Subject, Nonce, State, Browserbindung und PKCE werden geprüft. Sichere lokale Rücksprungziele werden zentral validiert. Cookies sind host-only mit `HttpOnly; Secure; SameSite=Lax`.

Cookie-Schreibzugriffe benötigen passende Browserherkunft, ergänzende CSRF-Token-Prüfungen bleiben aktiv. Ein übermittelter ungültiger Bearer-Token wird nicht durch ein Cookie ersetzt. Administrative Widerrufe wirken spätestens bei der nächsten Erneuerung des fünfminütigen Zugriffstokens.

## Angemeldet bleiben

Die Checkbox ist freiwillig und zunächst leer. Auf persönlichen Geräten ermöglicht sie eine Keycloak-Sitzung mit bis zu 30 Tagen Gesamtlaufzeit und Inaktivität. Ohne Remember-me gelten 24 Stunden Inaktivität und maximal sieben Tage. GUSTAV übernimmt die vom Token-Endpunkt bestätigte Refresh-Gültigkeit und führt keine unabhängige 24-Stunden-Grenze ein.

Das GUSTAV-Cookie bleibt ein Browser-Sitzungscookie. Nach einem Browser-Neustart kann Keycloak es über seine persistente Remember-me-Sitzung wiederherstellen. Ein signierter Marker begrenzt automatische Versuche auf einen pro Minute. Nach ausdrücklicher Abmeldung wird automatische Wiederanmeldung unterdrückt.

## Registrierung und Domain-Prüfung

`/register` führt direkt zu Keycloak. Anzeigename, Schul-E-Mail und Passwort werden einmal eingegeben; alle fünf aktiven Passwortanforderungen stehen vor der Eingabe zusammen sichtbar. Fehler bleiben Feldern zugeordnet, sichere Eingaben erhalten; Passwörter werden nicht erneut ausgegeben.

`ALLOWED_REGISTRATION_DOMAINS` steuert die verbindliche Keycloak-Profilvalidierung. Ein direkter IdP-Aufruf umgeht sie nicht. Der Realm-Import ist nur für neue Installationen bestimmt; bestehende Realms werden gezielt über die Admin-API aktualisiert. Eine zweite Domain- oder Passwortvalidierung im Frontend entfällt.

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
- Geschützte SvelteKit-Seiten lesen die gemeinsame Session-Projektion im Root-Layout. Fehlt oder verfällt die gemeinsame Sitzung, wird der sichere OIDC-Wiederanmeldungsfluss gestartet.
- Der Browser spricht für komplexe Seiten primär mit SvelteKit. FastAPI bleibt OIDC-/Sitzungsverantwortlicher und API-Adapter; ehemalige HTMX-Produktpfade sind nicht mehr aktiv.

## Aktueller Betriebsstand und Ausblick
- Das verbindliche Compose-Profil verwendet persistente gemeinsame Sitzungen und gesonderte CLI-Tokens. Infrastrukturfehler erhalten die Sitzung und liefern `503`; bestätigte ungültige Anmeldung wird abgelehnt.
- Rollen- und Ownership-Guards sind als wiederverwendbare Policies beziehungsweise zentrale Adaptergrenzen etabliert.
- Eine IServ-Anbindung und ein dafür geprüftes Account-Linking sind weiterhin geplant.
