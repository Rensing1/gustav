# Plan: Keycloak an Postgres anbinden (Compose) – statt Volume-Persistenz

Status: Final (abgenommen, ready for implementation)

## Executive Summary
- Keycloak speichert Realm-, Benutzer- und Konfigurationsdaten künftig ausschließlich in einer PostgreSQL-Datenbank; das Docker-Volume `keycloak_data` entfällt.
- Dev- und Prod-Umgebungen laufen mit derselben Keycloak-Quarkus-Konfiguration (`KC_DB=postgres`); Tests nutzen denselben Service, es braucht keine separaten Test-Datenbanken.
- Betriebsschwerpunkte: Backups, Wiederherstellung, Monitoring und Secret-Management werden über Postgres-Werkzeuge abgedeckt; Realm-Import bleibt nur für Erststarts aktiv.
- Risiken (z. B. Datenverlust, Ressourcenengpässe in geteilten Clustern) sind identifiziert und mit konkreten Mitigationsmaßnahmen hinterlegt.

## Zielbild
- Einheitliche Compose-/Deployment-Konfiguration für alle Umgebungen:
  - `KC_DB=postgres`
  - `KC_DB_URL=jdbc:postgresql://keycloak-db:5432/keycloak` (Dev) bzw. verwaltete Instanz (Prod)
  - `KC_DB_USERNAME`, `KC_DB_PASSWORD` aus `.env` (Dev) oder Secret-Store (Prod).
- Neuer Compose-Service `keycloak-db` (Image `postgres:16`) mit eigenem Volume `keycloak_pg_data`, Healthcheck `pg_isready -U keycloak`.
- Realm-Import (`keycloak/realm-gustav.json`) greift nur beim ersten Start einer leeren Datenbank; Folgestarts verhindern Re-Import.
- Keine Änderungen an App-APIs oder Session-Speicherung notwendig; bestehendes bcrypt-Plugin und Theme bleiben unverändert.

## Umfang & Abgrenzung
**In Scope**
- Compose-/Env-Anpassungen, um Keycloak an Postgres zu binden.
- Dokumentation (Plan, ARCHITECTURE, README) für lokale Entwickler und Ops.
- Migration bestehender DEV-Daten (Realm-Export → Import in Postgres).
- Test- und Smoke-Checks (pytest, E2E) gegen Postgres-gestütztes Keycloak.

**Out of Scope**
- Änderungen an GUSTAV-APIs oder Use Cases.
- Umstellung der Applikations-Sessions auf Postgres (bleibt Supabase).
- Erweiterungen wie Keycloak-Clustering oder IServ-Anbindung (eigenständige Initiativen).

## Architektur- & Infrastrukturentscheidungen
- PostgreSQL bleibt zentraler Datenspeicher (Synergie mit Supabase, bestehende Tooling-Kette).
- Für DEV wird ein Compose-interner Postgres-Dienst betrieben; Prod nutzt eine gemanagte Instanz (z. B. Supabase, Cloud SQL) mit TLS, Firewall und getrennten Rollen.
- Secrets werden nicht eingecheckt: `.env` nur als Vorlage; Prod/Stage beziehen Credentials aus Secret-Store/CI.
- Monitoring/Backup folgen bestehenden Postgres-Best-Practices (z. B. regelmäßige Dumps, Retention-Policy, Alerting bei Ausfällen).

## Aufgabenpakete
1. **Doku abschließen**  
   - Dieses Plan-Dokument finalisieren (erledigt).  
   - `docs/ARCHITECTURE.md` und README mit Hinweis auf Postgres-Persistenz aktualisieren.
2. **Compose & Env vorbereiten**  
   - `docker-compose.yml`: Keycloak-Service auf Postgres umstellen, neuen Service `keycloak-db` einfügen, `depends_on` + Healthcheck setzen, `keycloak_pg_data`-Volume definieren.  
   - `.env.example`: `KC_DB`, `KC_DB_URL`, `KC_DB_USERNAME`, `KC_DB_PASSWORD` ergänzen; Hinweis auf Secrets einfügen.
3. **Migration DEV**  
   - Bestehendes Realm via Admin-Konsole/CLI exportieren (Fallback-Backup).  
   - Compose stoppen, altes Volume entfernen, neue Services starten, Erstimport prüfen.  
   - Manuelle Smoke-Checks (Admin-Login, Demo-Account anlegen, Neustart → Account bleibt).
4. **Tests & QA**  
   - `.venv/bin/pytest -q` sicherstellen.  
   - `RUN_E2E=1 ... pytest -m e2e`.  
   - Optional: neuer E2E-Test „Keycloak-Nutzer übersteht Neustart“.  
   - GitHub Actions / CI aktualisieren, falls sie Keycloak starten.
5. **Rollout Prod**  
   - Managed Postgres bereitstellen, Zugriffsliste einrichten, SSL erzwingen.  
   - Secrets im Deployment setzen (`KC_DB_URL`, User, Passwort).  
   - Downtime-Fenster: Keycloak stoppen → Realm exportieren → neue Instanz importieren → Smoke-Tests.  
   - Backups/Monitoring aktivieren, On-Call briefen.

## Zeitplanung (Schätzung)
- Doku/Env-Vorbereitung: 0.5 PT  
- Compose-Anpassungen & lokale Migration: 1 PT  
- Tests & QA: 0.5 PT  
- Prod-Rollout inkl. Abnahme: 1 PT (+Puffer für Abstimmung)

## Risiken & Mitigation
- **Datenverlust beim Wechsel** → Vorab Realm-Export + Volume-Backup; Rollback-Skript bereithalten.  
- **DB-Ressourcen geteilt mit Supabase** → Ressourcenverbrauch beobachten; bei Engpass separate Instanz buchen.  
- **Fehlkonfiguration von Secrets** → CI-Checks auf gesetzte Variablen; Doku mit Schritt-für-Schritt-Anleitung.  
- **TLS/Firewall übersehen** → Prod-Checkliste mit SSL-Verifizierung und Netzsegment-Review.  
- **Compose-Drift zwischen Dev und Prod** → Eine zentrale Compose-/Helm-Definition, env-spezifische Overrides nur für Secrets.

## BDD-Szenarien (Operations)
1. **Persistenz über Neustart**  
   - Given leere Keycloak-DB  
   - When `docker compose up` (Erststart)  
   - Then Realm `gustav` ist importiert und Anmelden möglich  
   - When User `teacherX` wird angelegt und Keycloak neu gestartet  
   - Then User `teacherX` existiert weiterhin
2. **Kein Re-Import**  
   - Given Keycloak-DB mit Realm `gustav`  
   - When Keycloak erneut startet  
   - Then kein erneuter Import überschreibt Daten
3. **DB offline**  
   - Given Postgres nicht erreichbar  
   - When Keycloak startet  
   - Then Start schlägt fehl, Log meldet „Database is not reachable“
4. **Login-Flow bleibt intakt**  
   - Given Dienste laufen (web, keycloak, postgres)  
   - When E2E Login/Logout getestet wird  
   - Then alle Flows sind erfolgreich, Cookies und Redirects unverändert

## Akzeptanzkriterien
- Keycloak-Benutzer überstehen Container-Neustarts und Rebuilds in Dev und Prod.  
- Login-/Logout-/Forgot-Password-Flows funktionieren unverändert (pytest/E2E grün).  
- Dokumentation beschreibt Setup, Migration und Betrieb klar; Entwickler können lokal ohne Zusatz-DB starten.  
- Backups/Monitoring sind für Prod definiert und aktiviert.
