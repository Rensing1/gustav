# Hardware Cutover Playbook

Status: Stable
Owner: Ops/Platform + Felix

## Ziel
Risikoarmer Umzug auf neue Hardware (DB, Web, Keycloak, Proxy) mit klaren Abbruchkriterien und Rollback.

## Timeline (Beispiel)
- T-7d: Planung, Stakeholder, Freeze-Fenster kommunizieren.
- T-1d: Vollbackup (DB + Storage), Restore-Test, Preflight-Checks grün.
- T-0h: Freeze Start, Downscaling, Cutover, Validation, Unfreeze.
- T+1d: Nachkontrollen, Monitoring, Abschlussreport.

## Verantwortlichkeiten
- Plattform: Compose/Deploy, DNS/Proxy, Monitoring.
- DB: Backup/Restore, Rollen/DSN, Performance.
- App: Smoke-Tests, E2E, Release-Freigabe.

## Vorbereitung (T-1)
- Backups:
  - DB: `pg_dump -Fc -h <old-host> -U postgres -d postgres > backup.dump`
  - Storage: S3/Bucket-Export (siehe docs/operations/backup_restore.md).
- Provisioning:
  - `gustav_limited NOLOGIN`, Login-User `gustav_app IN ROLE gustav_limited`.
  - Secrets/ENV in Secret-Store hinterlegen.
  - Compose-DSNs prüfen (service-name statt 127.0.0.1).
- Preflight:
  - `make db-login-user` (DEV/Stage), `make up`, `make ps`, `make supabase-status`.
  - `scripts/preflight.sh` (alle Checks grün).

## Cutover (T-0)
1) Freeze fachliche Änderungen (Kommunikation im Team/Schule).
2) Downscale alte Web/Proxy-Instanzen (nur DB aktiv für Abschluss-Backup).
3) Finales Backup + Restore auf neuer DB.
4) Start neue Dienste: `docker compose up -d --build`.
5) DNS/Proxy-Switch (CNAME/Reverse-Proxy auf neue Targets).
6) Validation:
   - `/health` → 200
   - Login-Flow (E2E Login/Register), `/api/me` → 200
   - Lehrenden-Flow: Kurs anlegen, Listen laden
7) Unfreeze.

## Abbruchkriterien
- Health 200 nicht erreichbar > 5 min.
- Login-Flow bricht mit 5xx/4xx wiederholt.
- DB-Fehler (FATAL/NOLOGIN/Permission) nicht zeitnah lösbar.

## Rollback (falls Abbruch)
1) Proxy/DNS zurück auf alt.
2) Alte Web/Keycloak wieder hochfahren.
3) Ursachenanalyse, Fix, erneute Preflight-Checks.

## Post-Cutover (T+1)
- Logs/Fehler prüfen, Sessions/Last, grobe KPIs.
- PRs/Doku aktualisieren, Lessons Learned.

