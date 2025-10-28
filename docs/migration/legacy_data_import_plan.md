# Legacy → Alpha2 Data Migration Plan

## Zielsetzung
Schrittweise Migration der produktiven Daten aus der Legacy-Supabase in das neue Alpha2-Schema, wobei:
- Nutzerkonten nach Keycloak übertragen und den neuen Domain-IDs zugeordnet werden.
- Kurs-, Inhalts- und Einreichungsdaten maximal verlustfrei übernommen werden.
- Mastery-spezifische Artefakte (Wissensfestiger) sowie die alte Submission-Queue bewusst verworfen werden.

## Rahmenbedingungen
- **Primär-Lehrer je Kurs:** Mehrfach-Zuordnungen werden nicht übernommen; der Legacy-`creator_id` bestimmt den Owner.
- **Mastery-Daten:** Tabellen wie `mastery_tasks`, `student_mastery_progress`, `mastery_log`, `user_model_weights` werden nicht migriert.
- **Datei-Materialien:** Falls keine echten Metadaten vorliegen, werden Dateien als Markdown-Link importiert oder – wenn zugreifbar – beim Import gehasht.
- **Feedback-Queue:** Spalten zur asynchronen Verarbeitung in `submission` werden ignoriert; Feedbacksystem wird in Alpha2 neu implementiert.

## Migrationsschritte
1. **Identity Mapping vorbereiten**
   - Legacy-Keycloak Import (`backend/tools/legacy_user_import.py`).
   - Zwischentabelle `legacy_user_map(legacy_id uuid primary key, sub text unique)` anlegen.
   - Konsistenzprüfung: jede Legacy-ID besitzt genau ein neues `sub`.

   Hinweise:
   - Import mit Service-/Postgres-Role (RLS-Bypass) oder alternativ pro Batch `set local app.current_sub` setzen, falls Policies benötigt werden. Für reine Bulk-Imports bevorzugt: Service-Role.
   - Zeitzonen konsequent in UTC normalisieren (Ein-/Ausgangszeiten).

2. **Kurse & Mitgliedschaften**
   - `course` → `public.courses` (Titel, ggf. Beschreibung → `context_notes` später, `creator_id` via Mapping nach `teacher_id`).
   - `course_student` → `public.course_memberships` (`student_id` über Mapping ersetzen, `created_at` übernehmen).
   - `course_teacher` verwerfen (nur Logging für späteres Review).

   Hinweise:
   - Legacy-UUIDs der Kurse können als `id` beibehalten werden (Explizit-ID-Insert), um Nachvollziehbarkeit zu sichern.

3. **Lerneinheiten & Kursmodule**
   - `learning_unit` → `public.units` (`description` → `summary`, `creator_id` mappen).
   - `course_learning_unit_assignment` → `public.course_modules`; pro Kurs Positionswerte 1..n vergeben, `context_notes` leer lassen.

   Hinweise:
   - Legacy-UUIDs der `learning_unit` können als `units.id` übernommen werden.
   - `course_modules.id` wird neu erzeugt; Zugriff für Releases erfolgt über `(course_id, unit_id)` Lookup nach Insert.

4. **Abschnitte & Freigaben**
   - `unit_section` → `public.unit_sections` (`order_in_unit` → `position`).
   - `course_unit_section_status` → `public.module_section_releases` (nur veröffentlichte Datensätze; `visible = true`, `released_at` übernehmen).

   Hinweise & Regeln:
   - `released_by` ist in Alpha2 NOT NULL. Regel: Wenn Legacy-Veröffentlicher bestimmbar (z. B. Kurs-Owner), dann dessen `sub` setzen; sonst fallback `released_by = 'system'` (konform mit bestehender Backfill-Migration).
   - `unit_sections.id` kann aus Legacy übernommen werden. Achte auf Konsistenz `unit_id` ↔ Abschnitt.

5. **Materialien**
   - Legacy-JSON-Einträge pro Abschnitt transformieren.
     - Markdown-Inhalte → `public.unit_materials` (`kind = 'markdown'`, `body_md`).
     - Dateien/Links: wenn tatsächlicher Zugriff möglich → Datei herunterladen, `size_bytes` und `sha256` berechnen, `kind = 'file'`. Ansonsten als Markdown-Link importieren.
   - Optional: fehlende `title` aus Legacy-Struktur ableiten (Fallback auf Dateiname oder Platzhalter).

   Hinweise:
   - Alpha2-Constraint erzwingt vollständige Datei-Metadaten. Wenn kein Storage-Zugriff existiert, Fallback auf Markdown-Link (`kind='markdown'`) wählen, um Constraint-Verletzungen zu vermeiden.
   - Alternative: separater `legacy_blobs`-Bucket oder Staging-Tabelle zur späteren Nachpflege realer Blobs/Hashes.

6. **Aufgaben**
   - `task_base` + `regular_tasks` → `public.unit_tasks`.
     - `instruction` → `instruction_md`.
     - `assessment_criteria` JSON in Textarray (`criteria`) umwandeln.
     - `solution_hints` → `hints_md`, `max_attempts` übernehmen.
     - `order_in_section` → `position`.
   - `mastery_tasks` auslassen (nur Logging).

   Hinweise & Normalisierung:
   - `unit_tasks` benötigt konsistente `unit_id`/`section_id`: `unit_id` aus dem Abschnitt (`unit_sections.unit_id`) übernehmen; DB-Trigger erzwingt dies.
   - `criteria` in Alpha2: max. 10 Einträge, keine leeren Strings. Vor dem Insert trimmen, leere entfernen, deduplizieren, ggf. auf 10 begrenzen.

7. **Einreichungen**
   - `submission` → `public.learning_submissions`.
     - `student_id`, `task_id`, `course_id` via Mapping.
     - `solution_data` aufspalten: Textantwort → `text_body`; Datei → `storage_key` (nur wenn migrierbar, sonst Datensatz weglassen oder als Textnotiz übernehmen).
     - `attempt_number` → `attempt_nr`, `ai_feedback` → `feedback_md`.
     - Queue-bezogene Felder (Status, Retry) ignorieren.

   Ableitungsregel `course_id` (Legacy kennt dies nicht direkt):
   1) Ermittle die `unit_id` der Aufgabe (über Abschnitt). 2) Kandidatenkurse sind alle Kurse, in denen der Schüler Mitglied ist und deren `course_modules` die `unit_id` enthalten. 3) Wenn mehrere Kandidaten: bevorzuge Kurs, in dem die zugehörige Abschnittsfreigabe (`module_section_releases.visible = true`) zum Zeitpunkt `submitted_at` aktiv war; sonst den frühesten `courses.created_at`. 4) Wenn kein Kurs ermittelbar: Datensatz auslassen und protokollieren.
   - Import mit Service-Role umgeht RLS; optionaler Logik-Check: `public.check_task_visible_to_student()` zur Plausibilitätsprüfung verwenden.
   - Falls `attempt_number` fehlt: aus Chronologie pro (student, task) aufsteigend ableiten.

8. **Nachbereitung & Validierung**
   - Nach jedem Block referentielle Integrität prüfen (`select count(*)` auf verwaiste FKs).
   - Stichproben pro Kurs/Einheit vergleichen (Legacy vs. Alpha2).
   - Abschlussbericht mit Kennzahlen (z. B. importierte Kurse, ausgelassene Mastery-Aufgaben, Anzahl verworfener Datei-Materialien).

## Technik- und Betriebsleitlinien
- Transaktionen: pro Tabelle/Batch in 1–5k Zeilen; bei Reorder-Operationen `SET CONSTRAINTS ALL DEFERRED` nutzen (deferrable unique auf Positionen), um Kollisionen zu vermeiden.
- Idempotenz: Inserts so gestalten, dass ein Wiederanlauf möglich ist (z. B. ON CONFLICT DO NOTHING/UPDATE; dedizierte Mapping-/Staging-Tabellen). Fortschritt pro Schritt protokollieren.
- Performance: Batch-Insert (COPY oder Mehrfachwerte), Indizes beibehalten; bei sehr großen Datenmengen ggf. temporär Sekundärindizes deaktivieren und danach neu erstellen.
- Zeitstempel: Eingehende Zeiten in UTC normalisieren; wenn nicht vorhanden, aus Kontext ableiten oder auf `created_at` zurückfallen.
- IDs: Wo möglich Legacy-UUIDs beibehalten (units, unit_sections, tasks); andernfalls Mapping ableiten (z. B. `course_modules` via `(course_id, unit_id)` Lookup).

## Ergänzungen aus kritischer Reflektion

### Deterministischer Resolver für `submission.course_id`
- Eingabe: `student_id (legacy)`, `task_id (legacy)`, `submitted_at` (optional), abgeleiteter `section_id`/`unit_id`.
- Schrittfolge:
  1) Bestimme `unit_id` via `task → section → unit` Mapping.
  2) Kandidaten sind Kurse, in denen der Schüler Mitglied ist und deren `course_modules` die `unit_id` enthalten.
  3) Wenn mehrere Kandidaten: priorisiere den Kurs, in dem die zugehörige Abschnittsfreigabe zur Zeit `submitted_at` sichtbar war; sonst den Kurs mit frühestem `courses.created_at`.
  4) Keine Kandidaten: Submission nicht importieren, in Audit loggen.
- Ergebnis: eindeutige `course_id` oder dokumentierter Skip.

### Provenienz & Auditing
- Keine Vermischung von Import-Metadaten in Domänentabellen. Stattdessen dedizierte Audit-Struktur (Vorschlag):
  - `import_audit_runs(id uuid pk, source text, started_at_utc, ended_at_utc, notes)`
  - `import_audit_mappings(run_id uuid, entity text, legacy_id text, target_table text, target_id text, status text, reason text, created_at_utc)`
  - `legacy_user_map(legacy_id uuid pk, sub text unique)` (bereits vorgesehen)
- Pro Datensatz: Importstatus (ok/skip/conflict), Grund (mehrdeutig, fehlender Kurs, fehlender Blob), optional Checksummen/Counts.

### Datenqualität & Normalisierung
- Zentrale Helper im ETL:
  - `normalize_text`: trim, collapse whitespace, leere Strings zu NULL.
  - `normalize_title`: Fallback auf sinnvolle Platzhalter (z. B. Dateiname ohne Endung).
  - `normalize_criteria`: trim + dedupe + max. 10 Einträge, leere verwerfen.
  - `bound_length`: optionale Längenlimits (Dokumentation der abgeschnittenen Felder in Audit).

### Dateien & Fallbacks
- Priorität: echte Metadaten generieren (Download → `sha256`, `size_bytes`) und `kind='file'` setzen.
- Kein Zugriff: Fallback `kind='markdown'` mit Link; Audit-Eintrag mit Kennzeichnung "blob_missing" und Ziel-URL.
- Optional: `legacy_blobs`-Bucket/Staging für spätere Backfills; eigener Job, der Links auflöst und Metadaten ergänzt.

### Betrieb & Runbook
- Dry-Run: jeder Schritt mit `--dry-run` ausführbar (nur Zählungen, keine Writes), Report als JSON.
- Resume/Retry: Idempotente Upserts, Fortschritt pro Entität in `import_audit_runs` vermerken.
- Rollback: Import in Staging-Tabellen mit anschließender Switch-Operation (wo praktikabel) oder transaktionsbasiert pro Batch.
- Downtime: Falls erforderlich, nur für schreibende Teile; lesende Altumgebung parallel betreiben. Post-Import `ANALYZE` betroffene Tabellen.

### Observability & Sicherheit
- Strukturierte Logs (JSON) mit Countern: `courses_imported`, `units_imported`, `materials_as_links`, `submissions_skipped`, …
- Fehlerkategorien: `ambiguous_course`, `missing_course`, `blob_missing`, `constraint_violation`, `policy_denied`.
- PII-Schutz: E-Mails/Name maskieren in Logs/Reports (z. B. `m***@example.com`), vollständige PII nur in Audit-Tabellen mit Service-Role-Zugriff.



## Offene Punkte / TODO
- Prüfen, ob Legacy-Storage erreichbar ist, um echte Datei-Metadaten zu generieren.
- Definieren, wie `solution_data`-Einreichungen mit komplexen Strukturen (z. B. mehrere Anhänge) in Alpha2 abgebildet werden sollen.
- Skripte modular implementieren (z. B. Python + SQL) und lokal gegen Test-DB validieren, bevor sie auf Produktionsdaten laufen.

## Review / Analyse (Kurzreport)

Dieser Abschnitt fasst den Migrationsansatz zusammen, benennt Risiken/Fehlerquellen und listet Daten auf, die voraussichtlich nicht oder nur degradiert migrierbar sind. Er dient als Referenz für Dry-Run, Audit und Go/No‑Go‑Entscheidungen.

### 1) Wie funktioniert die Migration (Ablauf)
- Identitäten mappen
  - Legacy‑User werden in Keycloak übernommen; eine Mapping‑Tabelle `legacy_user_map(legacy_id, sub)` ordnet Legacy‑UUID → OIDC `sub` zu (Service‑/Postgres‑Role für Bulk, Zeiten in UTC).
- Kurse und Mitgliedschaften
  - `course` → `public.courses` (Owner via `creator_id` → `teacher_id`).
  - `course_student` → `public.course_memberships`; `course_teacher` wird verworfen (nur Log/Audit).
- Lerneinheiten und Module
  - `learning_unit` → `public.units` (description → summary; author über Mapping).
  - `course_learning_unit_assignment` → `public.course_modules` mit Positionen 1..n je Kurs.
- Abschnitte und Freigaben
  - `unit_section` → `public.unit_sections` (order_in_unit → position).
  - `course_unit_section_status` → `public.module_section_releases` (nur veröffentlichte; `released_at` übernehmen, `released_by` setzen bzw. Fallback `'system'`).
- Materialien
  - Pro Abschnitt Legacy‑JSON transformieren: Markdown → `unit_materials(kind='markdown')`.
  - Dateien: wenn Storage zugreifbar → Download, `size_bytes` und `sha256` berechnen, `kind='file'`; sonst als Markdown‑Link importieren (Constraint‑sicher).
- Aufgaben
  - `task_base` + `regular_tasks` → `public.unit_tasks` (instruction → `instruction_md`, criteria(JSON) → `text[]`, hints, `max_attempts`, `position`).
  - `unit_id` wird aus Abschnitt erzwungen (Trigger/Checks), Positionen je Section.
- Einreichungen
  - `submission` → `public.learning_submissions`: Text → `kind='text', text_body`; Bild → `kind='image'` mit Storage‑Metadaten/Hash.
  - `course_id` deterministisch ableiten über Mitgliedschaft, Modul, Release und Zeitpunkte; bei Ambiguität/Fehler Skip + Audit.
  - `attempt_nr` pro `(course_id, task_id, student_sub)` aus Historie ableiten (bzw. Helper nutzen).
- Betrieb/Runbook
  - Batchweise (1–5k), idempotent (ON CONFLICT), optionale DEFERRABLE‑Constraints bei Reorder, Dry‑Run + Audit‑Zählungen, PII‑Masking.

Relevante Migrationsdateien (Beispiele):
- Materialien/Dateien: `supabase/migrations/20251022093725_teaching_materials_file_support.sql`, `supabase/migrations/20251022112541_strengthen_sha256_check.sql`
- Abschnitte/Freigaben: `supabase/migrations/20251022135746_teaching_module_section_releases.sql`, `supabase/migrations/20251022145331_teaching_module_section_releases_released_by_not_null.sql`
- Aufgaben: `supabase/migrations/20251023061402_teaching_unit_tasks.sql`
- Einreichungen: `supabase/migrations/20251023093409_learning_submissions.sql`, `supabase/migrations/20251023120751_learning_submissions_constraints.sql`, Helper `supabase/migrations/20251023093417_learning_helpers.sql`

### 2) Mögliche Probleme / Risiken
- Identitäts‑Mapping
  - Fehlende/mehrdeutige User‑Zuordnung (Legacy‑ID ohne neues `sub`) verhindert Owner‑Felder und verursacht FK/RLS‑Konflikte.
- Strenge Constraints im neuen Schema
  - `unit_materials(kind='file')` verlangt vollständige Metadaten und hex‑`sha256` per Regex; ohne Storage‑Zugriff schlägt Insert fehl → Fallback als Markdown‑Link notwendig.
  - `unit_tasks` erzwingt konsistentes `(unit_id, section_id)` und eindeutige Positionen je Section (DEFERRABLE). Doppelte/fehlerhafte Positionswerte aus Legacy erfordern Re‑Sequenzierung.
  - `module_section_releases.released_by` ist NOT NULL; fehlende Historie erfordert Fallback `'system'`.
  - `learning_submissions`: `kind`‑spezifische Exklusivität; Bilder nur JPEG/PNG, positive Größe, `sha256` Regex. Andere Formate (HEIC/GIF/WebP) oder fehlende Hashes → Verstoß.
- Kursableitung für Submissions
  - Mehrdeutige Zuordnung bei mehreren Kursen mit derselben Unit; es braucht den Resolver (Release‑Zeitpunkt bevorzugen). Fehlen Zeitstempel/Release‑Daten → Skip.
- Orphans/Referenzen
  - Legacy‑Datensätze mit fehlenden Eltern (z. B. Task ohne Section) → FK‑Verletzung → Skip mit Audit.
- RLS/DSN
  - Import mit Limited‑Role triggert RLS und bricht Bulk/Idempotenz; Bulk‑Imports mit Service‑Role durchführen.
- Performance/Idempotenz
  - Einzel‑Inserts/ohne Upsert sind langsam/anfällig; Batching/COPY und ON CONFLICT nutzen.
- Zeit/Zeitzonen
  - Nicht‑normalisierte Zeiten verfälschen Kursableitung (Release‑Timing); alles in UTC normalisieren.
- Datenqualität
  - `criteria`: Leereinträge/mehr als 10 → Check‑Verstöße; vor Insert trimmen, deduplizieren, cap 10.

### 3) Nicht oder nur degradiert migrierbare Daten
- Mastery & verwandte Tabellen
  - `mastery_tasks`, `student_mastery_progress`, `mastery_log`, `user_model_weights` werden nicht migriert (bewusste Entscheidung).
- Submission‑Queue‑Artefakte
  - Alte Queue‑Felder (Status/Retry) werden verworfen; nur Inhalt/Feedback, falls vorhanden, bleibt.
- Mehrfach‑Lehrer‑Zuordnungen
  - `course_teacher` entfällt; nur Primär‑Owner (Legacy `creator_id`).
- Unauflösbare Identitäten/Kontexte
  - Datensätze ohne eindeutiges Mapping (Owner/Student), ohne referenzierbare Eltern (Unit/Section/Task) oder ohne eindeutige Kursableitung bei Submissions → Skip + Audit.
- Datei‑Blobs ohne Zugriff
  - Materialien/Einreichungen ohne erreichbare Blobs oder ohne Hash/Größe: Materialien als Markdown‑Link (Fallback) oder Submissions (Bild) → Skip.
- Komplexe `solution_data`
  - Mehrere Anhänge/komplexe Strukturen passen nicht in `kind in ('text','image')` → Konvertierung oder Ausschluss nötig.
- Bildformate jenseits JPEG/PNG
  - Nicht erlaubte Formate sind schema‑inkompatibel → Konvertierung oder Ausschluss.
- Freigabe‑Historie
  - Feine Verlaufsdaten aus Legacy werden zu Zustand + `released_at` verdichtet; detaillierte Historie geht verloren.

### Empfehlungen / Checkliste für den Dry‑Run
- Staging & Dry‑Run
  - Zuerst Staging‑Tabellen und `--dry-run` mit Zählungen; Audit‑Struktur verwenden (`import_audit_runs`, `import_audit_mappings`).
- Deterministischer Resolver
  - `submission.course_id` strikt gemäß Plan implementieren; Ambiguitäten/Fehler mit Codes (`ambiguous_course`, `missing_course`) auditieren.
- Datei‑Strategie
  - Erreichbarkeit des Legacy‑Storage früh klären. Materialien ohne Zugriff als Markdown‑Link; Submissions (Bild) ohne Metadaten skippen; `blob_missing` auditieren.
- Normalisierung vor Inserts
  - `criteria` cleanup (trim, dedupe, max 10), Titel/Text normalisieren, Positionswerte je Section/Modul resequenzieren, Zeiten auf UTC.
- Rollen & Transaktionen
  - Service‑Role für Bulk, Batches à 1–5k, DEFERRABLE nur gezielt DEFERRED setzen, danach `ANALYZE`.
- PII/Logging
  - PII in Logs maskieren; vollständige PII nur in Audit‑Tabellen mit Service‑Role‑Zugriff.

Hinweis: Diese Analyse spiegelt den Stand der Migrationen unter `supabase/migrations/` und der Referenzdokumente unter `docs/references/*` wider und sollte bei Schema‑Änderungen aktualisiert werden.
