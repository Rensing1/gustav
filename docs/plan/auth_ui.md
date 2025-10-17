# Plan: Authentifizierungs-UI (Login, Registrierung, Passwort vergessen)

_Stand: 2025-10-17_

## Ausgangslage & Zielbild

- **Was existiert (aktualisiert):** Host-basiertes Routing in DEV über Caddy: `app.localhost:8100` (GUSTAV) und `id.localhost:8100` (Keycloak). `/auth/login|register|forgot` leiten in PROD/DEV standardmäßig zur Keycloak‑UI, die per leichtem CSS‑Theme an GUSTAV angepasst ist. Optional (nur DEV/CI) können eigene SSR‑Formulare per Feature‑Flag verwendet werden (`AUTH_USE_DIRECT_GRANT=true`).
- **Was fehlt:** UI‑Feinschliff des Keycloak‑Themes (kompakter, deutschsprachige Labels, Logo optional) und klare Trennung der Zuständigkeiten (IdP verarbeitet Passwörter; GUSTAV verwaltet Sessions).
- **Ziel:** Einheitliches Erlebnis mit minimaler Komplexität: In PROD bleibt Keycloak die Login‑Oberfläche (gebrandet), in DEV können wir Formulare lokal testen. Kein Passworthandling in GUSTAV für PROD.
- **Rollout-Strategie:** DEV nutzt Subdomains (`app.localhost`, `id.localhost`) und Caddy; PROD behält IdP‑UI (gebrandet). Research für „Browser‑Flow‑Adapter ohne Direct Grant“ bleibt Phase 2, aber ist für PROD nicht zwingend.

## Leitplanken

- **Phasenweise Umsetzung:** Wir liefern zuerst eine einfache, funktionale Lösung (Phase 1) und härten sie in späteren Phasen.
- **KISS & FOSS:** Verständlicher Code, simple Komponenten, gut kommentiert, damit Lernende die Umsetzung nachvollziehen können.
- **Security First:** Credentials werden sofort an Keycloak weitergereicht, keine Speicherung, keine Protokollierung im Klartext. Fehlerzustände dürfen keine Account-Enumeration zulassen.
- **Clean Architecture:** Web-Adapter bedient sich an Use-Case-Ebene (`identity_access`), keine direkte Framework-Logik in der Domäne.
- **TDD / Red-Green-Refactor:** Tests lenken die Implementierung. Jeder Schritt startet mit fehlschlagenden Tests, erst danach minimaler Code.
- **Contract First:** API-Vertrag (OpenAPI) wird zuerst erweitert und bildet die Grundlage für Tests.
- **Glossary:** Konsistente Begriffe („Lernende“, „Lehrkräfte“, „Service Account“, „Session“).
- **Dokumentation:** Docstrings und Inline-Kommentare in Englisch, Markdown-Dokumentation hier gepflegt.

## Annahmen & Vorarbeiten

1. **Keycloak-Konfiguration & Betrieb (aktuell)**
   - Realm `gustav`; Authorization‑Code‑Flow mit PKCE.
   - DEV: Hostbasiert via Caddy (`app.localhost` → Web, `id.localhost` → Keycloak). Keine Pfadpräfixe mehr nötig.
   - PROD: Redirect zur Keycloak‑UI (gebrandet). Direct‑Grant bleibt auf DEV/CI beschränkt (Flag), nicht für PROD.
   - **Phase 2 (optional):** Research‑Ticket `AUTH-UI-KEYCLOAK-BROWSER-FLOW` bleibt offen, um perspektivisch IdP‑UI noch enger zu integrieren – ohne Passworthandling in GUSTAV.
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
- CSRF‑Cookie: `gustav_csrf` (nur für Double‑Submit, kein Server‑Store).

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
     - Phase 1: `authenticate_direct_grant` (nur DEV/CI/Tests) + Weiterleitung auf Keycloak-UI in Prod.
     - Phase 2: `authenticate_via_browser_flow` ersetzt Direct Grant, sobald Research abgeschlossen.
     - `create_user`/`trigger_password_reset` bleiben Admin-REST-Aufrufe mit klaren Exceptions.
   - Modul bleibt Framework-unabhängig, Fehler werden in klar typisierte Exceptions übersetzt (Clean Architecture).
   - CSRF-Schutz phasenweise:
     - Phase 1: Double-Submit (Hidden Feld + Cookie, kein Server-Store).
     - Phase 2: CSRFStore + One-Time-Token (siehe Terraform/DB-Konzept).

2. **Web-Adapter (FastAPI)**
   - Phase 1 (MVP):
     - GET-Routen rendern SSR-Formulare (`forms.InputField`, `forms.PasswordField`, `SubmitButton`), erzeugen Double-Submit-CSRF (zufälliger Token im Hidden Field + Cookie z. B. `gustav_csrf`).
     - POST-Routen validieren Formularfelder & CSRF, rufen `keycloak_client` (in Prod → Redirect, in DEV → Direct Grant), setzen Session-Cookie.
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
   - Feature-Flag `AUTH_USE_DIRECT_GRANT` (default False) kapselt den Direct-Grant-Adapter; PROD bleibt auf Redirect, DEV/CI aktiviert den UI-Flow explizit.

## Teststrategie (Red → Green)

1. **Contract-Tests anpassen/erweitern** (`backend/tests/test_auth_contract.py`)
   - GET `/auth/login` liefert HTML mit Formular + CSRF-Hidden-Field.
   - POST `/auth/login` gültig → 303 + Cookie; ungültige Credentials → 400; fehlendes Token → 403.
   - POST `/auth/register` → 303 + Redirect; Duplicate → 400; fehlendes Token → 403; Rollback → 500.
   - POST `/auth/forgot` → 202; fehlendes Token → 403.
2. **Neue Unit-/Integrationstests**
   - `backend/tests/test_keycloak_client.py`: Mock Keycloak (`responses`/`requests_mock`), testen Browser-Flow und optional Direct Grant Fallback.
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
   - Sobald Browser-Flow implementiert ist, ergänzen wir Tests/E2E, die `AUTH_USE_DIRECT_GRANT` toggeln. In Phase 1 reicht ein Testpfad (Direct Grant in DEV, Redirect in Prod).

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
| **Credential-Forwarding schwächt Keycloak-Schutzmechanismen** | Hoch | Phase 1: Prod bleibt auf Keycloak-UI, nur DEV/CI nutzen Direct Grant (Flag). Phase 2: Browser-Flow implementieren, Flag entfernen |
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
