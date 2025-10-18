# Plan: Registrierung – Convenience Redirect (GET /auth/register)

Datum: 16.10.2025

## Kontext / Ziel
- Ziel: Benutzer sollen sich registrieren können, ohne dass GUSTAV Passwörter verarbeitet.
- Ansatz: Ein schlanker Convenience-Endpunkt `GET /auth/register`, der zur Keycloak-Registrierungsseite weiterleitet.
- Prinzipien: Contract-First, TDD, KISS, Security-first (Credentials bleiben bei Keycloak).

## User Story
Als neuer Benutzer möchte ich über GUSTAV die Registrierung starten können, damit ich im Anschluss direkt den Login-Flow abschließen kann – ohne dass GUSTAV meine Zugangsdaten verarbeitet.

## BDD-Szenarien
- Given nicht eingeloggt, When `GET /auth/register`, Then 302 Redirect auf die Keycloak-Registrierungsseite.
- Given `login_hint=email`, When `GET /auth/register?login_hint=...`, Then 302 mit `login_hint` als Query (URL-encoded).
- Fehlerfälle: keine Zustandsänderungen, kein Cookie; Endpoint ist public.

## API-Vertrag (Entwurf)
- Pfad: `GET /auth/register`
- Response: `302` (Location → Keycloak Registrierungs-URL)
- Query: `login_hint` (optional, format: email)

## Datenbank / Migration
- Keine Änderungen notwendig.

## Tests (RED)
- `backend/tests/test_auth_contract.py`
  - `test_register_redirect`
  - `test_register_redirect_uses_oidc_cfg`
  - `test_register_redirect_forwards_login_hint`

## Implementierung (GREEN)
- `backend/web/main.py`: Route `GET /auth/register` konstruiert die Ziel-URL aus `OIDC_CFG.base_url` und `OIDC_CFG.realm` und hängt optional `login_hint` an.
- Slim-App (`create_app_auth_only`) spiegelt das Verhalten.

## Review
- KISS: Kein State, keine Cookies.
- Security: Keine Credentials in GUSTAV, nur Redirect.
- Clean Architecture: Web-Adapter nutzt OIDC-Konfig; Domäne bleibt unberührt.

## DoD
- Vertrag enthält `/auth/register`.
- Tests prüfen Redirect + login_hint; grün.
- Implementierung minimal; dokumentiert.

