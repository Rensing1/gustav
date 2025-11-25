# Plan: Daily Backups for Supabase DB, Storage Buckets, and Keycloak (2025-11-25)

## Kontext & Ziel
- Ziel: Tägliches Backup aller kritischen Daten (Supabase-Postgres inkl. Auth/User, Supabase-Storage-Buckets `materials`/`submissions`, Keycloak-Daten) in `/backups`, automatisch per Cron im Container, mit Aufbewahrung 7 Tage.
- Vorgaben: Keine Verschlüsselung, Nutzung ausschließlich der Secrets aus `.env`, identisches Verhalten in allen Umgebungen (lokal = prod), keine Backups für Ollama.
- Nicht-Ziele: Keine API-Änderungen, keine Schema-Migrationen, kein zusätzliches Monitoring.

## User Story
Als Betreiber von GUSTAV möchte ich, dass automatisch ein tägliches, einfach wiederherstellbares Backup der Datenbank, der Storage-Buckets und der Keycloak-Daten im Verzeichnis `/backups` erzeugt und 7 Tage vorgehalten wird, damit ich im Notfall schnell und nachvollziehbar wiederherstellen kann.

## BDD-Szenarien (Given-When-Then)
1) Happy Path  
Given `.env` enthält gültige DSNs/URLs für Supabase-DB und Keycloak-DB und die Storage-Pfade existieren  
When der Cron-Job läuft  
Then wird unter `/backups/<timestamp>/` ein Supabase-DB-Dump (`pg_dump` als plain SQL, gzipped), ein Keycloak-DB-Dump (plain SQL, gzipped) und ein Tarball der Supabase-Storage-Buckets erstellt und der Lauf protokolliert.

2) Retention  
Given es existieren Backup-Ordner, die älter als 7 Tage sind  
When der Cron-Job läuft  
Then werden diese Ordner gelöscht, neuere Backups bleiben bestehen.

3) Fehlende Umgebungsvariable  
Given eine erforderliche Variable (z. B. `DATABASE_URL` oder `KC_DB_URL`) fehlt  
When der Cron-Job startet  
Then bricht das Skript mit klarer Fehlermeldung ab und erzeugt kein neues Backup.

4) Supabase-DB-Dump schlägt fehl  
Given `pg_dump` liefert einen Fehlercode  
When das Skript läuft  
Then wird der Lauf als fehlgeschlagen gemeldet und keine weiteren Schritte (Storage/Keycloak) mehr ausgeführt.

5) Storage-Pfad fehlt oder ist leer  
Given der erwartete Storage-Wurzelpfad existiert nicht  
When das Skript versucht, den Tarball zu erstellen  
Then schlägt der Lauf fehl und protokolliert den fehlenden Pfad.

6) Keycloak-Dump schlägt fehl  
Given `pg_dump` für Keycloak liefert einen Fehlercode  
When das Skript läuft  
Then wird der Lauf als fehlgeschlagen protokolliert, Supabase-Dump/Storage-Tarball bleiben erhalten, aber der Gesamtstatus ist „failed“.

## API-Vertrag & Migrationen
- Keine API-Änderungen nötig (`api/openapi.yml` bleibt unverändert).
- Keine Schema-Migrationen nötig; Backup arbeitet nur lesend.

## Backup-Artefakte & Formate
- Supabase-DB: `pg_dump --format=plain` nach `/backups/<ts>/supabase_db.sql.gz` (DSN aus `.env`: bevorzugt `SESSION_DATABASE_URL` falls gesetzt, sonst `DATABASE_URL`; muss ausreichende Rechte für Auth-Schema haben).
- Keycloak-DB: `pg_dump --format=plain` nach `/backups/<ts>/keycloak_db.sql.gz` (DSN aus `KC_DB_URL` + Credentials aus `.env`).
- Storage: Tarball der Supabase-Storage-Buckets (Standard-Lokation `supabase/storage`, config-basiert) nach `/backups/<ts>/storage_buckets.tar.gz`.
- Optionales Manifest (JSON) mit Timestamp, DSN-Labels (ohne Secrets), Exit-Codes und Checksums für Nachvollziehbarkeit.

## Test-Design (TDD)
- Pytest erstellt temporäres Backup-Ziel (`tmp_path / "backups"`), setzt erforderliche ENV-Variablen und nutzt eine echte lokale Test-Datenbank (separate DB im vorhandenen Postgres, z. B. `backup_test`) mit einer Dummy-Tabelle, damit `pg_dump` real läuft.  
- Externe Aufrufe (`subprocess.run`) für `pg_dump`/`tar` werden nicht vollgemockt, sondern mit echten Binaries ausgeführt; Pfade/Env werden kontrolliert.  
- Assertions: erzeugte Dateien existieren, Dumps enthalten die Dummy-Tabelle, Retention löscht Ordner >7 Tage. Fehlerpfade werden über Exit-Code/Log geprüft.

## Implementierungsskizze
- Neues Skript (z. B. `scripts/backup_daily.py`) mit klaren Flags für Zielpfad, Timestamp-Format, Retention-Tage; nutzt nur ENV aus `.env`.
- Schritte: (1) Validate ENV & Pfade, (2) create timestamped dir, (3) run `pg_dump` Supabase, (4) run `pg_dump` Keycloak, (5) tar storage root, (6) optional manifest schreiben, (7) retention cleanup.
- Cron: vorbereitete Crontab-Zeile für täglichen Lauf (UTC, z. B. 02:00); wird im Container über `crond` oder systemd-Timer eingebracht (Compose-Service vorbereitet).
- Logging: stdout/stderr mit klaren Fehlermeldungen; Exit-Code !=0 bei Fehler.

## Offene Punkte / Annahmen
- `pg_dump` ist im Container verfügbar (ggf. via Base-Image sicherstellen).
- Ausreichende DB-Rechte: Supabase-DSN hat Zugriff auf Auth-Schema; Keycloak-DSN hat ausreichende Rechte für vollständigen Dump.
- Storage-Pfad: Standard `supabase/storage` (laut `supabase/config.toml`), keine zusätzlichen Buckets außer `materials`/`submissions`.

## Nächste Schritte
- Failing Pytest nach obigem Design ergänzen (inkl. Setup der Test-DB).
- Minimalimplementierung des Backup-Skripts, bis der Test grün ist.
- Cron-Integration (Compose/Service) und Dokumentation finalisieren.
