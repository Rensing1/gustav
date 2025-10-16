# Plan: Passwort-Reset Redirect (GET /auth/forgot)

Datum: 16.10.2025

## Kontext / Stand
- Ziel: Komfort-Endpunkt `GET /auth/forgot`, der zur Keycloak-Reset-Seite weiterleitet.
- Vertrag: In `api/openapi.yml` bereits modelliert (302 Redirect, optionaler `login_hint`).
- Umsetzung (nach TDD): RED-Tests ergänzt, minimale Implementierung in Web-Adapter, Tests grün.

## User Story
Als Benutzer möchte ich über `GET /auth/forgot` den Passwort-Reset bei Keycloak starten können, damit GUSTAV keine Passwörter verwalten muss. Optional soll meine E‑Mail als `login_hint` vorausgefüllt sein.

## BDD-Szenarien (Given–When–Then)
- Given nicht eingeloggt, When `GET /auth/forgot`, Then 302‑Redirect zur Keycloak Reset‑Seite.
- Given `login_hint=email`, When `GET /auth/forgot?login_hint=...`, Then 302 mit `login_hint` als Query‑Parameter (URL‑encoded).
- Fehlerfälle: nicht relevant (Endpoint ist nur Redirect), keine Cookies, kein State erforderlich.

## API-Vertrag (Contract-First)
- Datei: `api/openapi.yml`
- Pfad: `/auth/forgot` (GET)
- Verhalten: 302 Redirect auf Keycloak Reset‑Seite, optionaler Query‑Parameter `login_hint` (format: email).
- Status: Bereits vorhanden, keine Vertragsänderung nötig.

## Datenbank / Migration
- Keine Änderungen. Der Endpunkt führt nur einen Redirect aus.

## Tests (RED)
- Datei: `backend/tests/test_auth_contract.py`
  - `test_forgot_redirect_uses_oidc_cfg`: Prüft, dass die Redirect‑URL aus `OIDC_CFG.base_url` + Realm konstruiert wird (kein Hardcoding).
  - `test_forgot_redirect_forwards_login_hint`: Prüft, dass `login_hint` korrekt als Query‑Parameter weitergereicht wird.

## Implementierung (GREEN)
- Datei: `backend/web/main.py`
  - Route `GET /auth/forgot` baut die Ziel‑URL dynamisch aus `OIDC_CFG.base_url` und `OIDC_CFG.realm` und hängt optional `login_hint` via `urlencode` an.
  - Slim‑App für Tests (`create_app_auth_only`) spiegelt dieses Verhalten, um Contract‑Tests leichtgewichtig zu halten.

## Review (Refactor‑Ideen, Qualität)
- KISS & Security: Kein Zustand, keine Cookies; einfache, nachvollziehbare URL‑Konstruktion; kein Hardcoding von Host/Realm.
- Clean Architecture: OIDC‑Konfiguration liegt im Adapter, Domäne bleibt unberührt.
- Verbesserung: URL‑Konstruktion für Reset‑Seite könnte in einen kleinen Helper extrahiert werden, um Duplikat in Slim‑App zu vermeiden (derzeit zugunsten von Lesbarkeit akzeptiert).

## Definition of Done
- OpenAPI‑Vertrag deckt `/auth/forgot` ab.
- Pytest‑Fälle prüfen Redirect und `login_hint`.
- Implementierung setzt den Vertrag minimal um; Tests sind grün.
- Diese Plan‑Datei dokumentiert User Story, BDD, Vertrag, Tests und Umsetzung.

