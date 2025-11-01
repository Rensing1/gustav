# Legacy Backup Import Guide (Alpha2)

Dieses Handbuch erklärt, wie du den aktuellen Legacy-Datenstand aus dem Archiv `docs/migration/supabase_backup_20251101_103457.tar.gz` in eine lokale Alpha2-Supabase-Instanz überführst. Es richtet sich an alle, die Tests mit realistischen Daten fahren oder einen kompletten Datenstand für Entwicklung/QA benötigen.

## 1. Voraussetzungen prüfen
- `supabase` CLI installiert und im PATH.
- Lokale Supabase-Entwicklungsumgebung lauffähig (`supabase status`).
- Mindestens 8 GB freier Speicherplatz (Backup + entpackter Dump + temporäre DB).
- Aktuelle `.env`/Secrets im Repository hinterlegt.
- Python-Umgebung aktivierbar (`python -m venv .venv && source .venv/bin/activate` bei Bedarf).

> Tipp: Wenn bereits eine lokale Alpha2-Datenbank läuft, sichere deine Daten (z. B. `supabase db dump`) bevor du den Reset startest.

## 2. Repository vorbereiten
1. Stelle sicher, dass du im Alpha2-Projektverzeichnis arbeitest (z. B. `/home/felix/gustav-alpha2`).
2. Aktualisiere das Repository (`git pull`), damit alle Migrationstools aktuell sind.
3. Installiere Python-Abhängigkeiten, falls noch nicht erfolgt:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## 3. Lokale Supabase zurücksetzen und starten
1. Stoppe ggf. laufende Container (`supabase stop`).
2. Setze die Entwicklungsdatenbank zurück und spiele das aktuelle Schema ein:
   ```bash
   supabase db reset
   ```
3. Prüfe den Status und notiere den Postgres-DSN (wird für `pg_restore` benötigt):
   ```bash
   supabase status
   ```
   Typischer DSN für Service-Rolle: `postgresql://postgres:postgres@127.0.0.1:54322/postgres`. Exportiere ihn optional als Variable:
   ```bash
   export SERVICE_ROLE_DSN="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
   ```

## 4. Legacy-Backup entpacken
1. Navigiere in den Migrationsordner und entpacke das Archiv:
   ```bash
   cd docs/migration
   tar -xzf supabase_backup_20251101_103457.tar.gz
   ```
2. Nach dem Entpacken findest du entweder eine `.tar`-Datei (Custom-Format) oder eine `.sql`. Notiere den Pfad, z. B. `/home/felix/gustav-alpha2/docs/migration/supabase_backup_20251101_103457.tar`.

## 5. Legacy-Schema in separatem Namespace einspielen
Wir laden den Dump in ein eigenes Schema `legacy_raw`, damit wir die Legacy-Struktur parallel zum Alpha2-Schema auswerten können.

1. Lege das Schema an:
   ```bash
   psql "$SERVICE_ROLE_DSN" -c "create schema if not exists legacy_raw;"
   ```
2. Spiele das Backup in das Schema ein (ersetze `$DUMP_PATH` mit der entpackten Datei, egal ob `.tar` oder `.sql`):
   ```bash
   pg_restore \
     --clean \
     --if-exists \
     --schema=public \
     --dbname="$SERVICE_ROLE_DSN" \
     "$DUMP_PATH"
   ```
3. Verschiebe anschließend alle Legacy-Objekte in `legacy_raw` (falls der Dump feste Schemaangaben nutzt):
   ```bash
   psql "$SERVICE_ROLE_DSN" -f docs/migration/sql/move_legacy_to_raw.sql
   ```
   > Wenn `move_legacy_to_raw.sql` noch nicht existiert, erstelle eine einfache SQL-Datei, die Tabellen/Views von `public` nach `legacy_raw` umzieht (`alter table ... set schema legacy_raw;`).
4. Verifiziere den Import:
   ```bash
   psql "$SERVICE_ROLE_DSN" -c "select count(*) from legacy_raw.course;"
   ```

## 6. ETL in das Alpha2-Schema durchführen
### 6.1 Identity-Mapping
- Synchronisiere die Benutzer-IDs zwischen Legacy und Alpha2:
  ```bash
  .venv/bin/python -m backend.tools.sub_mapping_sync \
    --db-dsn "$SERVICE_ROLE_DSN" \
    --from-schema legacy_raw
  ```
- Prüfe die Tabelle `public.legacy_user_map` (Legacy-ID ↔ neues `sub`).

### 6.2 Kurs- und Inhaltsdaten übernehmen
- Verwende die vorbereiteten SQL/Python-Skripte aus `docs/migration/sql/` und `backend/tools/`:
  ```bash
  psql "$SERVICE_ROLE_DSN" -f docs/migration/sql/import_courses_from_legacy.sql
  psql "$SERVICE_ROLE_DSN" -f docs/migration/sql/import_units_from_legacy.sql
  psql "$SERVICE_ROLE_DSN" -f docs/migration/sql/import_sections_from_legacy.sql
  ```
- Falls Python-ETL benötigt wird (z. B. für komplexe JSON-Transformationen):
  ```bash
  .venv/bin/python -m backend.tools.legacy_material_import \
    --db-dsn "$SERVICE_ROLE_DSN" \
    --legacy-schema legacy_raw \
    --target-schema public
  ```

### 6.3 Aufgaben und Einreichungen
- Aufgaben importieren:
  ```bash
  psql "$SERVICE_ROLE_DSN" -f docs/migration/sql/import_tasks_from_legacy.sql
  ```
- Schülerabgaben inklusive Anhänge:
  ```bash
  .venv/bin/python -m backend.tools.legacy_submission_import \
    --db-dsn "$SERVICE_ROLE_DSN" \
    --legacy-schema legacy_raw \
    --storage-root /tmp/legacy_storage \
    --batch-size 500
  ```
- Fehlende Dateien werden protokolliert; prüfe das Log (`migration.log`).

### 6.4 Veröffentlichungen und Sichtbarkeiten
- Modul-/Abschnittsfreigaben nachziehen:
  ```bash
  psql "$SERVICE_ROLE_DSN" -f docs/migration/sql/import_releases_from_legacy.sql
  ```
- Setze `released_by`, falls im Legacy-Datensatz kein eindeutiger Lehrer vorhanden ist. Nutze dafür den Kurs-Owner oder den Fallback `system`.

## 6a. Legacy ↔ Alpha2 Schema Mapping (Überblick)
Nutze diesen Abschnitt als Referenz, wenn du während des ETL-Laufs Feldzuordnungen oder notwendige Transformationen nachschlagen willst. Alle Beispiele beziehen sich auf die Legacy-Tabellen aus `legacy_raw` (Dump `supabase_backup_20251101_103457`) und das aktuelle Alpha2-Schema laut `supabase/migrations`.

### Kurse & Mitgliedschaften
- **Legacy** `public.course(id uuid, name text, creator_id uuid, created_at, updated_at, created_by uuid)`
  - Quelle: `docs/migration/tmp/legacy_schema/all_schema.sql:9793`
- **Alpha2** `public.courses(id uuid, title text, subject text?, grade_level text?, term text?, teacher_id text, created_at, updated_at)`
  - Quelle: `supabase/migrations/20251020150101_teaching_courses.sql:20`
- **Mapping**
  - `id` bleibt erhalten (Explizit-Insert möglich).
  - `name → title`.
  - `creator_id → teacher_id` via `legacy_user_map` (OIDC `sub`).
  - `subject`, `grade_level`, `term` sind neu → zunächst `NULL` lassen.
  - `created_by` existiert nur im Legacy-Schema → optionales Audit-Feld.
- **Memberships**
  - `public.course_student(course_id uuid, student_id uuid, enrolled_at)` → `public.course_memberships(course_id uuid, student_id text, created_at)`
  - `student_id` muss über die Mapping-Tabelle in einen OIDC-`sub` (Text) umgewandelt werden.
  - `enrolled_at → created_at`.
  - `course_teacher` wird nicht übernommen (Owner steckt in `courses.teacher_id`).

### Lerneinheiten & Kursmodule
- **Legacy** `public.learning_unit(id uuid, title text, creator_id uuid, created_at, updated_at)`
- **Alpha2** `public.units(id uuid, title text, summary text?, author_id text, created_at, updated_at)`
- **Mapping**
  - `id` kann beibehalten werden.
  - `title` bleibt gleich.
  - `summary` existiert neu → `NULL`, bis Inhalte gepflegt werden.
  - `creator_id → author_id` (via `legacy_user_map`).
- **Kurs-Zuordnung**
  - `public.course_learning_unit_assignment(course_id, unit_id, assigned_at)` → `public.course_modules(id uuid, course_id, unit_id, position int, context_notes text?, created_at, updated_at)`
  - Für jede Kursbeziehung eine Positionsliste generieren (`position = ROW_NUMBER() OVER (PARTITION BY course ORDER BY assigned_at)` o. ä.).
  - `context_notes` bleibt leer.
  - `created_at = assigned_at`, `updated_at = assigned_at` (oder `now()` bei Fehlen).
  - Unique-Constraints (`(course_id, position)` und `(course_id, unit_id)`) beachten.

### Abschnitte & Freigaben
- **Legacy** `public.unit_section(id uuid, unit_id uuid, title text?, order_in_unit int, materials jsonb, created_at, updated_at)`
  - `title` war optional; fehlende Werte mit Platzhaltern ergänzen.
  - `order_in_unit` startet bei 0 → auf 1-basiges `position` anheben.
  - `materials` enthält Markdown/Dateien als JSON (siehe Abschnitt Materialien).
- **Alpha2** `public.unit_sections(id uuid, unit_id uuid, title text, position int, created_at, updated_at)`
- **Freigaben**
  - `public.course_unit_section_status(course_id, section_id, is_published, published_at)` → `public.module_section_releases(course_module_id uuid, section_id uuid, visible boolean, released_at timestamptz, released_by text)`
  - Vor dem Insert `course_module_id` via `(course_id, unit_id)` Lookup bestimmen.
  - `is_published → visible`.
  - `published_at → released_at`.
  - `released_by` muss gesetzt sein: Owner-`sub` aus `courses.teacher_id` oder Fallback `'system'` (vgl. `docs/migration/legacy_data_import_plan.md:50`).

### Materialien
- **Legacy-Datenquelle**
  - `unit_section.materials` (JSON) mit Elementen wie `{ "type": "markdown", "title": "…", "body": "…" }` oder Datei-Objekten mit `asset_id`.
  - `unit_material_asset` (separate Tabelle, u. a. `storage_key`, `mime_type`, `size_bytes`) plus zugehörige Dateien im Backup-Verzeichnis `storage_raw/section_materials/...`.
- **Alpha2-Ziel** `public.unit_materials(id uuid, unit_id uuid, section_id uuid, title text, body_md text?, kind text, storage_key text?, filename_original text?, mime_type text?, size_bytes integer?, sha256 text?, alt_text text?, position int, created_at, updated_at)`
- **Mapping**
  - Markdown: `kind='markdown'`, `body_md` aus JSON, Datei-Felder bleiben `NULL`.
  - Dateien: `kind='file'`, Metadaten zwingend (`storage_key`, `filename_original`, `mime_type`, `size_bytes`, `sha256`). Hash/Größe beim Import anhand des Backups berechnen.
  - Fehlende Blobs → als Markdown-Link importieren (`kind='markdown'`, `body_md` mit Link) und Outlier protokollieren.
  - `position` pro Abschnitt ab 1 durchnummerieren.

### Aufgaben
- **Legacy**
  - `task_base(id uuid, section_id uuid?, instruction text, task_type text, criteria text, assessment_criteria jsonb, solution_hints text, order_in_section int, created_at, updated_at)`
  - `regular_tasks(task_id uuid, order_in_section int, max_attempts int, prompt text, grading_criteria text[], solution_hints text)`
- **Alpha2** `public.unit_tasks(id uuid, unit_id uuid, section_id uuid, instruction_md text, criteria text[], hints_md text?, max_attempts int?, due_at?, position int, created_at, updated_at)`
- **Mapping**
  - `instruction` oder `regular_tasks.prompt` → `instruction_md` (Markdown).
  - `assessment_criteria` (JSON) → `criteria` (`text[]`).
  - `solution_hints` → `hints_md`.
  - `order_in_section` → 1-basiertes `position`.
  - `unit_id` aus zugehörigem Abschnitt ableiten (`unit_sections.unit_id`).
  - `max_attempts` aus `regular_tasks`, `NULL` = unbegrenzt.
  - Mastery-Daten (`mastery_tasks`) werden ausgelassen und nur geloggt (`docs/migration/legacy_data_import_plan.md:11`).

### Einreichungen
- **Legacy** `public.submission(id uuid, student_id uuid, task_id uuid, submitted_at, submission_data jsonb, ai_feedback text, …, attempt_number int, feedback_status text, retry_count int, ai_insights jsonb, …)`
  - Assets liegen im Storage-Backup `storage_raw/submissions/...`.
- **Alpha2** `public.learning_submissions(id uuid, course_id uuid, task_id uuid, student_sub text, kind text, text_body text?, storage_key text?, mime_type text?, size_bytes int?, sha256 text?, attempt_nr int, analysis_status text, analysis_json jsonb?, feedback_md text?, error_code text?, created_at, completed_at?)`
- **Mapping**
  - `student_id → student_sub` (Mapping).
  - `attempt_number → attempt_nr`.
  - `submission_data`: Textantworten in `text_body`, Medien mit `storage_key`/`mime_type`/`size_bytes`/`sha256` ablegen.
  - AI-Felder (`ai_feedback`, `feed_back_text`, `feed_forward_text`, `ai_insights`) als `feedback_md` bzw. `analysis_json`.
  - `feedback_status` auf Alpha2-Enum (`pending`, `completed`, `error`) mappen.
  - `course_id` über Task→Section→Unit→Course-Modul ermitteln; fehlende Zuordnung als Outlier `missing_course` protokollieren.

### Nicht migrierte Bereiche
- Mastery-Tabellen (`mastery_tasks`, `student_mastery_progress`, `mastery_log`, `user_model_weights`) bleiben außen vor.
- Legacy-Queues (z. B. Submission-Processing) werden verworfen.
- `course_teacher` sowie eventuelle Mehrfach-Owner fließen nicht ins Ziel; stattdessen Audit-Eintrag erzeugen.

> Hinweis: Für jeden Abschnitt empfiehlt es sich, eine kleine SQL- oder Python-Hilfsfunktion zu schreiben, die die oben genannten Transformationen kapselt. Damit bleibt der eigentliche ETL-Lauf reproduzierbar und gut testbar.

## 7. Validierung & Smoke-Tests
1. Zählwerte prüfen:
   ```bash
   psql "$SERVICE_ROLE_DSN" -f docs/migration/sql/check_entity_counts.sql
   ```
2. Sanity-Checks für RLS:
   ```bash
   psql "$SERVICE_ROLE_DSN" -v sub='teacher-sub-uuid' -f docs/migration/sql/check_rls_teacher_access.sql
   ```
3. Starte danach die Anwendung (`docker compose up -d --build` oder Frontend) und führe manuell Stichproben aus (Kursübersicht, Lerneinheit öffnen, Aufgabe ansehen).

## 8. Troubleshooting
- **`pg_restore` schlägt wegen vorhandener Objekte fehl**: Stelle sicher, dass `supabase db reset` erfolgreich war. Alternativ `--clean --if-exists` setzen, wie oben gezeigt.
- **Verwaiste Einträge in `legacy_user_map`**: Führe den User-Mapping-Lauf erneut aus oder ergänze manuell fehlende Zuordnungen.
- **Fehlende Dateien**: Prüfe den Pfad `/tmp/legacy_storage`. Im Zweifel nutze `docs/migration/sql/materials_as_links.sql`, um fehlende Dateien temporär als Markdown-Link einzutragen.
- **Constraint-Verletzungen**: Schaue in das Skript-Log; korrigiere die Daten in `legacy_raw` oder passe das ETL-Skript an.

## 9. Aufräumen
- Entferne temporäre Dateien (`rm docs/migration/supabase_backup_20251101_103457.*`).
- Falls nicht mehr benötigt, lösche die Tabellen im `legacy_raw`-Schema:
  ```bash
  psql "$SERVICE_ROLE_DSN" -c "drop schema legacy_raw cascade;"
  ```
- Stoppe Supabase, falls du Ressourcen sparen möchtest: `supabase stop`.

## 10. Weiterführende Dokumente
- `docs/migration/legacy_data_import_plan.md` – detaillierter Projektplan und Annahmen.
- `docs/migration/legacy_migration_cli_usage.md` – Beschreibung der vorhandenen CLI-Tools.
- `docs/migration/sql/` – SQL-Skripte für spezifische Import-Schritte.
- `legacy-code-alpha1/backend/tools/` – Python-Hilfsprogramme für Transformationen.

## 11. Automatisierter Gesamtlauf (Fallback)
Wenn du alle Schritte oben nicht einzeln ausführen möchtest, kannst du den gesamten Prozess mit dem neuen Skript `scripts/import_legacy_backup.py` automatisieren. Das Skript erledigt:
- Restore des Dumps in ein isoliertes Schema (Standard `legacy_raw`).
- Aufbau der `legacy_user_map` inklusive Fallback-Subs für Legacy-Benutzer.
- ETL sämtlicher relevanter Tabellen (Kurse, Units, Materialien, Aufgaben, Abgaben, Releases) unter Beachtung der Mapping-Regeln.
- Provisionierung des lokalen App-Logins (`make db-login-user`), sofern dieser noch fehlt. Das Skript nutzt dafür die Variablen `DB_HOST`, `DB_PORT`, `DB_SUPERUSER`, `DB_SUPERPASSWORD`, `APP_DB_USER` und `APP_DB_PASSWORD`. Stelle sicher, dass diese Werte vor dem Lauf gesetzt sind (Standard: `postgres`/`postgres` auf 127.0.0.1:54322).
- Erstellung eines detaillierten JSON-Reports mit Zählwerten und eventuellen Warnungen (`docs/migration/reports/legacy_import_<timestamp>.json`).

Beispielaufruf:

```bash
.venv/bin/python scripts/import_legacy_backup.py \
  --dump docs/migration/supabase_backup_20251101_103457.tar.gz \
  --dsn "postgresql://postgres:postgres@127.0.0.1:54322/postgres" \
  --legacy-schema legacy_raw \
  --workdir .tmp/migration_run
```

Optional:
- `--dry-run` zeigt die Statistiken an, ohne Inserts zu schreiben.
- `--report` legt den Report-Pfad fest.
- `--keep-temp` lässt entpackte Dumps im Workdir.
- `--kc-base-url`, `--kc-host-header`, `--kc-admin-user`, `--kc-admin-pass` (optional) erlauben das automatische Nachziehen der echten Keycloak-`sub`-IDs anhand der Benutzer-E-Mail. Ohne diese Parameter vergibt das Skript wie bisher Platzhalter vom Typ `legacy-email:<adresse>`.

> Hinweis: Mastery-Daten bleiben bewusst außen vor. Das Skript protokolliert fehlende Zuordnungen (z. B. wenn ein Submission keinem Kurs zugeordnet werden kann) im Report.
