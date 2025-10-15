# Plan: Keycloak Roles & Session Hardening

Stand: Rollen-Mapping, Cookie-Härtung (prod/dev), JWKS-Fehlerpfad, State/Session-Expiry umgesetzt; Tests grün (15.10.2025).

## Kontext
- Ausgangspunkt: Commit `feat: verify id tokens via JWKS`.
- Keycloak-Login-Flow funktioniert mit In-Memory-State/Session-Stores und getesteter ID-Token-Verifikation.
- Offen: Rollen-Mapping (`student|teacher|admin`), robuste Fehlerpfade im OIDC-Client, Ablauf von State/Session und Härtung der Cookies (Secure/SameSite).
- Ziel dieses Plans: Anforderungen präzisieren, TDD-Vorgehen definieren und saubere Implementierung vorbereiten, bevor wir die reale Keycloak-Integration (docker-compose) final prüfen.

## User Story
Als verantwortliche Lehrkraft (Felix) möchte ich, dass sich Benutzer über Keycloak anmelden können und GUSTAV dabei zuverlässig ihre Rolle (`student`, `teacher` oder `admin`) erkennt, Sessions sicher verwaltet und Fehler im Login-Prozess sauber behandelt, damit wir eine vertrauenswürdige Authentifizierung im Schulkontext gewährleisten können.

## BDD-Szenarien

### Rollen-Mapping
- **Given** ein erfolgreiches Keycloak-Login mit Realm-Rollen `["student"]`  
  **When** der Callback verarbeitet wird  
  **Then** enthält die GUSTAV-Session die Rolle `["student"]`.

- **Given** ein Callback mit Realm-Rollen `["student", "teacher"]`  
  **When** die Session erstellt wird  
  **Then** werden nur die drei bekannten Rollen (`student`, `teacher`, `admin`) übernommen.

- **Given** ein Callback ohne `realm_access.roles`  
  **When** die Session erstellt wird  
  **Then** erhält der Benutzer standardmäßig die Rolle `["student"]`.

- **Given** Keycloak liefert zusätzliche benutzerdefinierte Rollen  
  **When** GUSTAV die Session erstellt  
  **Then** werden unbekannte Rollen ignoriert, mit Debug-Log dokumentiert und das Ergebnis fällt nicht leer (Fallback `["student"]`).

### OIDC-Fehlerpfade
- **Given** Keycloak antwortet beim Token-Austausch mit 400  
  **When** der Callback-Endpunkt aufgerufen wird  
  **Then** liefert GUSTAV `400 {"error": "token_exchange_failed"}` und setzt kein Cookie.

- **Given** die JWKS können nicht geladen werden (Netzwerkfehler)  
  **When** der Callback verarbeitet wird  
  **Then** liefert GUSTAV `400 {"error": "invalid_id_token"}` und protokolliert den Fehler.

- **Given** das ID-Token enthält eine unbekannte `kid`  
  **When** die Verifikation erfolgt  
  **Then** wird der Login abgelehnt und der Statuscode ist 400.

### State- und Session-Expiry
- **Given** ein gespeicherter State ist abgelaufen  
  **When** der Callback mit diesem State aufgerufen wird  
  **Then** liefert GUSTAV `400 {"error": "invalid_code_or_state"}`.

- **Given** eine Session ist abgelaufen  
  **When** `/api/me` aufgerufen wird  
  **Then** antwortet GUSTAV mit `401 {"error": "unauthenticated"}`.

### Cookie-Härtung
- **Given** der Login endet erfolgreich im Produktionsmodus  
  **When** das Session-Cookie gesetzt wird  
  **Then** enthält es die Flags `HttpOnly`, `Secure` und `SameSite=strict`.

- **Given** der Logout-Endpunkt wird aufgerufen  
  **When** das Cookie gelöscht wird  
  **Then** ist sichergestellt, dass Browser das Cookie sofort verwerfen (gleiches `Secure`/`SameSite`-Profil).

## API-Vertrag (Entwurf)
- Keine neuen Endpunkte erforderlich; bestehender Vertrag deckt Rollen- und Session-Information ab.
- Anpassung vorgenommen: `Set-Cookie`-Header bei `/auth/callback` beschreibt die Flags (`HttpOnly; Secure; SameSite=strict` in Prod, `HttpOnly; SameSite=lax` in Dev/Test).

## Datenbank / Migration
- Keine neuen Tabellen oder Spalten notwendig: Sessions in dev weiterhin In-Memory.
- Eventuelle spätere Persistenz (Redis/Postgres) wird separat geplant.

## Technische Notizen
- Rollen-Mapping in `auth_callback`: explizit auf erlaubte Rollen filtern, Unbekanntes ignorieren (Debug-Log).
- Session-Expiry über `monkeypatch` auf `identity_access.stores._now` testen, damit Produktionscode Zeitquelle behält.
- Cookie-Härtung steuern wir über Umgebungsvariable `GUSTAV_ENV` (`dev` vs. `prod`): In Prod setzen wir `HttpOnly`, `Secure`, `SameSite="strict"`, in Dev `HttpOnly`, `SameSite="lax"` ohne `Secure`.
- Fehlerpfade im OIDC-Client und in `verify_id_token`: Logging über modulweiten `logger.warning` (keine personenbezogenen Daten).
- Eigene Exception-Klasse für Token-Exchange-Fehler prüfen, damit der Webadapter differenziert reagieren kann.
- Für realen Keycloak-Test: docker-compose-Service nutzen, siehe Validierungsplan unten.

## Manueller Validierungsplan (Keycloak docker-compose)
1. `docker-compose up keycloak` im Projektstamm starten; warten, bis Realm `gustav` bereit ist.
2. Testbenutzer in Keycloak anlegen (z. B. `student@example.com`, Rolle `student`).
3. Backend starten: `uvicorn backend.web.main:app --reload`.
4. Browser: `http://localhost:8100/auth/login` aufrufen, durch den kompletten Flow einloggen.
5. Browser-Devtools prüfen:
   - Cookie `gustav_session` besitzt Flags wie laut `GUSTAV_ENV` definiert.
   - `/api/me` liefert E-Mail und erwartete Rollen.
6. Logout testen (`POST /auth/logout` oder UI) → Cookie weg, `/api/me` → 401.
7. Fehlerfall provozieren: Keycloak stoppen → Callback erneut aufrufen → HTTP 400 mit Logging.

## TDD-Vorgehen
1. Tests für Rollen-Mapping, Fehlerpfade, Session/State-Expiry und Cookie-Flags schreiben (`backend/tests/test_auth_contract.py` erweitern, ggf. neue Module).
2. Nur minimalen Code ergänzen, um Tests zu erfüllen (KISS, Security first).
3. Nach Grün-Phase Code-Review (Selbstprüfung) + Verbesserungen und Dokumentation (Docstring, Inline-Kommentare).

## Nächste Schritte (high-level)
1. Vertrag prüfen (keine Änderungen erwartet) und ggf. Hinweis zu Cookie-Flags ergänzen.
2. Tests schreiben (RED).
3. Minimalen Code implementieren (GREEN).
4. Review/Refactor, Dokumentation ergänzen.
5. docker-compose-Testlauf mit Keycloak (manueller Verifizierungsplan).

## Lokale Entwicklungsumgebung
- 15.10.2025 21:03:41: Virtuelle Umgebung `.venv/` im Projektstamm vorhanden. Bitte vor pytest-Läufen mit `. .venv/bin/activate` aktivieren.
