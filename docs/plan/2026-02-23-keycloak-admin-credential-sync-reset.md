# Plan: Local Keycloak Admin Credential Sync + Guarded Reset

Status: umgesetzt

## Hintergrund
- `make verify` scheiterte in `test-e2e`, weil lokale Keycloak-Admin-Credentials drifteten:
  - `KC_ADMIN_CLIENT_SECRET` in `.env` passte nicht mehr zum Realm-Client.
  - `KEYCLOAK_ADMIN_PASSWORD` funktionierte nicht mehr zuverlässig für `admin-cli` Password Grant.
- Ursache sind lokale Snapshot-/Import-Läufe, die DB-Zustand und `.env` auseinanderziehen können.

## Ziel
- Einen deterministischen lokalen Workflow bereitstellen, der vor E2E-Läufen
  beide Credential-Pfade wieder synchronisiert:
  1. Confidential client (`KC_ADMIN_CLIENT_*`)
  2. Master admin user (`KEYCLOAK_ADMIN*`, Password Grant via `admin-cli`)

## Umsetzung
1. Neues Tool `backend.tools.keycloak_admin_sync`:
   - Synct `KC_ADMIN_CLIENT_SECRET` in Keycloak DB (inkl. Fallback `master` realm).
   - Nutzt danach `client_credentials`, um Master-Admin-User zu erstellen/aktualisieren.
   - Setzt Passwort + weist Realm-Rolle `admin` zu.
   - Verifiziert abschließend den Password-Grant (`admin-cli`) als Kompatibilitätscheck.
   - Guardrails:
     - blockiert non-local Keycloak-Basen ohne `--allow-remote-kc`
     - `--reset-admin-user` nur mit explizitem `--yes`

2. Neue Make-Targets:
   - `make keycloak-admin-sync`
   - `make keycloak-admin-reset`
   - `make test-e2e` ruft automatisch `make keycloak-admin-sync` vor pytest auf.

3. Tests:
   - `backend/tests/migration/test_keycloak_admin_sync.py`
   - Fokus auf SQL-Building, Localhost-Guardrail, Reset-Ack-Guardrail, Reset-Flow.

4. Doku:
   - `docs/references/make_targets.md`
   - `docs/tests/e2e_howto.md`

## Risiken / Grenzen
- Tool ist bewusst lokal-first; remote Nutzung nur mit explizitem Override.
- Reset-Modus ist destruktiv für den gewählten Master-Admin-User (delete/recreate).
- Password-Grant bleibt nur für Test-Kompatibilität; App-Runtime nutzt weiterhin primär `client_credentials`.
