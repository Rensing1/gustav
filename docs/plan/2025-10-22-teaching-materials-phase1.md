# Plan: Unterrichten – Materialien Phase 1

Goal: Den Unterrichten-Kontext schrittweise um Materialien erweitern. Wir starten mit reinen Markdown-Inhalten (Iteration 1a) und liefern in einem Folgeinkrement Datei-Materialien mit Pre-Signed Uploads (Iteration 1b). Schülerzugriff und Releases bleiben weiterhin Aufgabe des Lernen-Kontexts.

## Scope & Prinzipien
- KISS, Security-first, FOSS; Clean Architecture: Use-Case-Layer bleibt frameworkfrei.
- Contract-First & TDD: OpenAPI-Anpassungen und failing pytest-Tests gehen jeder Implementierung voraus.
- RLS: Alle DB-Zugriffe erfolgen author-gebunden (`app.current_sub`), kein Bypass über Service-DSNs.
- Iteratives Vorgehen: Erst Markdown (Iteration 1a), danach Datei-Uploads (Iteration 1b). Jede Iteration besitzt eigenständige Migrationen und Tests.
- Titelpflicht 1..200 Zeichen; Markdown-Body ohne hartes DB-Limit, aber mit konfigurierbarem Request-Body-Guard (z. B. 1–2 MB).
- Keine Wiederverwendung von Materialien zwischen Abschnitten.

## Liefer-Inkremente

### Iteration 1a — Markdown-Materialien (dieser Sprint)

**User Story**
- Als Lehrkraft möchte ich Textmaterial (Markdown) in einem Abschnitt anlegen, bearbeiten, löschen und in der Reihenfolge verändern, damit ich meine Inhalte strukturiert darstellen kann.

**BDD-Szenarien (Given-When-Then)**
- Happy Path: Autor ruft `GET /materials` auf → 200 mit positionssortierter Liste. `POST` erzeugt Eintrag (`position = next`, Timestamps), `PATCH` aktualisiert Titel/Body, `DELETE` entfernt Eintrag, `reorder` akzeptiert die exakte Permutation.
- Edge Cases: Abschnitt ohne Materialien → `reorder` liefert 400 `section_mismatch`. Löschen resequenziert auf `1..n`. Leer-/zu langer Titel → 400 `invalid_title`.
- Fehlerfälle: Nicht-Autor → 403 `forbidden`; ungültige UUID → 400 `bad_request`; fremde Material-ID in `reorder` → 404 `not_found`.

**API Contract (Auszug)**
- `GET /api/teaching/units/{unit_id}/sections/{section_id}/materials`
- `POST /api/teaching/units/{unit_id}/sections/{section_id}/materials`
- `PATCH /api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}`
- `DELETE /api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}`
- `POST /api/teaching/units/{unit_id}/sections/{section_id}/materials/reorder`

Antworten enthalten `id, section_id, title, body_md, position, created_at, updated_at`. Validierung erfolgt im Handler (400 statt 422).

**Datenbank & Migration**
- Migration `teaching_unit_materials_markdown.sql`
  - `public.unit_materials`
    - `id uuid pk default gen_random_uuid()`
    - `section_id uuid not null` FK → `unit_sections(id)` on delete cascade
    - `title text not null` (1..200)
    - `body_md text not null`
    - `position int not null check (position > 0)`
    - `created_at timestamptz default now()`, `updated_at timestamptz default now()`
    - Unique `unique(section_id, position) DEFERRABLE INITIALLY IMMEDIATE`
    - Index `idx_unit_materials_section(section_id)`
  - Trigger `trg_unit_materials_updated_at`
  - Constraint/Trigger `unit_materials_section_unit_match` validiert, dass `unit_sections.unit_id` zur angefragten Section passt (Guard gegen Cross-Unit-Inserts).
- RLS: Select/Insert/Update/Delete nur, wenn die verknüpfte Unit dem aktuellen Autor gehört (`learning_units.author_id = app.current_sub`).

**Tests (pytest)**
- Neues Modul `backend/tests/test_teaching_materials_markdown_api.py`
  - Authz (401/403), CRUD, Reorder, Resequencing, 400 für invalide Payloads und UUIDs.
  - RLS mit Limited-Role-DSN, `set_config('app.current_sub', ...)` verifiziert.
  - Performance: Liste erzeugt exakt eine DB-Query (kein N+1).
- Ergänzung von Contract-Checks in `test_openapi_teaching_contract.py` für neue Pfade/Schemas.

**Implementation & Architektur**
- Service-Layer `teaching/services/materials.py` kapselt Businesslogik für Markdown (create/update/delete/reorder/list).
- Repo (`backend/teaching/repo_db.py`) erhält Markdown-spezifische Methoden (`create_markdown_material`, `list_materials_for_section_owned`, `update_markdown_material`, `delete_material`, `reorder_section_materials`).
- Webadapter `backend/web/routes/teaching.py` erweitert um Endpunkte; Handler geben strukturierte 400/403/404 zurück.
- Dokumentation: `docs/glossary.md` (Eintrag „Material“ aktualisieren), `docs/database_schema.md` ergänzt Tabelle & Constraints.

### Iteration 1b — Datei-Materialien mit Pre-Signed Uploads (Folgeinkrement)

**User Stories**
- Als Lehrkraft möchte ich Dateien (PDF, Bilder) sicher hochladen und einem Abschnitt zuordnen.
- Als Lehrkraft möchte ich für Datei-Material eine Download-URL erhalten, um die Darstellung zu prüfen.

**Ergänzende BDD-Szenarien**
- Upload-Intent: Author ruft `POST upload-intents` auf → 200 mit kurzlebiger URL, sofern MIME/Größe whitelisted und Ownership stimmt.
- Finalize: Nach Upload sendet Client `POST finalize` mit `sha256`. Server prüft HEAD (Größe, MIME, optional Magic Bytes) und legt Material an. Wiederholter Call → 200 (idempotent).
- Download: Author erhält `GET download-url?disposition=inline|attachment` → 200 mit URL, TTL ≤ 60 s.
- Edge & Fehler: Abgelaufener Intent → 400 `intent_expired`; MIME/Size außerhalb Whitelist → 400; Finalize ohne Objekt → Storage löscht Key, API liefert 400; falscher `sha256` → 400.

**API-Erweiterungen**
- `POST /materials/upload-intents`
  - Body `{ filename, mime_type, size_bytes }`
  - Response `{ intent_id, material_id, storage_key, method, url, headers?, fields?, accepted_mime_types, max_size_bytes, expires_at }`
- `POST /materials/finalize`
  - Body `{ intent_id, title, sha256, alt_text? }`
  - 201 neu, 200 bei Wiederholung (Idempotenz)
- `GET /materials/{material_id}/download-url?disposition=inline|attachment`
- `PATCH` für Datei-Material erlaubt `title`, `alt_text`.

**Supabase Storage Setup (minimal)**
- Dienste: Für Datei-Materialien benötigen wir nur Postgres, das API‑Gateway (Port 54321) und Storage. Andere Services (Auth, Realtime, Studio, Inbucket) sind nicht erforderlich.
- Konfiguration (`supabase/config.toml`):
  - `[api].enabled = true`
  - `[storage].enabled = true`
  - Optional explizit deaktivieren: `[auth].enabled = false`, `[realtime].enabled = false`, `[studio].enabled = false`, `[inbucket].enabled = false`.
- Start: `supabase start` (nicht `db start`), damit Gateway+Storage laufen; deaktivierte Dienste werden nicht gestartet.
- Netzwerkzugriff aus dem App‑Container:
  - Vom Host: `SUPABASE_STORAGE_URL=http://127.0.0.1:54321/storage/v1`.
  - Aus Docker‑Containern: `SUPABASE_STORAGE_URL=http://host.docker.internal:54321/storage/v1` (in `web` bereits per `extra_hosts` gesetzt).
- Bucket‑Provisionierung (privat):
  - Per Migration: `supabase/migrations/..._storage_materials_bucket.sql` mit `insert into storage.buckets ...` (privat, `allowed_mime_types` passend zur API‑Whitelist).
  - Alternativ lokal per CLI: `supabase storage create-bucket materials --public=false`. Für CI/Prod weiterhin via Migration provisionieren.
- Secrets/Keys (nur Server):
  - `SUPABASE_SERVICE_ROLE_KEY` (für Presign/HEAD/Delete im Backend). In `web` via `.env` setzen.
  - Optional: `SUPABASE_JWT_SECRET` falls wir eigene Kurzzeit‑JWTs signieren (später möglich). `SUPABASE_ANON_KEY` wird für diesen Flow nicht benötigt.
- Produktion: Supabase Cloud (mit Storage) oder eigener S3‑kompatibler Dienst; der Adapter kapselt HTTP‑Aufrufe und bleibt austauschbar.

**Datenbank-Erweiterung (zweite Migration)**
- `unit_materials` ergänzen
  - `kind text not null default 'markdown' check (kind in ('markdown','file'))`
  - Datei-Felder: `storage_key text`, `filename_original text`, `mime_type text`, `size_bytes int`, `sha256 text`, `alt_text text`
  - `unique(storage_key)` (nicht null)
  - Update von RLS-Policies: gleiche Ownership-Prüfung, aber `kind`-abhängige Validierungen.
- Neue Tabelle `public.upload_intents`
  - `id uuid pk default gen_random_uuid()`
  - `material_id uuid not null` (geplante Material-ID zur Idempotenz)
  - `author_id text not null`
  - `section_id uuid not null`
  - `storage_key text not null` (Format `materials/{author}/{unit}/{section}/{material_uuid}/{sanitized_filename}`)
  - `filename text not null`, `mime_type text not null`, `size_bytes int not null check (size_bytes > 0)`
  - `expires_at timestamptz not null`, `consumed_at timestamptz null`, `created_at timestamptz default now()`
  - Indizes auf `author_id`, `(section_id, material_id)`
- Löschstrategie: Vorläufig synchron via Storage-Adapter (`delete_object`) bei Material/Section/Unit-Delete. Eine optionale Outbox (`storage_deletions`) wird in einem eigenen Plan eingeführt, sobald ein Background-Worker verfügbar ist.
- RLS: `upload_intents.author_id = app.current_sub`; keine Fremdzugriffe.

**Storage-Adapter Implementierung**
- HTTP-basiert, nutzt Supabase Storage REST API:
  - Presign Upload: `POST {SUPABASE_STORAGE_URL}/object/upload/sign/{bucket}/{key}` mit Service-Role JWT.
  - HEAD/Metadata: `POST /object/info` oder `GET /object/sign/{key}`?`download=1&token=...`? (Wir verwenden `POST /object/info` zum Prüfen von Größe und Content-Type).
  - Delete: `DELETE /object/{bucket}/{key}`.
- JWT-Erstellung: Service-Role Key signiert; Supabase CLI liefert `SUPABASE_JWT_SECRET`. Wir bauen Hilfsfunktion, die Kurzzeit-JWT mit `role = service_role` erstellt (analog existierender Auth-Code).
- Bucket-Namespace fest verdrahtet (`materials`); Helper stellt sicher, dass Keys `materials/{author}/{unit}/{section}/{material_uuid}/{sanitized_filename}` folgen.
- Für Tests ersetzen wir Adapter durch Stub (kein echter HTTP-Call). Integrationstests optional, sobald Storage-Service auch im CI verfügbar ist.

**Storage-Sicherheit & Guards**
- Private Bucket, kein Listing. Presigned URLs nur serverseitig mit Service-Key, TTL Upload 3–5 min, Download 30–60 s.
- Policy Conditions: exakter `storage_key`, `content-length-range`, `content-type` Whitelist (pdf, png, jpg, jpeg). Keine ACL Felder.
- Serverseitige Checks: `sha256` Pflicht; HEAD-Vergleich (Größe, MIME); optional Magic-Byte-Validierung.
- Dateinamen werden sanitisiert (ASCII-Slug + suffix). Originalname wird im DTO gespeichert (`filename_original`).
- Logging & Rate-Limiting für Upload-Intents/Finalizes.

**Tests Iteration 1b**
- Neues Modul `backend/tests/test_teaching_materials_files_api.py`
  - Upload-Intent Guards (Ownership, MIME, Size, TTL).
  - Finalize (Happy Path, Idempotenz, abgelaufener Intent, HEAD/SHA mismatch → 400 + `delete_object`).
  - Download-URL TTL, Disposition, Author-Only.
  - Delete Material → ruft synchron `delete_object`; Delete Section/Unit → Adapter erhält für jede Datei einen Call.
- Storage-Adapter Mock kontrolliert Presign-Parameter (Key, Conditions). Integrationstests mit echtem Bucket bleiben optional.
- Reuse bereits vorhandener Markdown-Reorder- und RLS-Tests; Ergänzung für `kind`-Validierung.

**Manuelle Verifikation nach Setup**
- `supabase status` prüfen → Storage-Service läuft.
- `supabase storage list-buckets` → Bucket `materials` existiert.
- `curl -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" http://127.0.0.1:54321/storage/v1/bucket/materials` → 200 (Smoke-Test).
- Upload-Flow end-to-end ausprobieren (Intent → curl Upload → Finalize) bevor Implementierung live geht.

**Implementation & Architektur (Iteration 1b)**
- Service erweitert um Datei-spezifische Use Cases (Presign, Finalize, Delete). Markdown-Code bleibt unverändert.
- Repo behandelt `material_id` vorab (geplanter UUID), verwaltet `upload_intents` und Idempotenz (`consumed_at`, `unique(storage_key)`).
- Storage-Adapter Interface: `presign_upload`, `presign_download`, `head_object`, `delete_object`.
- Dokumentation: `docs/database_schema.md` und `docs/references/teaching.md` um Upload-/Download-Flows und Sicherheitsmaßnahmen erweitern.
- Cleanup: Periodisches Script (z. B. CLI-Command) löscht abgelaufene Intents/Dateien; echte Outbox erst mit dediziertem Worker.

## Sicherheits- und Datenschutznotizen
- Materials API bleibt Teacher-only; Schülerzugriff folgt im Lernen-Kontext mit Release-Checks.
- RLS-Policies verhindern Cross-Section/Unit-Zugriffe. Tests decken 403/404-Pfade ab.
- Presigned URLs sind kurzlebig und streng gebunden an exakt einen Objekt-Key; Credentials verlassen nie das Backend.
- Request-Body-Guards schützen vor DoS bei großen Markdown-Uploads; Grenzen sind konfigurierbar.
- Audit-Logging: Upload-Intent/Finalize-Aufrufe werden protokolliert (sub, timestamp, section_id, storage_key).

## Open Questions
- Virenscan: wann/wie einbinden (synchroner Scan vs. asynchroner Worker)?
- Dateinamen-Sanitizing: konkrete Regeln/Bibliothek (z. B. python-slugify) abstimmen.
- Maximalgrößen & Quotas: Produktentscheidung (Initial 20 MB?) und wo konfiguriert.
- Cleanup-Jobs: Frequenz und Verantwortlichkeit (Cron, Supabase Edge Function, Worker?).

## Next Steps
1. Iteration 1a vorbereiten: OpenAPI anpassen, Migration `teaching_unit_materials_markdown.sql` erzeugen, failing Tests `test_teaching_materials_markdown_api.py` schreiben, minimal implementieren, Dokumentation aktualisieren.
2. Nach Abschluss: Review & Lessons Learned. Folgeplan für Iteration 1b finalisieren (inkl. eventuell separatem Plan-Dokument), dann OpenAPI/Migration/Tests für Datei-Uploads entwerfen.
