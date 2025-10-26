# Plan: Keycloak an Postgres anbinden (Compose) – statt Volume-Persistenz

Status: Draft (nur Planung, keine Umsetzung)

## Zielbild
- Keycloak speichert Realm, Benutzer und Konfiguration in einer Postgres‑Datenbank (persistente DB), nicht mehr (nur) unter `/opt/keycloak/data` im Container.
- DEV: Compose nutzt dedizierte Postgres‑Instanz/Schema für Keycloak.
- PROD: Gleiche Konfiguration (KC_DB=postgres), DB‑Credentials aus Secret‑Store; Backups/Retention separat geregelt.

## Motivation
- Volume‑Persistenz ist für DEV bequem, skaliert aber nicht und ist für PROD ungeeignet.
- Postgres‑Persistenz erlaubt: saubere Backups, Upgrades, Replikation, klare Trennung von App‑Daten und IdP‑Daten.

## Scope (Iteration A)
- Docker‑Compose: Keycloak mit `KC_DB=postgres` und passenden `KC_DB_*`‑Variablen konfigurieren.
- Option „Reuse vs. Separate DB“: DEV kann eine eigene DB im bestehenden Supabase‑Postgres nutzen (separates Schema/DB‑Name), PROD nutzt eine separate Instanz/DB.
- Realm‑Import‑Semantik: Erststart importiert `realm-gustav.json` in die leere DB; bei Folgestarts kein Re‑Import.

Nicht‑Ziele:
- Keine Änderung an App‑APIs/OpenAPI.
- Kein Wechsel der Session‑Speicherung (App‑Sessions bleiben optional in Supabase‑DB).

## Architekturentscheidungen
- Keycloak Quarkus‑Konfiguration (ab v24):
  - `KC_DB=postgres`
  - `KC_DB_URL=jdbc:postgresql://<host>:<port>/<database>`
  - `KC_DB_USERNAME`, `KC_DB_PASSWORD`
- Netzwerk/Compose:
  - DEV: Service `keycloak-db` (Postgres) oder Nutzung vorhandener Supabase‑DB mit dediziertem User/Schema.
  - Health‑Checks, Restart‑Policy, klare Abhängigkeiten (depends_on / healthcheck) setzen.

## BDD‑Szenarien (Operations)
1) Persistenz über Neustart
   - Given leere Keycloak‑DB
   - When compose up (Erststart)
   - Then Realm „gustav“ ist importiert und Anmelden ist möglich
   - When Benutzer „teacherX“ wird erstellt
   - And Keycloak‑Container wird neu gestartet
   - Then Benutzer „teacherX“ existiert weiter
2) Re‑Import verhindert
   - Given Keycloak‑DB mit vorhandenem Realm
   - When compose up (Folgestart)
   - Then kein erneuter Import überschreibt Daten
3) Fehlerfall DB offline
   - Given DB nicht erreichbar
   - When compose up
   - Then Keycloak startet nicht, Logs zeigen „DB unavailable“, Exit ≠ 0
4) E2E Login bleibt intakt
   - Given laufende Dienste (web, keycloak, db)
   - When E2E Login/Logout Tests laufen
   - Then alle Login‑Flows grün, Cookies/Hosts konsistent

## Compose‑Änderungen (Entwurf)
- Keycloak Service:
  - Entferne/ignoriere `keycloak_data` Volume (nur DEV noch optional nutzbar).
  - Füge Umgebungsvariablen hinzu:
    - `KC_DB=postgres`
    - `KC_DB_URL=jdbc:postgresql://keycloak-db:5432/keycloak`
    - `KC_DB_USERNAME=keycloak`
    - `KC_DB_PASSWORD=keycloak`
- Neuer Service `keycloak-db` (nur DEV):
  - Image: `postgres:16`
  - Volumes: `keycloak_pg_data:/var/lib/postgresql/data`
  - Env: `POSTGRES_DB=keycloak`, `POSTGRES_USER=keycloak`, `POSTGRES_PASSWORD=keycloak`
  - Healthcheck: `pg_isready -U keycloak`

Hinweis: Alternativ DEV an Supabase‑Postgres anbinden (separater User/Schema). In PROD strikt separate Instanz/DB verwenden.

## Migration / Rollout
- DEV: 
  1) Export optionaler Nutzer (wenn erforderlich) oder Realm per Admin‑Konsole.
  2) `docker compose down` (Keycloak), `docker volume rm <project>_keycloak_data` (falls vorhanden).
  3) Compose mit `keycloak-db` hochfahren; erster Start importiert Realm.
  4) Sanity‑Checks (Admin‑Login, Demo‑Accounts, Theme).
- PROD:
  1) Neue DB bereitstellen (Managed Postgres), User/Pass/Firewall/SSL anlegen.
  2) KC_ENV‑Variablen als Secrets setzen.
  3) Rolling Deploy mit Readiness/Health‑Checks.
  4) Backups/Monitoring aktivieren (z. B. pgBackRest, Cloud‑Backups).

## Tests
- E2E: `RUN_E2E=1`
  - `test_identity_login_register_logout_flow` muss weiterhin grün sein.
  - Neuer E2E‑Test (optional): „Benutzer bleibt über Keycloak‑Neustart bestehen“.
- Smoke: Health‑Endpoint Keycloak + OpenID‑Konfiguration erreichbar.

## Sicherheit & Compliance
- Secrets nicht in Repo: Passwörter/DSN via `.env` (DEV) oder Secret‑Store (PROD).
- DB‑Backups, minimaler Zugriff (Least Privilege), IP‑Restriktionen/SSL.
- Keine personenbezogenen Daten in Logs.

## Akzeptanzkriterien
- Keycloak‑Accounts bleiben über Container‑Rebuilds erhalten (DEV "+ PROD“ mit echter DB).
- Login‑Flow unverändert funktionsfähig (E2E grün).
- Doku/README erklärt DEV/PROD‑Konfiguration klar.

## ToDos (Umsetzungsvorschlag)
1. Compose erweitern: `keycloak-db`, `KC_DB_*` setzen; Volumes anpassen.
2. README/ARCHITECTURE aktualisieren (DEV/PROD‑Pfad, Secrets).
3. E2E‑Test „Persistenz über Neustart“ hinzufügen (optional, markiert als e2e).
4. Rollout DEV verifizieren; dann PROD‑Varianten dokumentieren.

