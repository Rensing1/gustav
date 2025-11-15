# 2025-11-15 – Learning-Worker Queue Bereinigung

Status: geplant

## Kontext
- Referenz: `docs/plan/2025-11-14-PR-fix3.md`, Must-Fix 0 („Legacy-Queues blockieren Worker“).
- Problem: Der Worker leased noch optional aus `learning_submission_ocr_jobs`, löscht/requeued Jobs aber ausschließlich in `learning_submission_jobs`. Legacy-Deployments würden dadurch hängen bleiben.
- Ziel: Legacy-Queue endgültig entfernen, Worker vereinfachen, Tests & Docs aktualisieren.

## User Story
> Als Learning-Worker-Betreiber:in möchte ich, dass es nur noch eine einheitliche Queue-Tabelle (`learning_submission_jobs`) gibt, damit alle Deployments deterministisch arbeiten und keine Jobs in verwaisten Legacy-Tabellen hängen bleiben.

## BDD-Szenarien
1. **Happy Path (einzige Queue vorhanden)**  
   - **Given** eine Migration hat `learning_submission_ocr_jobs` entfernt und eine Submission ist in `learning_submission_jobs` mit Status `queued`  
   - **When** der Worker `run_once()` ausführt  
   - **Then** der Job wird geleast, verarbeitet und der Datensatz aus `learning_submission_jobs` gelöscht

2. **Edge Case (Datenbank ohne Queue-Tabellen)**  
   - **Given** `learning_submission_jobs` existiert nicht (zerschossenes Setup)  
   - **When** `run_once()` aufgerufen wird  
   - **Then** der Worker beendet sich sauber ohne Job-Verarbeitung und protokolliert den Fehlerzustand, statt auf `learning_submission_ocr_jobs` zurückzufallen

3. **Fehlerfall (Migration trifft auf Legacy-Tabelle)**  
   - **Given** ein Staging-System enthält noch `learning_submission_ocr_jobs` mit Daten  
   - **When** die neue Migration ausgeführt wird  
   - **Then** die Tabelle wird in einem `drop table if exists ... cascade` entfernt, sodass zukünftige Worker-Läufe nicht mehr versuchen können, daraus zu lesen

## API / OpenAPI
Es ist kein externer API-Endpunkt betroffen. Die Worker-Queue ist ein internes Infrastruktur-Detail. Daher enthält `api/openapi.yml` **keine Änderungen**; bestehende Contracts für Submission-Uploads bleiben unverändert.

## Datenmodell & Migration
- **Ziel**: `learning_submission_ocr_jobs` vollständig entfernen (inkl. Sequenzen/Indizes).  
- **Migrationsentwurf**:  
  ```sql
  -- supabase/migrations/20251115000000_drop_learning_submission_ocr_jobs.sql
  drop table if exists public.learning_submission_ocr_jobs cascade;
  comment on table public.learning_submission_ocr_jobs is null;
  ```
  (Datum/Dateiname wird durch `supabase migration new` vergeben.)
- Keine neuen Spalten oder RLS-Anpassungen nötig, da `learning_submission_jobs` bereits produktiv ist.

## Teststrategie (Red → Green)
1. **Migration-Test** (`backend/tests/migration/test_learning_worker_queue_drop.py`):  
   - Setzt mit psycopg eine temporäre Tabelle `learning_submission_ocr_jobs`, führt alle Migrationen aus, erwartet `to_regclass('public.learning_submission_ocr_jobs') is null`.
2. **Worker-Test** (`backend/tests/test_learning_worker_jobs.py` oder neues Spezialfile):  
   - Patcht `_lease_next_job`-Flow, stellt sicher, dass ausschließlich `learning_submission_jobs` angesprochen wird (z.B. via `psycopg`-Spy oder explizite Insert/Selects).  
   - Erwartet, dass `_resolve_queue_table` entfernt ist und ein fehlender Table-Name einen klaren Fehler wirft.

## Tasks
1. Migration erzeugen (`supabase migration new drop_learning_submission_ocr_jobs`) und SQL eintragen.  
2. Worker vereinfachen (`process_learning_submission_jobs.py`): `_resolve_queue_table` löschen, DML hart auf `learning_submission_jobs`, Logging ergänzen.  
3. Tests implementieren (Migration + Worker).  
4. Docs aktualisieren (`docs/CHANGELOG.md`, ggf. `docs/ARCHITECTURE.md` Storage/Worker-Sektion, README-Hinweis „Legacy-Queue entfernt“).  
5. Pytest und Supabase-Migrationen laufen lassen, Ergebnisse dokumentieren.

## Risiken / Mitigation
- **Rollback-Fähigkeit**: Drop ist destruktiv. Vor Deploy sicherstellen, dass keine Deployments mehr `learning_submission_ocr_jobs` befüllen (laut Review schon seit Import-Fixes).  
- **Testdauer**: Migrationstest kann langsam sein; möglichst zielgerichtete DB-Setup-Helfer nutzen.

