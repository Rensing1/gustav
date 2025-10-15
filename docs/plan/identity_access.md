# Plan: Benutzerverwaltung mit Keycloak (minimalistisch)

Stand: initial

Ziel
- Minimalistische Einführung von Keycloak für Registrierung, Login, Logout, Rollen (`student|teacher|admin`), Passwort ändern (zunächst über Keycloak Account Console), Account löschen.
- Ein Realm (`gustav`), eine Schule. Cookies (HttpOnly, Secure, SameSite) für UX und Sicherheit.
- Contract‑First (OpenAPI), TDD (pytest), KISS.

Bezug: `docs/auth_legacy.md`
- Bisherige Auth: Supabase (GoTrue), HttpOnly Cookies, Sessions in DB, Profile & RLS.
- Migration: E‑Mail, Rolle, und (falls möglich) Passwort‑Hash (bcrypt) übernehmen.

Entscheidungen (bestätigt)
- Keycloak via docker‑compose, ein Realm `gustav`.
- Rollen: `student`, `teacher`, `admin` (Vergabe durch Admin, Default `student`).
- Cookies: httpOnly (immer), Secure/SameSite (prod), in dev entsprechend gelockert.
- Registrierung: E‑Mail‑Verifizierung (prod); in dev optional ausgeschaltet.
- QR‑Registrierung: Kurs‑Token (TTL 15 Minuten), nach Login Kurszuweisung.
- Passwort ändern: vorerst über Keycloak Account Console (Link aus UI). Eigene UI später optional.
- Migration: bevorzugt Import bestehender bcrypt‑Hashes; Fallback „Force password reset“.

Architektur (kurz)
- OIDC Authorization Code Flow (serverseitig). Keycloak als IdP. Unser Web‑Adapter (FastAPI) setzt/liest httpOnly‑Session‑Cookie.
- Keycloak‑Konfig als Code (Realm‑Export/CLI), damit reproduzierbar.

API‑Oberfläche (Entwurf – wird in `api/openapi.yml` konkretisiert)
- `GET /auth/login` → Redirect zu Keycloak (Start Auth‑Flow)
- `GET /auth/callback` → Tauscht Code gegen Token, legt Session an, setzt httpOnly‑Cookie, Redirect zu Startseite
- `POST /auth/logout` → Session invalidieren, Cookie leeren
- `GET /api/me` → 200 mit `{ email, roles }` wenn eingeloggt; sonst 401
- (später) `POST /auth/qr` / `GET /auth/login?state=...` für QR‑Flow (Token‑State)

User Story (vereinfachte Form)
- Als Schüler möchte ich mich mit E‑Mail/Passwort anmelden und automatisch meine Rolle `student` erhalten, damit ich auf meine Kurse zugreifen kann. In der Schule kann ich alternativ per QR beitreten.
- Als Lehrer/Admin möchte ich Rollen verwalten (in Keycloak) und den Passwortwechsel Keycloak überlassen.
- Als Benutzer möchte ich mich sicher abmelden können (Cookie löschen, Session invalidieren).

BDD‑Szenarien (Auszug)
- Login (Happy Path)
  - Given ich bin nicht eingeloggt
  - When ich `GET /auth/login` aufrufe
  - Then werde ich zu Keycloak weitergeleitet
- Callback (Happy Path)
  - Given Keycloak liefert einen gültigen `code`
  - When `GET /auth/callback?code=...` aufgerufen wird
  - Then wird ein httpOnly‑Cookie gesetzt und ich werde zur Startseite geleitet
- Callback (Fehler)
  - Given der Code ist ungültig/abgelaufen
  - Then erhalte ich 400 und kein Cookie
- Logout
  - Given ich bin eingeloggt
  - When ich `POST /auth/logout` aufrufe
  - Then wird das Cookie gelöscht und die Session invalidiert
- /api/me (eingeloggt)
  - Given gültige Session
  - When `GET /api/me`
  - Then 200 und `{ email, roles:[...] }`
- /api/me (nicht eingeloggt)
  - Given keine Session
  - When `GET /api/me`
  - Then 401
- QR (Happy Path)
  - Given ein gültiger Kurs‑Token (15 Min gültig)
  - When ich über den QR‑Link den Login starte
  - Then werde ich nach erfolgreichem Login dem Kurs zugeordnet
- QR (abgelaufen)
  - Given ein abgelaufener Kurs‑Token
  - Then erhalte ich 410 (oder 400) mit verständlicher Info

Schlanker Implementierungsplan (iterativ)
1) API‑Vertrag: o.g. Endpunkte in `api/openapi.yml` ergänzen (Contract‑First)
2) docker‑compose: Keycloak‑Service + Realm/Client/Rollen (Konfig als Code)
3) Tests (pytest): Login/Callback/Logout/me (Keycloak‑Calls gemockt)
4) Minimaler Adapter: Code bis Tests grün (Cookie setzen/löschen, Redirects)
5) Migration (Legacy → Keycloak): Import (bcrypt) bzw. Reset‑Aktion; Rollenzuweisung
6) QR‑Registrierung: Token‑Store (TTL 15 Min), Login mit `state`, Kurszuweisung

Migration (Legacy → Keycloak)
- Daten aus Alt‑System: `email`, `role`, `password_hash` (bcrypt). Mapping: Rolle → Realm‑Rolle, E‑Mail unverändert.
- Bevorzugt: Passwort‑Import (bcrypt) in Keycloak (Kompatibilität prüfen); andernfalls initiales Passwort + „UPDATE_PASSWORD“‑Aktion beim ersten Login.
- Konflikte (gleiche E‑Mail): Duplikate erkennen, Admin‑Entscheidung (mappen/zusammenführen/ignorieren).
- E‑Mail‑Verifizierung: für migrierte Konten je nach Legacy‑Status setzen oder erneuern.

Sicherheit & DSGVO
- Cookies: httpOnly, Secure (prod), SameSite angemessen; CSRF‑Schutz für mutierende Endpunkte.
- Brute‑Force: Keycloak Login‑Beschränkungen aktivieren; Passwort‑Policy (min. 8 Zeichen, 1 Zahl, 1 Buchstabe).
- Account löschen: Benutzer in Keycloak löschen; App‑Daten je Kontext (pseudonymisieren/löschen) – wird pro Bounded Context konkretisiert.
- Logging/Audit: sicherheitsrelevante Events in Keycloak/Anwendungslogs nachvollziehbar, PII‑sparsam.

IServ (Ausblick)
- Perspektivisch OIDC‑Anbindung an IServ (falls verfügbar), sonst SAML. Account‑Linking nach E‑Mail oder `sub`.

Definition of Done (für den ersten Inkrement)
- `api/openapi.yml` enthält die vier Endpunkte (login, callback, logout, me) mit klaren Responses.
- pytest‑Suite deckt Happy Paths und Kernfehlerfälle ab; Tests grün.
- docker‑compose startet Keycloak; Realm/Client/Rollen vorhanden.
- Minimaler Adapter setzt/liest httpOnly‑Cookie; `/api/me` liefert Rollen.
- Kurze README‑Ergänzung zur Auth‑Bedienung (Login/Logout/Passwort ändern via Keycloak‑Konsole).

