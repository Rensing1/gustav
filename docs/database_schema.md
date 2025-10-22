# Database Schema Overview

This document summarizes the production session table introduced for persistent sessions.

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
  - Sessions note: If `SESSIONS_BACKEND=db` is enabled, `public.app_sessions` requires a service-role DSN. Otherwise keep in-memory sessions to avoid service-role in the app.

- RLS policies
  - Policies are defined in `supabase/migrations/20251020154107_teaching_rls_policies.sql`.
  - They rely on `SET LOCAL app.current_sub = '<sub>'` per transaction to identify the acting user.

### `public.unit_materials`

- Purpose: Materialien je Abschnitt. Unterstützt Markdown (`kind = 'markdown'`) und Datei-Materialien (`kind = 'file'`).
- Columns
  - `id uuid` primary key (`default gen_random_uuid()`).
  - `unit_id uuid not null` → `learning_units(id)` (`on delete cascade`) to keep author-level ownership in sync.
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
  - Policies (`unit_materials_select/insert/update/delete_author`) spiegeln die Ownership von `learning_units` wider (`app.current_sub`).
  - Inserts/Updates prüfen via Join auf `unit_sections`, dass nur eigene Abschnitte beschrieben werden.
  - Datei-Metadaten werden nur über Upload-Intents gesetzt (siehe unten).
  - Optionaler Alternativtext (`alt_text`, ≤ 500 Zeichen) kann nachträglich via API-PATCH gepflegt werden, um Barrierefreiheit zu verbessern.

### `public.upload_intents`

- Purpose: Kurzlebige Upload-Intents für Datei-Materialien. Kapselt Presign-Infos und Idempotenz.
- Columns
  - `id uuid` primary key (`default gen_random_uuid()`).
  - `material_id uuid not null` — vorab reservierte Material-ID.
  - `unit_id uuid not null` → `learning_units(id)` (`on delete cascade`).
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
  - `released_by text null` — OIDC `sub` der Lehrkraft, die zuletzt den Status geändert hat.
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
