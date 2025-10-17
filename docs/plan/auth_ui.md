# Plan: Authentifizierungs-UI (Login, Registrierung, Passwort vergessen)

_Stand: 2025-10-17_

## Ausgangslage & Zielbild

- **Was existiert (aktualisiert):** Host-basiertes Routing in DEV über Caddy: `app.localhost:8100` (GUSTAV) und `id.localhost:8100` (Keycloak). `/auth/login|register|forgot` leiten in DEV/PROD zur Keycloak‑UI, die per leichtem CSS‑Theme an GUSTAV angepasst ist. Eigene SSR‑Formulare (Direct‑Grant) wurden entfernt.
- **Was fehlt:** UI‑Feinschliff des Keycloak‑Themes (kompakter, deutschsprachige Labels, Logo optional) und klare Trennung der Zuständigkeiten (IdP verarbeitet Passwörter; GUSTAV verwaltet Sessions).
- **Ziel:** Einheitliches Erlebnis mit minimaler Komplexität: In PROD bleibt Keycloak die Login‑Oberfläche (gebrandet), in DEV können wir Formulare lokal testen. Kein Passworthandling in GUSTAV für PROD.
- **Rollout-Strategie:** DEV nutzt Subdomains (`app.localhost`, `id.localhost`) und Caddy; PROD behält IdP‑UI (gebrandet). Keine Direct‑Grant‑Formulare mehr.

## Aktualisierung (heute)

- Security: `/api/me` setzt jetzt `Cache-Control: no-store` (Verhindert Caching von Auth‑Zuständen).
- Wartbarkeit: Auth‑Routen in eigenes Modul ausgelagert (`backend/web/routes/auth.py`), Haupt‑App bindet den Router ein.
- UX: Registrierungsseite zeigt einen Passwort‑Policy‑Hinweis (DE) an; E2E testet Sichtbarkeit.
- Logout vereinheitlicht: `GET /auth/logout` löscht App‑Session und meldet zusätzlich am IdP ab (End‑Session), anschließend zurück zur App.
- Contract‑First: OpenAPI aktualisiert – reine Redirect‑Endpunkte für Login/Registrierung/Forgot; keine POST‑Formulare/CSRF mehr.

Hinweis: Ältere Abschnitte in diesem Plan, die CSRF/SSR‑Formulare und POST‑Routen beschreiben, sind obsolet. Maßgeblich ist der Vertrag in `api/openapi.yml`.

## Neue Phase: Plattformintegration (Login erzwingen, Sidebar, Logout App+IdP)

Ziel dieser Phase ist die tiefere Integration der Authentifizierung in die Plattformoberfläche, ohne die Sicherheitsgrenzen (Passworteingabe beim IdP) zu durchbrechen. Wir erzwingen Login serverseitig, reichern die Sidebar mit Identitätsdaten an und vereinheitlichen den Logout so, dass sowohl die App‑Session als auch die Keycloak‑SSO‑Sitzung beendet werden.

### User Story

> Als nicht angemeldete Person werde ich grundsätzlich zur Anmeldung umgeleitet. Nach Anmeldung gelange ich zur Startseite. Als angemeldete Person sehe ich in der Sidebar meine E‑Mail und meine Rolle und kann mich vollständig abmelden (App + IdP).

### BDD‑Szenarien (Given‑When‑Then)

Login‑Erzwingung (Middleware)
- Given ich bin nicht angemeldet und fordere eine HTML‑Seite an (z. B. `/dashboard`)
  When ich `GET /dashboard` aufrufe
  Then erhalte ich `302` mit `Location: /auth/login` (ohne „next“)

- Given ich bin nicht angemeldet und fordere eine JSON‑API an (z. B. `/api/courses`)
  When ich `GET /api/courses` aufrufe
  Then erhalte ich `401` mit Problem‑JSON und ohne Redirect

- Given ich bin nicht angemeldet und ein HTMX‑Request geht ein
  When ich `GET /courses` mit Header `HX-Request: true` aufrufe
  Then erhalte ich `401` und `HX-Redirect: /auth/login`

Whitelist (keine Erzwingung)
- Given eine Anfrage auf `/auth/*`, `/health`, `/_static/*`
  Then greift die Middleware nicht (keine Redirect‑Schleife)

Sidebar (angemeldet)
- Given ich bin angemeldet
  When eine Seite mit Sidebar gerendert wird
  Then sehe ich meine `email` und meine feste `role` und einen Button „Abmelden“

Vereinheitlichter Logout (App + IdP)
- Given ich bin angemeldet
  When ich `GET /auth/logout` aufrufe
  Then wird das App‑Session‑Cookie sicher gelöscht
  And der Browser wird mit `302` zum Keycloak `end_session_endpoint` umgeleitet
  And nach Rückkehr lande ich auf `/`
  And ein anschließendes `GET /api/me` liefert `401`

Rückkehrziel
- Given ich melde mich neu an
  When der Login‑Callback erfolgreich war
  Then werde ich auf die Startseite `/` geleitet (kein „next“)

### API‑Contract (Draft‑Ergänzung)

Nur die Logout‑Route ändert ihr Verhalten: sie löst nun explizit IdP‑Logout aus (App + IdP). Keine weiteren öffentlichen Endpunkte kommen hinzu.

```yaml
paths:
  /auth/logout:
    get:
      summary: Logout (App-Session löschen und am IdP abmelden)
      description: |
        Löscht das GUSTAV-Session-Cookie und leitet zum OIDC `end_session_endpoint` (Keycloak) weiter.
        Nach der Abmeldung am IdP wird zur App-Startseite (`/`) zurückgeleitet.
      parameters:
        - in: query
          name: redirect
          required: false
          schema:
            type: string
            default: "/"
          description: Ziel innerhalb der App nach erfolgreicher IdP-Abmeldung.
      responses:
        "302":
          description: Redirect zum IdP end_session_endpoint (und anschließend zurück zur App)
          headers:
            Location:
              schema: { type: string }
```

Hinweis: Für geschützte HTML‑Seiten wird 302 zu `/auth/login` erwartet; für JSON/HTMX 401. Das wird im Vertrag der jeweiligen Endpunkte unter `401` dokumentiert (keine zusätzlichen Routen nötig).

### Tests (Rot)

- Middleware (Unit/Integration)
  - HTML‑Anfrage: 302 → `/auth/login`
  - JSON‑Anfrage: 401 ohne Redirect
  - HTMX‑Anfrage: 401 mit `HX-Redirect: /auth/login`
  - Whitelist: keine Erzwingung auf `/auth/*`, `/health`, `/_static/*`

- Sidebar (SSR)
  - Angemeldet: Sidebar rendert `email`, `role`, „Abmelden“
  - Nicht angemeldet: kein Zugriff (durch Middleware abgesichert)

- Logout (App + IdP)
  - Aufruf `GET /auth/logout` setzt Lösch‑Cookie (passende Flags) und liefert `302` zum `end_session_endpoint`
  - E2E: Nach Rückkehr auf `/` ist `/api/me` → `401`

Dateien (Tests)
- `backend/tests/test_auth_middleware.py` (neu)
- `backend/tests/test_navigation_sidebar.py` (neu)
- `backend/tests_e2e/test_identity_login_register_logout_e2e.py` (ergänzen: „IdP‑End‑Session“‑Assertion)

### Implementierung (Grün)

- Middleware hinzufügen (`backend/web/main.py`):
  - Allowlist: `/auth/`, `/health`, `/_static/`
  - Erkennung HTML vs. JSON vs. HTMX (Accept/Headers)
  - HTML → 302 `/auth/login`; JSON/HTMX → 401 (+ `HX-Redirect`)

- Sidebar anreichern (`backend/web/components/navigation.py`):
  - Claims aus Session/ID‑Token extrahieren (mind. `email`, feste `role`)
  - Anzeige im Seitenmenü; Abmelde‑Button verlinkt auf `GET /auth/logout`

- Logout vereinheitlichen (`backend/web/routes/auth.py`):
  - Route `/auth/logout`: Session‑Cookie sicher löschen (HttpOnly, Secure in PROD, `SameSite=strict`) und Redirect zum IdP `end_session_endpoint` mit `post_logout_redirect_uri=/`
  - Optional `id_token_hint`, falls vorhanden; ansonsten Fallback ohne Hint (DEV)

- OpenAPI aktualisieren (`api/openapi.yml`):
  - `/auth/logout` Beschreibung/Response auf „App + IdP“ ausrichten
  - Geschützte Routen mit `401` dokumentieren (keine Redirects für JSON)

### Sicherheit & Datenschutz

- Session‑Cookie sicher löschen (gleiche Attribute wie beim Setzen; `Max-Age=0`, `Expires` in Vergangenheit)
- Keine PII in Redirect‑URLs oder Logs
- `/api/me` weiterhin mit `Cache-Control: no-store`

### Abgrenzung (Out‑of‑Scope für diese Phase)

- „next“-Parameter (zielgerichtete Rückleitung)
- Öffentliche Seiten (Landing, Impressum) – kann per Allowlist später ergänzt werden
- Kurs‑/domänenspezifische Rollenauflösung (nur eine feste IdP‑Rolle wird angezeigt)

### Akzeptanzkriterien

- Nicht angemeldete HTML‑Zugriffe werden zuverlässig auf `/auth/login` umgeleitet; JSON/HTMX erhalten 401
- Sidebar zeigt für angemeldete Nutzer E‑Mail und Rolle, inkl. funktionsfähigem Abmelden‑Button
- `GET /auth/logout` beendet App‑Session und IdP‑SSO, anschließend ist ein erneuter Besuch der App login‑pflichtig
- Tests (Unit, Integration, E2E) laufen grün

### Nacharbeiten / Doku

- `docs/ARCHITECTURE.md`: Abschnitt „Identity & Auth“ um Middleware‑Erzwingung, Sidebar‑Claims und vereinten Logout ergänzen
- README: kurzer Hinweis zum Verhalten von `/auth/logout`

## Leitplanken

- **Phasenweise Umsetzung:** Wir liefern zuerst eine einfache, funktionale Lösung (Phase 1) und härten sie in späteren Phasen.
- **KISS & FOSS:** Verständlicher Code, simple Komponenten, gut kommentiert, damit Lernende die Umsetzung nachvollziehen können.
- **Security First:** Credentials werden sofort an Keycloak weitergereicht, keine Speicherung, keine Protokollierung im Klartext. Fehlerzustände dürfen keine Account-Enumeration zulassen.
- **Clean Architecture:** Web-Adapter bedient sich an Use-Case-Ebene (`identity_access`), keine direkte Framework-Logik in der Domäne.
- **TDD / Red-Green-Refactor:** Tests lenken die Implementierung. Jeder Schritt startet mit fehlschlagenden Tests, erst danach minimaler Code.
- **Contract First:** API-Vertrag (OpenAPI) wird zuerst erweitert und bildet die Grundlage für Tests.
- **Glossary:** Konsistente Begriffe („Lernende“, „Lehrkräfte“, „Service Account“, „Session“).
- **Dokumentation:** Docstrings und Inline-Kommentare in Englisch, Markdown-Dokumentation hier gepflegt.

## Umsetzungsschritt: Prod‑Build‑Härtung (Theme/CSS) – ✅ erledigt

- Ziel: Reproduzierbares Deployment ohne Volumes. Das App‑CSS wird beim Image‑Build in das Keycloak‑Theme kopiert.
- Änderungen:
  - Neues Image für Keycloak: `keycloak/Dockerfile` kopiert
    - `keycloak/themes/gustav` → `/opt/keycloak/themes/gustav`
    - `backend/web/static/css/gustav.css` → `/opt/keycloak/themes/gustav/login/resources/css/app-gustav-base.css`
    - `keycloak/realm-gustav.json` → `/opt/keycloak/data/import/realm-gustav.json`
  - `docker-compose.yml`: Keycloak verwendet `build:` statt Upstream‑Image; Volumes für Theme/CSS/Realm entfallen.
- Start (lokal):
  - `docker compose up -d --build caddy web keycloak`
  - Erststart von Keycloak dauert 10–20 s; danach ist die gebrandete Login‑Seite verfügbar.


## Annahmen & Vorarbeiten

1. **Keycloak-Konfiguration & Betrieb (aktuell)**
   - Realm `gustav`; Authorization‑Code‑Flow mit PKCE.
   - DEV: Hostbasiert via Caddy (`app.localhost` → Web, `id.localhost` → Keycloak). Keine Pfadpräfixe mehr nötig.
   - PROD: Redirect zur Keycloak‑UI (gebrandet). Direct‑Grant bleibt auf DEV/CI beschränkt (Flag), nicht für PROD.
   - **Phase 2 (optional):** Verbesserungen am IdP‑Theme (UX, i18n) – Passwörter bleiben ausschließlich beim IdP.
   - Service-Client (z. B. `gustav-admin`) mit Client-Credentials und Rollen `manage-users`, `view-users`, `manage-accounts` bleibt notwendig für Registrierung/Reset.
   - Keycloak-Brute-Force-Detection und MFA-Policies bleiben aktiv; Tests stellen sicher, dass der MVP-Flow keine gesperrten Accounts o. Ä. ignoriert.
2. **Secrets & Env-Handling**
   - `.env` enthält nur Platzhalter; echte Secrets kommen aus Secret-Store (Docker Secrets, 1Password CLI). 
   - Benötigte Variablen:
     - `KC_SERVICE_CLIENT_ID`
     - `KC_SERVICE_CLIENT_SECRET`
     - `KC_ADMIN_REALM` (default `master`)
     - `KC_LOGIN_ACTION_EXECUTION` (falls nötig, um eine spezifische Execution anzusprechen)
   - Tests ersetzen Secrets durch Fixtures (`monkeypatch`).
3. **UI Framework**
   - Weiterverwendung der Python-Komponenten (Form Fields, Layout).
   - Neue Form-Elemente (TextInput, PasswordInput) werden in `backend/web/components/forms` ergänzt.

## User Story

> Als Lernende:r möchte ich mich direkt in GUSTAV registrieren, anmelden und mein Passwort zurücksetzen können, damit ich ohne Keycloak-UI Zugriff auf meine Kurse habe und mich sicher aufgehoben fühle.

## BDD-Szenarien (Phase 1 konkret)

### Login

- Happy Path
  - Given ein CSRF‑Cookie und Hidden‑Feld im Login‑Formular
  - And ein existierender Nutzer mit gültigem Passwort
  - When das Formular an `/auth/login` gepostet wird (email, password, csrf_token, optional redirect)
  - Then antwortet der Server mit 303 und setzt `gustav_session`
  - And `Location` zeigt auf `redirect` oder `/`

- Ungültige Credentials
  - Given valides CSRF
  - When falsches Passwort gepostet wird
  - Then 400, generische Fehlermeldung, kein Session‑Cookie

- Bereits angemeldet
  - Given gültige Session
  - When GET `/auth/login?redirect=/kurs/1`
  - Then 303 → `/kurs/1`

- Account gesperrt/Policy verletzt
  - Given Keycloak meldet `invalid_grant`/`disabled`
  - When POST `/auth/login`
  - Then 400, generische Fehlermeldung, keine PII im Log

- CSRF verletzt
  - Given fehlendes/ungültiges Token
  - When POST `/auth/login`
  - Then 403, kein Login‑Versuch gegen Keycloak

### Registrierung

- Happy Path
  - Given valides CSRF und neue E‑Mail
  - When POST `/auth/register` (email, password, optional display_name)
  - Then 303 → `/auth/login?login_hint=<email>`; User in Keycloak erstellt; Standardrolle `student` zugewiesen

- E‑Mail bereits vorhanden
  - Given valides CSRF und existente E‑Mail
  - When POST `/auth/register`
  - Then 400, generische Fehlermeldung (keine Enumeration)

- Schwaches Passwort / Policy
  - When Passwort verletzt Richtlinie
  - Then 400, neutrales Feedback; keine Session

- Rollenvergabe fehlgeschlagen
  - Given User erstellt, Role‑Assign scheitert
  - Then 500, Support‑Hinweis, kein Auto‑Rollback

### Passwort vergessen

- Happy Path
  - Given valides CSRF und eine E‑Mail (existierend oder nicht)
  - When POST `/auth/forgot`
  - Then 202 JSON `{message}`; kein Hinweis auf Existenz der Adresse

- CSRF verletzt
  - Given fehlendes/ungültiges CSRF
  - When POST `/auth/forgot`
  - Then 403

### Edge Cases

- Ungültiger redirect (fremde Origin)
  - Given `redirect` zeigt auf fremde Origin
  - When Login erfolgreich
  - Then Ignorieren des Ziels, Redirect auf `/`

## OpenAPI-Änderungen (Draft)

```yaml
paths:
  /auth/login:
    get:
      summary: Render login form
      parameters:
        - in: query
          name: redirect
          schema: { type: string }
      responses:
        "200":
          description: "HTML login form"
          content:
            text/html:
              schema: { type: string }
        "303":
          description: "Already authenticated"
          headers:
            Location: { schema: { type: string } }
    post:
      summary: Submit credentials
      requestBody:
        content:
          application/x-www-form-urlencoded:
            schema:
              type: object
              required: [email, password, csrf_token]
              properties:
                email: { type: string, format: email }
                password: { type: string }
                redirect: { type: string }
                csrf_token: { type: string }
      responses:
        "303":
          description: "Login success"
          headers:
            Location: { schema: { type: string } }
            Set-Cookie: { schema: { type: string } }
        "400": { description: "Invalid credentials or policy violation" }
        "403": { description: "CSRF invalid" }

  /auth/register:
    get: { … }  # analog: HTML Formular
    post:
      summary: Create user account
      requestBody:
        content:
          application/x-www-form-urlencoded:
            schema:
              type: object
              required: [email, password, csrf_token]
              properties:
                email: { type: string, format: email }
                password: { type: string, minLength: 8 }
                display_name: { type: string }
                csrf_token: { type: string }
      responses:
        "303":
          description: "Account created"
          headers:
            Location: { schema: { type: string } }
        "400": { description: "Validation error" }
        "403": { description: "CSRF invalid" }
        "500": { description: "Role assignment failed" }

  /auth/forgot:
    get: { … }  # HTML Formular
    post:
      summary: Trigger reset email
      requestBody:
        content:
          application/x-www-form-urlencoded:
            schema:
              type: object
              required: [email, csrf_token]
              properties:
                email: { type: string, format: email }
                csrf_token: { type: string }
      responses:
        "202":
          description: "Reset mail triggered"
          content:
            application/json:
              schema:
                type: object
                required: [message]
                properties:
                  message: { type: string }
        "403": { description: "CSRF invalid" }
        "429": { description: "Rate limit hit (future extension)" }
```

Kontrakt‑Entscheidungen Phase 1:
- GET liefert HTML (`text/html; charset=utf-8`).
- POST antwortet mit 303 (Redirect) bzw. 202/400/403; Fehlerseiten sind HTML, Reset‑Erfolg ist JSON.
- Session‑Cookie: `gustav_session` (`HttpOnly`, `Secure` in PROD, `SameSite=Lax`).
- CSRF‑Cookie für eigene SSR‑Formulare entfällt (Direct‑Grant entfernt).

Status: Vertrag ist aktualisiert (siehe `api/openapi.yml:1`), SSR‑GET‑Seiten und POST‑Routen sind implementiert und getestet.

## Migrationen (Phase 1)

- Keine Änderungen an Supabase/PostgreSQL notwendig.
- CSRF Double‑Submit benötigt keinen Server‑Store; Phase 2 führt CSRFStore/DB‑Schema ein.

## Akzeptanzkriterien (Phase 1)

- Contract‑Tests decken Statuscodes, Headers (Location, Set‑Cookie) und Content‑Types ab.
- CSRF‑Tests erzwingen 403 bei fehlendem/ungültigem Token für Login/Registrierung/Forgot.
- DEV/CI: Direct‑Grant‑Pfad grün; PROD: Redirect auf Keycloak‑UI unverändert funktional.
- E2E: Login/Logout via neuer UI inkl. CSRF funktioniert in DEV.

## Technische Umsetzung

1. **Domänenelemente / Use Cases (identity_access)**
   - Neues Modul `keycloak_client.py` kapselt Interaktion mit Keycloak:
     - Browser‑Flow bleibt alleinige Implementierung (kein Direct‑Grant mehr).
     - `create_user`/`trigger_password_reset` bleiben Admin-REST-Aufrufe mit klaren Exceptions.
   - Modul bleibt Framework-unabhängig, Fehler werden in klar typisierte Exceptions übersetzt (Clean Architecture).
   - CSRF-Schutz phasenweise:
     - Phase 1: Double-Submit (Hidden Feld + Cookie, kein Server-Store).
     - Phase 2: CSRFStore + One-Time-Token (siehe Terraform/DB-Konzept).

2. **Web-Adapter (FastAPI)**
   - Phase 1 (MVP):
   - GET‑Routen leiten direkt zur IdP‑UI; keine SSR‑Formulare.
   - POST‑Routen entfallen; Session entsteht ausschließlich via Callback nach IdP‑Login.
     - Flash-Messages optional via Query-Parameter.
   - Phase 2: Umstellung auf CSRFStore + One-Time-Token, Flash-System ausbauen, Browser-Flow-Adapter integrieren.

3. **UI-Komponenten**
   - Phase 1: `TextInputField` ergänzt, SSR‑Seiten verwenden Layout + Form‑Komponenten. CSS bleibt bewusst minimal (KISS).
   - Phase 2: Ausbau (FormContainer, differenzierte Success-Messages, bessere Responsivität).
   - CSS (`backend/web/static/css/gustav.css`):
     - Phase 1: Fokus auf Lesbarkeit & Fehlermeldungen.
     - Phase 2: erweiterte responsiv/Accessibility-Anpassungen.

4. **Sessionmanagement**
   - Wiederverwendung des existierenden `SESSION_STORE`.
   - Nach erfolgreicher Passwort-Anmeldung ID-Token verifizieren (bestehende Funktion `verify_id_token`) → Session anlegen → Cookie setzen.

5. **Fehler- & Sicherheitsaspekte**
   - Keine Passwörter/E-Mails in Logs (Masking/Hashing).
   - Einheitliche Fehlermeldungen (z. B. „Anmeldung fehlgeschlagen“).
   - Phase 1: Double-Submit-CSRF, Tests stellen 403 sicher.
   - Phase 2: Ausbau (CSRFStore + One-Time-Token, serverseitiges Throttling).
   - Rate Limiting: vorerst Keycloak-Brute-Force nutzen, Ticket für app-seitiges Throttling vormerken.
   - Kein Feature‑Flag mehr für Direct‑Grant; Flows sind ausschließlich Redirect‑basiert.

## Teststrategie (Red → Green)

1. **Contract-Tests anpassen/erweitern** (`backend/tests/test_auth_contract.py`)
   - GET `/auth/login` liefert HTML mit Formular + CSRF-Hidden-Field.
   - POST `/auth/login` gültig → 303 + Cookie; ungültige Credentials → 400; fehlendes Token → 403.
   - POST `/auth/register` → 303 + Redirect; Duplicate → 400; fehlendes Token → 403; Rollback → 500.
   - POST `/auth/forgot` → 202; fehlendes Token → 403.
2. **Neue Unit-/Integrationstests**
   - `backend/tests/test_keycloak_client.py`: entfällt (Direct‑Grant entfernt).
   - `backend/tests/test_auth_ui.py`: Form-Verarbeitung, CSRF, Flash-Messages, Already-logged-in Redirect.
   - `backend/tests/test_csrf_store.py` (optional) für Token-Generierung/Härtung.
3. **E2E (aktualisiert)** (`backend/tests_e2e/test_identity_login_register_logout_e2e.py`)
   - Flow über `app.localhost` → Redirect zu `id.localhost` → Callback → Session prüfen.
   - Registrierung: via IdP‑UI oder Admin‑API, Rollenprüfung über `/api/me`.
   - Szenario mit Feature‑Flag = false bleibt bestehen (IdP‑Redirect).
4. **Abdeckung Offene Fälle**
   - Login mit Redirect + CSRF.
   - Registrierung Duplicate + Rollenprüfung.
   - Passwort Reset (nur Statuscode, Rate-Limit-Simulation per Mock).
5. **Feature-Flag Coverage (Phase 2)**
   - Tests/E2E prüfen ausschließlich Redirect‑Flows (kein Flag mehr).

## Aufgaben & Reihenfolge

0. Research: Ticket `AUTH-UI-KEYCLOAK-BROWSER-FLOW` (Browser-Flow SPI) evaluieren & Ergebnis dokumentieren
1. Plan finalisieren (dieses Dokument) ✅
2. **Contract First** ✅
   - `api/openapi.yml` aktualisieren (inkl. Beschreibung des Feature-Flags in den Annotations/Doku-Hinweisen).
   - Review mit Felix.
3. **TDD Iteration Login (Phase 1)** ✅
   - Tests schreiben (Contract + Behavior + CSRF) für MVP (Direct Grant aktiv, Redirect-Pfad separat getestet).
   - Implementieren (Use Case + FastAPI, einfache Double-Submit-CSRF, Redirect in Prod).
   - Refactor, Docstrings ergänzen.
4. **TDD Iteration Registrierung (Phase 1)** ✅
   - Tests → Implementierung → Refactor (Rollenvergabe via Admin-API, keine Auto-Rollbacks).
5. **TDD Iteration Passwort vergessen (Phase 1)** ✅
   - Tests → Implementierung → Refactor (CSRF, neutrale Response, Logging).
6. **UI / Styling Feinschliff (Phase 1)** ✅
   - Kompakt‑Layout umgesetzt (Card/Abstände), Fokus‑Ring konsistent.
   - Small‑Screen‑Tweaks ergänzt (`@media (max-width: 420px)`).
   - Screenshot‑Hinweis: Login‑Seite unter `http://id.localhost:8100/realms/gustav/account/` → „Anmelden“.
7. **E2E Test aktualisieren (Phase 1)** ✅
   - Hostbasiertes Routing (app/id.localhost) abbilden; optional DEV‑Formulare testen.
8. **Dokumentation aktualisieren** ✅
   - `docs/ARCHITECTURE.md` (Auth-Flows) ergänzt; README Quickstart DEV‑Flag ergänzt.
9. **Theme vereinheitlichen (Basis‑CSS teilen) ✅**
   - Kanonisches App‑CSS `backend/web/static/css/gustav.css` als `app-gustav-base.css` in Keycloak‑Theme eingebunden (Compose‑Volume). 
   - Vorteil: spätere Änderungen am App‑CSS greifen sofort auch in der Auth‑UI.
10. **Registrierung & Validierung (E2E) ✅**
    - Fehlerfälle: fehlende Felder, ungültige E‑Mail, schwaches Passwort, Passwort≠Bestätigung, Duplicate‑E‑Mail.
    - Umsetzung: `backend/tests_e2e/test_identity_register_validation_e2e.py`
11. **/auth/register Redirect modernisiert ✅**
    - Statt `…/registrations` wird der Auth‑Endpoint mit `kc_action=register` verwendet. `login_hint` wird weitergereicht.
12. **Passwort‑Policy (DEV) ✅**
    - `length(8) and digits(1) and lowerCase(1) and upperCase(1)` (ohne `specialChars(1)`). Policy wird in E2E via Admin‑API gesetzt (deterministisch).
9. **Review & Feedback**
   - Code Review (Selbstkritisch + Felix).
   - Tests laufen lassen (`pytest -q`).
10. **Plan Phase 2**
   - Research-Ergebnisse einarbeiten, Aufgabenliste für Browser-Flow/CSRFStore/Flag-Coverage ergänzen.
11. Commit & PR.

## Theme‑Spezifikation (Phase 1)

- Card
  - Breite: 420–480 px (max-width: 480px), margin: 48px auto
  - Padding: 24 px innen; Border: 1 px `var(--color-border)`; Radius: 8 px
  - Hintergrund: `var(--color-bg-surface)`, Text: `var(--color-text)`
- Typografie
  - Basis: `var(--font-base)`; Titel `.kc-title`: 24 px/1.3, Gewicht 600, Farbe `var(--color-text-heading)`
  - Labels `.kc-label`: 14 px/1.4, Farbe `var(--color-text)`
- Formularlayout
  - `.kc-form` nutzt Grid mit `gap: 12px`; Inputs `.kc-input` Höhe 40 px
  - Fokus: 2 px Outline `var(--color-border-focus)`; Hover leicht (`var(--color-bg-hover)`)
  - Submit `.kc-submit` Höhe 44 px; Primärfarbe `var(--color-primary)`
- Links/Meta
  - `.kc-links` Abstand oben 8 px, Textgröße 14 px; Linkfarbe `var(--color-primary)`
  - Fehlermeldung `.kc-message.kc-error`: Border‑Left 3 px `var(--color-error)`; Hintergrund `var(--color-bg-overlay)`
- Barrierefreiheit
  - Fokus‑Sichtbarkeit immer an; Mindestkontrast WCAG‑AA; Touch‑Ziele ≥ 40 px
- Internationalisierung
  - Default‑Locale: `de`; Keys über `messages_de.properties` überschreiben: `doLogIn`, `doRegister`, `doForgotPassword`, `usernameOrEmail`, `password`

Hinweis: Alle Farben/Typo‑Variablen folgen `backend/web/static/css/gustav.css` und `docs/UI-UX-Leitfaden.md`.

## Risiken & Gegenmaßnahmen

| Risiko | Bewertung | Gegenmaßnahme |
| --- | --- | --- |
| **Credential-Forwarding schwächt Keycloak-Schutzmechanismen** | Hoch | Gelöst durch Entfernung des Direct‑Grant: Passwörter werden ausschließlich beim IdP verarbeitet |
| **Secrets versehentlich eingecheckt** | Hoch | Secrets ausschließlich aus Secret-Store laden, `.env` nur Platzhalter, Pre-commit-Hooks/CI-Prüfung |
| **Credential Logging / PII-Leak** | Hoch | Logging-Middleware härten (Masking), Review von `logger`-Aufrufen |
| **Account Enumeration** | Mittel | Neutrale Fehlermeldungen, Reset immer 202, Monitoring intern |
| **CSRF bei Formularen** | Hoch | CSRF-Token verpflichtend, Tests erzwingen 403, Security-Review |
| **Rate Limiting fehlt** | Mittel | Keycloak-Brute-Force aktiv lassen, Ticket für app-seitiges Throttling (Redis) |
| **UI-Inkonsistenzen / Accessibility** | Niedrig | Zentrale Form-Komponenten, manuelle QA mit Screenreader |
| **Testflakiness E2E** | Mittel | Stabilisierung: Wartehilfen, dedizierte Test-Profile, Mock-Option für CI |

## Offene Fragen (aktualisiert)

1. Mehrsprachigkeit (DE/EN) jetzt oder später? (aktuell: DE)
2. Direktes Einloggen nach Registrierung beibehalten? (Keycloak‑Standard) Oder E‑Mail‑Verifizierung erzwingen (empfohlen für PROD)?
3. AGB-/Datenschutz‑Consent im Registrierungsformular? (DSGVO)
4. Lehrkräfte: zusätzliche Felder (z. B. Schulnummer)? Separate Story.
5. Phase‑2‑Research konkretisieren: Kriterien, Aufwand, Nutzen gegenüber gebrandeter IdP‑UI.

## Nächste Schritte

- Theme‑Feinschliff für IdP‑UI (kompakte Card, DE‑Labels, optional Logo).
- Optional: E‑Mail‑Verifizierung aktivieren; MailHog im Compose ergänzen; Web blockt Zugriffe bis `email_verified=true`.
- E2E auf hostbasiertes Routing (`app.localhost`/`id.localhost`) stabilisieren.
- README/Docs konsolidieren (Proxy‑Setup, /etc/hosts, lokaler Betrieb).

---

_Prepared by: Codex (Felix’ Tutor & Dev)_

## Code‑Review (dev → master) – Ergänzung 2025‑10‑17

Befunde (kritisch)
- State-Erzeugung/Verwendung inkonsistent: Vertrag beschreibt serverseitig erzeugtes `state`, Implementierung akzeptiert client‑übergebenes `state` und verwendet es (CSRF‑Risiko).
- Offener Redirect: `redirect` wird ohne serverseitige Validierung übernommen und später als Ziel genutzt (potenziell extern). Es existiert nur eine Regex im Vertrag, keine Durchsetzung im Code.
- Query‑Injection bei `login_hint`: In `/auth/register` wird `login_hint` per Stringkonkatenation eingefügt, ohne URL‑Encoding.
- Cookie‑Optionen dupliziert: Sicherheitsflags werden in zwei Modulen berechnet (Drift‑Risiko).
- `expires_at` inkonsistent: Schema `Me` sieht `expires_at` vor, Endpoint liefert es nicht.
- Rollenpriorität unklar: „erste bekannte Rolle“ ist abhängig von Token‑Reihenfolge; Anzeige kann variieren.
- Fehlende `Cache-Control: no-store` auf 400‑Antworten im Callback (nur 401 ist abgedeckt).
- OIDC `nonce` wird nicht verwendet (Replay‑Schutz für ID‑Tokens fehlt; mittel‑kritisch im Code‑Flow, aber empfehlenswert).
- Cookie‑Lifetime vs. Server‑Session: Session hat TTL, Cookie bleibt Session‑Cookie ohne `Max‑Age` (UX‑Inkonsistenz).

Contract‑First Änderungen (Entwurf)
- /auth/login: `state` Query‑Parameter entfernen (serverseitig erzeugt; keine Client‑Übergabe). Beschreibung anpassen.
- /auth/login: `redirect` klarer fassen („nur absolute In‑App‑Pfade; kein Schema/Host; Whitelist“).
- /auth/callback: Für Fehlerfälle `400` Response im Vertrag mit `Cache-Control: no-store` dokumentieren.
- /api/me: Entweder `expires_at` aus dem Schema entfernen (Option A) oder es im Endpoint tatsächlich mitliefern (Option B, UTC‑ISO‑8601).
- /auth/logout/success: optionale `operationId` ergänzen (Konsistenz).

BDD‑Szenarien (Given‑When‑Then) – Ergänzung
- Open‑Redirect verhindert
  - Given ich rufe `GET /auth/login?redirect=https://evil.com` auf
    When ich später über `/auth/callback` erfolgreich zurückkomme
    Then werde ich auf `/` umgeleitet (nicht auf eine externe Domain)
- Client‑State wird ignoriert
  - Given ich übergebe `state=attacker` an `GET /auth/login`
    When `/auth/callback` mit diesem `state` aufgerufen wird
    Then erhalte ich `400 invalid_code_or_state`
- Login‑Hint korrekt kodiert
  - Given ich rufe `GET /auth/register?login_hint=a%2Bteacher@example.com` auf
    Then enthält `Location` genau einen Parameter `login_hint=a+teacher@example.com` und keinen injizierten Zusatzparam
- Callback‑Fehler nicht cachebar
  - Given `GET /auth/callback` schlägt fehl
    Then enthält die Antwort `Cache-Control: no-store`
- Rollenanzeige deterministisch
  - Given Token mit `roles=["student","teacher"]`
    Then ist die SSR‑Primärrolle „Lehrer“ (fixe Priorität admin > teacher > student)
- Logout nutzt id_token_hint
  - Given Session enthält `id_token`
    Then `GET /auth/logout` setzt `id_token_hint` im IdP‑Endpunkt

Tests (RED)
- `test_login_rejects_external_redirects` (Contract/Integration)
- `test_login_ignores_client_state` (Contract)
- `test_register_encodes_login_hint` (Contract)
- `test_callback_errors_set_no_store_header` (Contract)
- `test_role_priority_for_ssr_display` (SSR/Middleware)
- `test_logout_uses_id_token_hint_when_available` (Contract)

Minimaler Code‑Fix (GREEN)
- `backend/web/routes/auth.py`
  - `/auth/login`: entferne Verwendung des Query‑Params `state`; nutze immer `rec.state`.
  - Validiere `redirect`: nur In‑App‑Pfad (`^/[A-Za-z0-9_\-/]*$`); bei Verstoß `redirect=None`.
  - `/auth/register`: baue Ziel‑URL mit `urllib.parse` und `urlencode`, nicht via String‑Konkatenation.
- `backend/web/main.py`
  - `/auth/callback`: in allen `400`‑Zweigen `Cache-Control: no-store` ergänzen.
  - SSR‑Rollenanzeige: primäre Rolle per fester Priorität bestimmen (admin > teacher > student).
  - Optional: Cookie‑`Max-Age` an Server‑Session‑TTL angleichen (nur PROD). 
- Utilities
  - Cookie‑Flags: zentrale Helper (bereits vorhanden) nutzen und Duplikat in `routes/auth.py` entfernen.

Refactor & Doku
- `api/openapi.yml` gemäß „Contract‑First Änderungen“ aktualisieren.
- Kurzkommentare an sicherheitskritischen Stellen (Warum Redirect‑Validierung? Warum `no-store`?).
- README/DOCS: Entscheidung „State stets serverseitig“ und „nur In‑App‑Redirects“ dokumentieren.
- Optional: `nonce` in `OIDCClient.build_authorization_url` ergänzen und im Callback prüfen (Folgeticket, da Test/Implementierung umfangreicher).

Akzeptanzkriterien (DoD)
- Alle neuen RED‑Tests grün, bestehende Suite weiterhin grün.
- Kein externer Redirect mehr möglich; `state` kann nicht vom Client injiziert werden.
- `login_hint` ist korrekt url‑kodiert; keine Param‑Injection.
- `Cache-Control: no-store` auf allen Auth‑Fehlern vorhanden.
- Primärrolle für Anzeige deterministisch.
- Vertrag und Implementierung sind konsistent; Doku aktualisiert.

Migrationen / Datenbank
- Keine Schemaänderungen erforderlich (reine Auth‑Adapter‑/Contract‑Härte).

Priorisierte Nächste Schritte (1–2 PRs)
1) Contract‑First & Tests (RED) – ✅ erledigt
   - OpenAPI angepasst (Client‑`state` entfernt; `redirect` klar definiert).
   - Tests ergänzt: Redirect‑Validierung, State‑Ignorierung, Hint‑Encoding, No‑Store, Rollen‑Priorität, Logout‑Hint.
2) Minimal Fix (GREEN) & Refactor – ✅ erledigt
   - Implementierung wie oben; Fehler‑Header ergänzt; Login‑Hint encoding.
   - Dokumentation aktualisiert (ARCHITECTURE, README).

Ergebnisse (Umsetzung 2025‑10‑17)
- Vertrag: `api/openapi.yml` aktualisiert (Login ohne Client‑State; Callback‑Fehler mit `Cache-Control: no-store`; Logout‑`redirect` beschrieben).
- Tests: `backend/tests/test_auth_hardening.py` hinzugefügt (State‑Ignorierung, Open‑Redirect verhindert, No‑Store, Rollen‑Priorität, Logout‑Hint). Gesamtsuite: 88 Tests grün.
- Codehärtung:
  - `backend/web/routes/auth.py`: State nur serverseitig; `redirect` strikt validiert (In‑App‑Pfad‑Regex); `login_hint` sicher mit `urlencode` gesetzt; Logout nutzt `id_token_hint`, falls vorhanden.
  - `backend/web/main.py`: `Cache-Control: no-store` für alle 400er im Callback; deterministische Primärrolle (admin > teacher > student) für SSR; Middleware setzt identitätsbezogene Sidebar‑Infos.
- Doku: `docs/ARCHITECTURE.md` und `README.md` um Middleware‑Erzwingung, Sicherheitsregeln und unified Logout ergänzt.

Akzeptanzkriterien (DoD) – Status: erfüllt
- Kein externer Redirect mehr möglich; Client‑`state` wird ignoriert.
- `login_hint` korrekt URL‑kodiert; Fehler‑Antworten nicht cachebar.
- Primärrolle UI‑deterministisch; Logout setzt `id_token_hint` wenn möglich.
- Vertrag, Implementierung und Tests konsistent; 88/88 Tests grün.

## Phase 2: Nonce, Session‑TTL, expires_at (Research → TDD)

### User Story
> Als Admin möchte ich zusätzlichen Replay‑Schutz (OIDC nonce), eine konsistente Session‑Lebensdauer (Cookie Max‑Age = Server‑TTL) und klare Verträge für Clients (expires_at in /api/me), damit Sicherheit und UX deterministisch sind.

### BDD‑Szenarien (Given‑When‑Then)

Nonce (Replay‑Schutz)
- Given /auth/login startet den OIDC‑Flow
  When die Authorization‑URL generiert wird
  Then enthält sie einen `nonce`‑Parameter

- Given /auth/callback wird mit gültigem Code aufgerufen
  When das ID‑Token keinen passenden `nonce` zur Login‑Anfrage enthält
  Then antwortet der Server mit `400` und `Cache-Control: no-store`

Cookie‑Lebensdauer (Prod)
- Given Session‑TTL ist 3600s (Standard)
  When /auth/callback erfolgreich ist (in PROD)
  Then enthält `Set-Cookie` `Max-Age=3600` und `SameSite=strict; HttpOnly; Secure`

/api/me liefert expires_at
- Given eine gültige Session
  When GET /api/me
  Then enthält die Antwort `expires_at` als UTC‑ISO‑8601 und `Cache-Control: no-store`

### API‑Contract (Draft‑Ergänzung)

- /auth/login
  - description: Hinweis, dass `nonce` serverseitig erzeugt und geprüft wird (kein Client‑Param)
- /auth/callback
  - description: Nonce‑Prüfung erwähnt; 400 bei Mismatch (bereits no‑store dokumentiert)
- /api/me
  - Schema `Me` behält `expires_at`; Endpoint liefert es verbindlich (Option B)

### Tests (RED)
- test_login_includes_nonce_param
- test_callback_rejects_when_id_token_nonce_mismatch
- test_callback_sets_cookie_max_age_matches_session_ttl_prod
- test_me_includes_expires_at_and_no_store

### Minimal‑Implementierung (GREEN)
- identity_access.oidc: `build_authorization_url(..., nonce)`
- identity_access.stores.StateStore: Nonce in StateRecord speichern
- /auth/callback: Nonce aus Claims gegen gespeicherten State prüfen (400 bei Mismatch, no‑store)
- Cookie: `_set_session_cookie` optional mit `max_age=ttl` (nur PROD)
- /api/me: `expires_at` aus Session serialisieren (UTC‑ISO‑8601)

### Dokumentation
- docs/ARCHITECTURE.md: Abschnitt „Nonce & Session‑TTL“ ergänzen
- README: Kurznotiz zu Nonce/TTL verhalten
