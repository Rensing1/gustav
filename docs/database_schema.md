# Datenbankschema – ausgewählte sicherheitskritische Strukturen

Stand: Version 0.0.4, zuletzt geprüft am 2026-08-16.

Dieses Dokument ist bewusst keine vollständige Spaltenreferenz. Die einzige Quelle der Wahrheit sind die geordneten SQL-Dateien unter `supabase/migrations/`; API-Payloads werden ausschließlich durch `api/openapi.yml` definiert. Hier werden ausgewählte Tabellenfamilien und Sicherheitsentscheidungen erklärt, bei denen eine reine Schemaauflistung den fachlichen Zusammenhang nicht ausreichend zeigt.

## Tabellenfamilien im Überblick

- Identity & Access: `app_sessions`, `bff_sessions`, `cli_tokens`;
- Teaching: `courses`, `course_memberships`, `course_modules`, `units`, `unit_sections`, `unit_phases`, `unit_modules`, `unit_module_edges`, `unit_materials`, `unit_tasks`, `module_section_releases`;
- Kurseinladungen: `course_invitations`, `course_invite_redemptions`, `course_invite_mail_batches`, `course_invite_mail_deliveries`;
- Learning: `learning_submissions`, `learning_submission_jobs`, `learning_submission_task_snapshots`, Dialog- und Exporttabellen;
- Practice: `learning_practice_states`, `learning_practice_sessions`, `learning_practice_session_stacks`, `learning_practice_session_items`, `learning_practice_attempts`;
- Betrieb und Datenschutz: `storage_deletion_outbox`, `course_deletion_jobs`, `ai_usage_events`, `dialog_ai_usage_events`, `concern_box_entries`.

Neue Tabellen oder Constraints werden ausschließlich per Migration ergänzt. Diese Übersicht darf deshalb niemals als Grundlage für manuelle Schemaänderungen verwendet werden.

## public.app_sessions

- Columns
  - `session_id` text PRIMARY KEY — opaque random identifier stored in the httpOnly cookie.
  - `sub` text NOT NULL — stable subject ID from the IdP.
  - `roles` jsonb NOT NULL — array of realm roles filtered to ["student", "teacher", "admin"].
  - `name` text NOT NULL — display name used in the UI.
  - `id_token` text NULL — optional; if stored, consider at‑rest protection and short TTL.
  - `expires_at` timestamptz NOT NULL — server‑side expiry.

- Indexes
  - `idx_app_sessions_sub (sub)`
  - `idx_app_sessions_expires_at (expires_at)`

- Security
  - Row Level Security enabled; no grants to `anon`/`authenticated`. Access via service role only.

- Retention
  - Expired rows should be purged regularly, e.g.: `delete from public.app_sessions where expires_at < now();`

## Teaching (Unterrichten)

- DSN usage
  - Runtime (app): Use a limited-role DSN (e.g., `gustav_limited`) so RLS is always active.
  - Migrations: Apply via `supabase migration up` (runs as owner/service). The app does not need to switch DSNs.
  - Sessions note: Das verbindliche Compose-Profil verwendet `SESSIONS_BACKEND=db`. In-Memory-Sessions sind ausschließlich Test-Doubles und kein produktiver Fallback.

- RLS policies
  - Policies are defined in `supabase/migrations/20251020154107_teaching_rls_policies.sql`.
  - They rely on `SET LOCAL app.current_sub = '<sub>'` per transaction to identify the acting user.

### Kurseinladungen

Die Migrationen `20260815120000_course_invitations.sql`, `20260815121000_course_invitation_redeem_conflict_fix.sql` und `20260815214500_course_invitation_mail_retry_hardening.sql` definieren den aktuellen Vertrag.

- `public.course_invitations` speichert Kursbindung, Ablauf, Widerruf und ausschließlich einen Digest der geheimen Nonce. Das vollständige Capability-Token wird nie persistiert.
- `public.course_invite_redemptions` macht die Einlösung atomar und idempotent und verhindert den unbemerkten Wiedereintritt über eine bereits verwendete Einladung.
- `public.course_invite_mail_batches` gruppiert einen Versandauftrag ohne dauerhaft eine Empfängerliste zu veröffentlichen.
- `public.course_invite_mail_deliveries` hält temporäre Zustellarbeit. Erfolgreiche Klartextadressen werden sofort entfernt; endgültig fehlgeschlagene spätestens nach der festgelegten Aufbewahrungsfrist.
- Eng begrenzte `SECURITY DEFINER`-Funktionen führen Rotation, Vorschau, Einlösung und Queue-Übergänge unter expliziten Rollen- und Ownership-Prüfungen aus.
- Archivierung eines Kurses widerruft seine aktive Einladung atomar.

### `public.unit_materials`

- Purpose: Materialien je Abschnitt. Unterstützt Markdown (`kind = 'markdown'`) und Datei-Materialien (`kind = 'file'`).
- Columns
  - `id uuid` primary key (`default gen_random_uuid()`).
  - `unit_id uuid not null` → `units(id)` (`on delete cascade`) to keep author-level ownership in sync.
  - `section_id uuid not null` → `unit_sections(id)` (`on delete cascade`).
  - `title text not null` — validated 1..200 Zeichen in der Application.
  - `body_md text` — Markdown-Inhalt (nur bei `kind='markdown'`, sonst `NULL`).
  - `position int not null` (`check position > 0`) — 1-basierte Reihenfolge innerhalb eines Abschnitts.
  - `kind text not null default 'markdown'` (`check kind in ('markdown','file')`).
- Datei-Metadaten (nur bei `kind='file'`):
    - `storage_key text` — Pfad im Storage-Bucket.
    - `filename_original text` — ursprünglicher Dateiname.
    - `mime_type text` — Content-Type.
    - `size_bytes integer` (`> 0`).
    - `sha256 text` — hex-codierter Hash (64 Zeichen, Regex `^[0-9a-f]{64}$`).
    - `alt_text text` — optionaler Alternativtext.
  - `created_at timestamptz default now()`, `updated_at timestamptz default now()`.
- Constraints & Indizes
  - `unique(section_id, position) DEFERRABLE INITIALLY IMMEDIATE` für stabile Reorder-Transaktionen.
  - Unique Index `unit_materials_storage_key_idx (storage_key) WHERE storage_key IS NOT NULL` verhindert doppelte Objektpfade.
  - CHECK `unit_materials_file_fields_check` stellt sicher, dass nur passende Spalten pro `kind` gesetzt werden (Markdown ohne Storage-Felder, Dateien mit vollständigen Metadaten).
  - Indizes `idx_unit_materials_unit` und `idx_unit_materials_section` beschleunigen Owner-Scopes.
  - Trigger `trg_unit_materials_updated_at` nutzt `set_updated_at()` für automatische Timestamps.
  - Trigger `trg_unit_materials_section_match` (`unit_materials_section_unit_match()`) stellt sicher, dass `section_id` zu `unit_id` gehört und nicht nachträglich gewechselt wird.
  - Storage-Key-Pfade werden beim Erzeugen/Finalisieren auf `[A-Za-z0-9._-]` normalisiert (Author/Unit/Section/Material) um Path-Traversal auf S3-kompatiblen Backends zu verhindern.
- Security / RLS
  - Tabelle ist RLS-aktiviert; `gustav_limited` besitzt `SELECT/INSERT/UPDATE/DELETE`.
  - Policies (`unit_materials_select/insert/update/delete_author`) spiegeln die Ownership von `units` wider (`app.current_sub`).
  - Inserts/Updates prüfen via Join auf `unit_sections`, dass nur eigene Abschnitte beschrieben werden.
  - Datei-Metadaten werden nur über Upload-Intents gesetzt (siehe unten).
  - Optionaler Alternativtext (`alt_text`, ≤ 500 Zeichen) kann nachträglich via API-PATCH gepflegt werden, um Barrierefreiheit zu verbessern.

### `public.upload_intents`

- Purpose: Kurzlebige Upload-Intents für Datei-Materialien. Kapselt Presign-Infos und Idempotenz.
- Columns
  - `id uuid` primary key (`default gen_random_uuid()`).
  - `material_id uuid not null` — vorab reservierte Material-ID.
  - `unit_id uuid not null` → `units(id)` (`on delete cascade`).
  - `section_id uuid not null` → `unit_sections(id)` (`on delete cascade`).
  - `author_id text not null` — Lehrkraft (`app.current_sub`).
  - `storage_key text not null` — erwarteter Objektpfad.
  - `filename text not null` — Originalname.
  - `mime_type text not null`.
  - `size_bytes integer not null` (`check size_bytes > 0`).
  - `expires_at timestamptz not null` — Ablauf der Intent-Validität.
  - `consumed_at timestamptz null` — wird gesetzt, sobald Finalize erfolgreich ist.
  - `created_at timestamptz default now()`.
- Constraints & Indizes
  - `unique(material_id)` und `unique(storage_key)` sichern Idempotenz und eindeutige Pfade.
  - Indizes `upload_intents_author_idx (author_id)` und `upload_intents_section_idx (section_id, material_id)` unterstützen Lookups.
- Security / RLS
  - Tabelle ist RLS-aktiviert; `gustav_limited` besitzt `SELECT/INSERT/UPDATE/DELETE`.
  - Policies (`upload_intents_select/insert/update/delete_author`) erlauben nur Zugriffe mit passendem `author_id = current_setting('app.current_sub')`.
- Lifecycle
  - Upload-Intent wird über Service-Layer erzeugt, validiert und nach Finalize (`consumed_at`) markiert.
  - Abgelaufene Intents können asynchron aufgeräumt werden (Follow-up).

### `public.module_section_releases`

- Purpose: Speichert den Freigabe-Status einzelner Abschnitte pro Kursmodul, damit Lehrkräfte Sichtbarkeit toggeln können.
- Columns
  - `course_module_id uuid not null` → `course_modules(id)` (on delete cascade).
  - `section_id uuid not null` → `unit_sections(id)` (on delete cascade).
  - `visible boolean not null` — `TRUE` wenn Abschnitt freigeschaltet ist, sonst `FALSE`.
  - `released_at timestamptz null` — Zeitpunkt der letzten Freischaltung (`NULL`, wenn aktuell verborgen).
  - `released_by text not null` — OIDC `sub` der Lehrkraft, die zuletzt den Status geändert hat.
- Constraints & Indizes
  - Primary Key `(course_module_id, section_id)` stellt Idempotenz sicher.
  - Indizes `idx_module_section_releases_module`, `idx_module_section_releases_section` unterstützen Lookups in beide Richtungen.
- Security / RLS
  - Tabelle ist RLS-aktiviert; Grants für `gustav_limited` (`SELECT/INSERT/UPDATE/DELETE`).
  - Policies prüfen, dass nur Kurs-Owner (via Join `course_modules` ↔ `courses`) lesen/schreiben dürfen und dass Abschnitte zur Unit des Moduls gehören.
  - `set_config('app.current_sub', ...)` wird vor jeder Operation gesetzt, damit RLS greift.
- Behavior
  - Upsert-Semantik: PATCH mit `visible=true/false` überschreibt vorhandene Zeile (Release-Historie wird intentionally nicht versioniert).
  - Cascade: Löschen eines Kursmoduls entfernt automatisch alle Freigaben durch `on delete cascade`.
  - Datenkonsistenz: CHECK-Constraint erzwingt `released_at IS NOT NULL` wenn `visible=true` und `released_at IS NULL` wenn `visible=false`.

### `public.unit_tasks`

- Purpose: Aufgaben (Tasks) je Abschnitt mit Positionslogik und RLS‑gestützter Ownership (Autor der Unit).
- Columns
  - `id uuid` primary key (`default gen_random_uuid()`).
  - `unit_id uuid not null` → `units(id)` (`on delete cascade`).
  - `section_id uuid not null` → `unit_sections(id)` (`on delete cascade`).
  - `instruction_md text not null` — Aufgabenbeschreibung (Markdown), serverseitig auf Nicht‑Leer validiert.
  - `criteria text[] not null default '{}'` — bis zu 10 Kriterien, keine leeren Einträge.
  - `teacher_context_md text null` — optionaler, lehrkraftseitiger KI‑Kontext (Markdown); wird nicht an Schüler ausgeliefert.
  - `due_at timestamptz null` — optionale Fälligkeit (UTC, ISO‑8601).
  - `max_attempts integer null check (max_attempts > 0)` — optionale Versuchsbegrenzung (≥ 1).
  - `position integer not null check (position > 0)` — 1‑basierte Reihenfolge im Abschnitt.
  - `created_at timestamptz not null default now()`, `updated_at timestamptz not null default now()`.
- Constraints & Indizes
  - `unit_tasks_instruction_not_blank`: `length(btrim(instruction_md)) > 0`.
  - `unit_tasks_criteria_length`: `array_length(criteria, 1) <= 10`.
  - `unit_tasks_criteria_entries_not_blank`: keine leeren Strings in `criteria`.
  - `unique(section_id, position) DEFERRABLE INITIALLY IMMEDIATE` — stabile, atomare Reorder‑Transaktionen.
  - Trigger `trg_unit_tasks_updated_at` (setzt `updated_at`).
  - Trigger `trg_unit_tasks_section_match` (Funktion `unit_tasks_section_unit_match()`):
    - Erzwingt, dass `section_id` zur `unit_id` gehört.
    - Verhindert Änderung von `section_id` bei Updates (immutabel).
  - Indizes `idx_unit_tasks_section`, `idx_unit_tasks_unit` beschleunigen Owner‑Scopes.
- Security / RLS
  - Tabelle ist RLS‑aktiviert; `gustav_limited` besitzt `SELECT/INSERT/UPDATE/DELETE`.
  - Policies spiegeln Ownership über Join zu `units` wider; Identität via `set_config('app.current_sub', ...)`:
    - `unit_tasks_select_author`
    - `unit_tasks_insert_author`
    - `unit_tasks_update_author`
    - `unit_tasks_delete_author`

Hinweise
- Reorder erfolgt ausschließlich über API (`POST /api/teaching/units/{unit_id}/sections/{section_id}/tasks/reorder`) mit Mengen‑Gleichheit der IDs und ohne Duplikate.
    - Validierungen auf der API‑Ebene: `instruction_md` nicht leer; `criteria` max. 10 nicht‑leere Strings; `due_at` mit Zeitzone (auch `…Z`); `max_attempts ≥ 1`.

## Learning (Lernen) — Security Notes

- SECURITY DEFINER Helper
  - Alle in `public.*` definierten SECURITY‑DEFINER‑Funktionen nutzen einen gehärteten `search_path` (`pg_catalog, public`).
  - Alle Tabellen/Views werden in SQL‑Bodies vollqualifiziert (`public.<tabelle>`), um Schema‑Hijacking zu verhindern.
  - Grants: Ausführung ist für die App‑Rolle `gustav_limited` erlaubt; RLS bleibt aktiv, wenn Funktionen SELECTs auf RLS‑Tabellen vermeiden und stattdessen Ownership in der Funktion selbst prüfen.

- DSN & RLS
  - Runtime (app): ausschließlich Limited‑Role‑DSN (`gustav_limited`), siehe `backend/learning/repo_db.py` (DSN‑Auflösung priorisiert `LEARNING_DATABASE_URL`).
  - Tests/Dev: Fallback‑DSNs greifen auf `127.0.0.1:54322` (Supabase CLI) zurück, damit RLS‑Pfad getestet wird.

### Practice

Practice-Daten sind lernenden-, kurs- und aufgabengebunden:

- `public.learning_practice_states` speichert den versionierten Wiederholungszustand je Lernendem und Aufgabe.
- `public.learning_practice_sessions` stellt höchstens eine aktive Sitzung je Lernendem sicher.
- `public.learning_practice_session_stacks` und `public.learning_practice_session_items` frieren die Auswahl einer Sitzung als nachvollziehbaren Snapshot ein.
- `public.learning_practice_attempts` protokolliert einzelne native oder H5P-Versuche und deren fachliche Einstufung.

Der Scheduler-Vertrag ist versioniert (`gustav-practice-v1`). Musterlösungen und Auswertungsdetails dürfen nur über berechtigungsgeprüfte Helper beziehungsweise Endpunkte gelesen werden.
