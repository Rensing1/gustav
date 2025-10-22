# Plan: Unterrichten – Materialien Iteration 1b (Datei-Uploads)

Goal: Dateibasierte Materialien mit Presigned Uploads einführen, ergänzend zu den bereits ausgelieferten Markdown-Materialien aus Iteration 1a.

## Scope & Constraints
- KISS, Security-first, FOSS; Use-Case-Layer frameworkfrei.
- Contract-first & TDD: OpenAPI und failing Tests zuerst.
- RLS strikt über `app.current_sub`; keine Service-DSN-Bypässe.
- Erweiterung baut auf existierenden Markdown-Materialien auf (`kind = 'markdown'`).
- Unterstützte Dateitypen initial: `application/pdf`, `image/png`, `image/jpeg`.
- Maximalgröße (Produktentscheidung offen, Default 20 MB) als konfigurierbare Grenze.
- Schülerzugriff weiterhin außerhalb des Scopes (Lernen-Kontext).
- Lessons Learned 1a: Guard-Order vor Payload-Validierung, konsistente JSON-Responses, deferrable Constraints bei Reorder, vollständige RLS-Tests.
- Ergänzend (Iteration 1b): Dateinamen-Sanitizing früh festlegen (z. B. `python-slugify`), Presign-TTL und Größenlimits zentral konfigurieren und validieren.

## User Stories
- Als Lehrkraft möchte ich eine Datei sicher hochladen und einem Abschnitt zuordnen, um Materialien in verschiedenen Formaten bereitzustellen.
- Als Lehrkraft möchte ich eine Download-URL für Datei-Material erhalten, um das Ergebnis zu prüfen oder weiterzugeben.

## BDD-Szenarien
### Upload Intent
- Given eine autorisierte Lehrkraft und eine gültige Datei-Metadaten-Payload
  When sie `POST /materials/upload-intents` aufruft
  Then erhält sie 200 mit Presign-URL, notwendigen HTTP-Headern und Ablaufzeit (≤ konfiguriertem Limit).
- Edge: Dateityp nicht erlaubt → 400 `mime_not_allowed`.
- Edge: Größe > Limit → 400 `size_exceeded`.
- Fehler: Nicht-Autor → 403 `forbidden`.

### Finalize
- Given ein zuvor erzeugter Intent und erfolgreicher Upload
  When Lehrkraft `POST /materials/finalize` mit `sha256`, `title` sendet
  Then erzeugt das System ein Material (`kind = file`), setzt Metadaten und gibt 201.
- Edge: Wiederholter Finalize → 200 mit bestehendem Material.
- Fehler: Intent abgelaufen → 400 `intent_expired` (Storage-Key wird bereinigt, Retry möglich solange Intent nicht konsumiert ist).
- Fehler: `sha256`-Mismatch → 400 `checksum_mismatch` + Delete im Storage (Retry nach neuem Upload erlaubt).
- Sicherheits-Guard: Intent muss zur Session/Lehrkraft gehören; Replay aus anderer Session → 403 `forbidden`.

### Download URL
- Given ein Datei-Material, das der Lehrkraft gehört
  When sie `GET /materials/{material_id}/download-url?disposition=inline`
  Then erhält sie 200 mit kurzlebiger URL.
- Edge: `disposition` außerhalb `inline|attachment` → 400 `invalid_disposition`.
- Fehler: Nicht-Autor oder Material unbekannt → 403/404.

### Deletion & Cleanup
- Given ein Datei-Material im Abschnitt
  When Lehrkraft `DELETE` auf das Material sendet oder den Abschnitt löscht
  Then Storage-Objekt wird synchron gelöscht.
- Fehler: Storage-Delete schlägt fehl → 502 `storage_delete_failed` (Planung für spätere Outbox notwendig).

## API Contract (Entwurf)
- `POST /api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents`
  - Request `{ filename: string, mime_type: string, size_bytes: int }`
  - Response 200 `{ intent_id, material_id, storage_key, url, headers, accepted_mime_types, max_size_bytes, expires_at }`
- `POST /api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize`
  - Request `{ intent_id: uuid, title: string, sha256: string, alt_text?: string }`
  - Response 201 (new material) / 200 (existing)
- `GET /api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url`
  - Query `disposition=inline|attachment`
  - Response 200 `{ url, expires_at }`
- `PATCH` Datei-Material erlaubt `title`, `alt_text`.
- Fehler-Ressourcen spiegeln neue Detailcodes (`mime_not_allowed`, `size_exceeded`, `intent_expired`, `checksum_mismatch`, `invalid_disposition`, `storage_delete_failed`).

OpenAPI-Erweiterungen werden als separater Abschnitt in `api/openapi.yml` ergänzt; bestehende `Material`-Schema erhält `kind`, Datei-Metadaten und optionales `alt_text`.

## Datenbank- & Storage-Migration
- Erweiterung `public.unit_materials`:
  - Spalten: `kind text not null default 'markdown' check kind in ('markdown','file')`,
    `storage_key text`, `filename_original text`, `mime_type text`, `size_bytes integer`, `sha256 text`, `alt_text text`.
- Constraint: `unique(storage_key)` (`where storage_key is not null`).
- Trigger/Check stellt sicher, dass Markdown-Materialien keine File-Felder setzen und Datei-Materialien alle Pflichtfelder besitzen.
- Neue Tabelle `public.upload_intents` mit RLS (`author_id = app.current_sub`) und Constraint, dass ein Intent nur vom angelegten Autor konsumiert werden kann.
- Adoption einer Sanitizing-Hilfe (z. B. `python-slugify`) für `filename`; Eingaben auf ASCII/Whitelist begrenzen.
- Migration legt privaten Storage-Bucket `materials` an (wenn noch nicht vorhanden).
- Deferrable Constraints bleiben aktiv; Reorder unverändert.

## Tests (Pytest)
- Neues Modul `backend/tests/test_teaching_materials_files_api.py`:
  - Upload Intent: Happy Path (Response enthält nur `url` + `headers`, `expires_at` ≤ konfiguriertem Limit) + MIME/Size-Guards + 403 Nicht-Autor + 400 für ungültige UUIDs.
  - Finalize: Happy Path (Material entsteht), idempotent, Intent abgelaufen, SHA-Mismatch (Storage-Delete wird erwartet), Intent gehört anderem Autor oder fremder Session → 403.
  - Download URL: Happy Path mit `inline/attachment`, invalid disposition, Nicht-Autor.
  - Delete Material: Storage-Delete wird auf Mock-Adapter erwartet, ebenso bei Section/Unit-Delete; Fehlerpfad `storage_delete_failed` liefert 502 und Logging-Hinweis.
  - Storage-Adapter Mocks decken Presign-Parameter und HEAD-Validierung ab.
- Contract-Tests (`backend/tests/test_openapi_teaching_contract.py`) ergänzen neue Pfade/Schemas/Examples.

## Implementation Outline
- Service `MaterialsService` erweitert um Datei-spezifische Methoden (`create_upload_intent`, `finalize_file_material`, `presign_download`, `delete_file_material`).
- Repository `DBTeachingRepo` implementiert Upload-Intent-Verwaltung, Materialerstellung mit vorab reservierten IDs und Storage-Key-Generierung.
- Utility-Funktion `sanitize_filename` (Slugify) stellt sichere Keys (`ASCII`, kein Path-Traversal) bereit und wird von Service/Repo gemeinsam verwendet.
- Storage-Adapter Interface (neues Modul `backend/teaching/storage.py`): `presign_upload`, `head_object`, `delete_object`, `presign_download`. Adapter kapselt Retries (z. B. drei Versuche) und protokolliert Fehler.
- Web-Routen in `backend/web/routes/teaching.py` fügen neue Endpunkte hinzu, setzen Guard-Order (Autorprüfung vor Validierung).
- Konfiguration (`config.py`/Settings) erhält Limits (`MAX_MATERIAL_FILE_SIZE`), MIME-Whitelist, Presign-TTL (maximal fünf Minuten), Retry-Anzahl und Logging-Level; Settings in Tests zentral injizierbar.
- Beobachtbarkeit: Logging für alle Fehlerpfade (`storage_delete_failed`, `checksum_mismatch`) und optional Metrics-Hooks vorbereiten.
- Dokumentation: `docs/database_schema.md`, `docs/glossary.md` (Material `kind`), evtl. `docs/references/teaching.md` für Ablaufdiagramm.

## Lessons Learned Reflektion (Iteration 1a)
- Validierungs-Guards vor Payload-Parsing platzieren, um Fehler-Orakel zu vermeiden.
- Alle neuen Endpunkte liefern `JSONResponse` mit explizitem Statuscode.
- Reorder- und Ownership-Checks wiederholen, um keine RLS-Lücken zu erzeugen.
- Tests früh mit realer DB durchspielen (Fixture `require_db_or_skip` nutzen).
- Dateiname früh sanitizen (Slugify) und Presign-Responses minimal halten (nur benötigte Felder `url`, `headers`).

## Review Follow-ups (Oktober 2025)
- `Material`-Contract zeigt `alt_text` und Datei-Metadaten auch für Updates an. PATCH-Payload, Service und Repo müssen `alt_text` lesen/schreiben (inkl. Validierung und Tests).
- Storage-Key benötigt robuste Sanitizing-Regel für _alle_ Pfadkomponenten (Autor, Unit, Section, Material, Dateiname), damit kein Filesystem-Backend Path Traversal zulässt.
- In-Memory-Repo `_Repo` implementiert Dateiwege nicht komplett; ergänzende Methoden für Upload Intent/Finalize/Download/Delete werden benötigt, damit Dev-Server ohne DB weiter funktioniert.
- OpenAPI-Beispiele müssen alle real möglichen Detailcodes (`invalid_filename`, `mime_not_allowed`, `size_exceeded`, `intent_expired`, `checksum_mismatch`, `invalid_disposition`, `storage_delete_failed`) aufführen.
- Tests erweitern (Upload Intent Validation inkl. `invalid_filename`, Größe über Limit, MIME in Großschreibung, Intent-Ablauf) und Alt-Text-Update (Contract-Test + API-Test) hinzufügen.

## Next Steps
- [x] OpenAPI-Snippet und Schema-Erweiterung (mit minimalem Presign-Response) ausarbeiten.
- [x] SQL-Migration `20251022093725_teaching_materials_file_support.sql` entwerfen und ablegen.
- [x] Pytest-Datei für Datei-Materialien schreiben (zunächst failing, inkl. Intent-Ownership- und Retry-Fälle).
- [x] Minimal-Implementierung (Service/Repo/Routes/Adapter-Stub mit Sanitizing & Retries) erstellen.
- [x] Dokumentation aktualisieren und Lessons Learned nachziehen; Logging- & Retry-Strategie dokumentieren.
