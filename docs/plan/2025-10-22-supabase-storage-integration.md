# Plan: Supabase Storage Integration (self‑hosted)

Status: draft
Owner: Felix & Team
Date: 2025‑10‑22

## Kontext
- Ziel: Datei‑Uploads für Unterrichtsmaterialien produktionsreif machen (presigned Upload → Finalize → Download/Delete).
- Aktuell: Postgres (Supabase) läuft; Supabase Storage und Studio laufen noch nicht. Backend‑Workflow ist vorhanden (Upload‑Intent/Finalize/Download), Storage‑Adapter fehlt.
- Clean Architecture: Storage bleibt Infrastruktur‑Detail (Adapter), Use‑Cases unverändert.

## User Story
Als Lehrkraft möchte ich Dateien (PDF/Bilder) sicher zu einem Abschnitt hochladen, damit Lernende Materialien sehen können. Die Dateien sollen privat gespeichert werden und nur kurzlebige, signierte URLs erlauben.

Akzeptanzkriterien (Auszug):
- Max 20 MB; MIMEs: application/pdf, image/png, image/jpeg.
- Bucket `materials` privat; kein direkter öffentlicher Zugriff, nur signierte URLs.
- Upload-Intent 3 min gültig; Download-URL 45 s.
- Finalize prüft Größe/MIME via HEAD und lehnt inkonsistente Uploads ab; bei Fehlern wird Storage‑Objekt bereinigt.

## Entscheidungen
- Adapter: `SupabaseStorageAdapter` implementiert `StorageAdapterProtocol` (backend/teaching/storage.py).
- Kein API‑Contract‑Change nötig (api/openapi.yml bleibt stabil).
- ENV‑Konfiguration: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, optional `SUPABASE_STORAGE_BUCKET` (default: materials).
- Supabase Studio: nicht erforderlich für lokale Integration.
- Reverse‑Proxy: Caddy bleibt für die App. Supabase‑eigene Services laufen eigenständig; kein zusätzlicher Kong‑Setup nötig für den ersten Schritt.

## BDD‑Szenarien (Given‑When‑Then)
- Happy Path Upload
  - Given autorisierte Lehrkraft, gültiger Abschnitt
  - When POST Upload‑Intent mit filename/mime/size
  - Then 200 mit presigned URL + headers; TTL ≤ 180 s
- Finalize erfolgreich
  - Given Objekt via presigned URL hochgeladen
  - When POST Finalize mit intent_id/title/sha256
  - Then 201 Material(kind=file), DB gespeichert, keine Orphans
- Finalize: falsche Größe
  - Given Storage HEAD content_length ≠ intent.size_bytes
  - When Finalize
  - Then 400 checksum_mismatch und Storage.delete_object aufgerufen
- Finalize: MIME mit Parametern
  - Given Storage HEAD content_type „application/pdf; charset=UTF-8“
  - When Finalize
  - Then 201 akzeptiert (MIME-Basis stimmt)
- Download URL
  - Given bestehendes File‑Material
  - When GET download-url?disposition=inline
  - Then 200 mit URL + expires_at (≈ 45 s)
- Delete: Upstream‑Fehler
  - Given Storage.delete_object wirft Fehler
  - When DELETE /materials/{id}
  - Then 502 storage_delete_failed, DB‑Zeile bleibt bestehen
- Unauthorisiert/IDs ungültig → 403/400/404 gemäß bestehendem Vertrag

## OpenAPI / Contract
- Ergänzung: Für `upload-intents`, `finalize` und `download-url` ist jetzt `503 service_unavailable` dokumentiert, wenn kein Storage-Adapter konfiguriert ist.
  Das reflektiert die bestehende Laufzeitsemantik (`NullStorageAdapter`). 502 Beispiel bleibt bei DELETE.

## Datenbank / Migration
- Keine SQL‑Schemaänderungen notwendig. Supabase Storage‑Bucket ist außerhalb von Postgres. DB‑Migrationen bleiben unberührt.

## Umsetzungsschritte
1) Supabase Storage lokal aktivieren (ohne Studio)
   - `supabase/config.toml`: `[storage] enabled = true`
   - Bucket definieren:
     - `[storage.buckets.materials]`
     - `public = false`
     - `file_size_limit = "20MiB"`
     - `allowed_mime_types = ["application/pdf","image/png","image/jpeg"]`
     - `objects_path = "./storage/materials"`
   - Start: `supabase stop` → `supabase start -x studio`
   - Prüfen: `supabase status`
2) Adapter implementieren
   - Datei: `backend/teaching/storage_supabase.py`
   - Methoden:
     - `presign_upload(...)` → createSignedUploadUrl
     - `head_object(...)` → stat/list/info (liefert `{content_length, content_type}`)
     - `presign_download(...)` → createSignedUrl mit `content-disposition`
     - `delete_object(...)` → remove
   - Bootstrapping: `set_storage_adapter(SupabaseStorageAdapter(...))` in App‑Init (siehe `backend/web/routes/teaching.py:726`).
3) Tests (TDD)
   - Neuer Test: `backend/tests/test_supabase_storage_adapter.py`
   - Mocks für HTTP‑Aufrufe; Validierung der Rückgabe‑Formate und TTLs.
   - Integration: Vorhandene API‑Tests weiterverwenden (Fake Adapter bleibt für Fehlerpfade). Zusätzliche Tests prüfen `503` bei nicht konfiguriertem Adapter und `Cache-Control: no-store` für Download-URL.
4) Doku
   - `docs/references/storage_and_gateway.md`: Setup, ENV, TTLs, CORS‑Hinweise, Pfad‑Sanitizing.
   - `docs/ARCHITECTURE.md`: Abschnitt „Storage (Supabase) – Prod/Dev“ ergänzen.

## Sicherheit
- Service‑Role‑Key nur im Backend (ENV); niemals im Client.
- Signierte URLs kurzlebig; private Buckets.
- Pfad‑Segmente sanitisiert (bereits im Service umgesetzt). Bucket-Name kann über `SUPABASE_STORAGE_BUCKET` gesetzt werden (default: `materials`).
- Finalize validiert Größe/MIME via HEAD; auf Fehler → Delete, 400.
- Rate‑Limits und Logging auf App‑Ebene; Storage selber bleibt nicht öffentlich exponiert.

## Kong vs Caddy (Gateway)
- Jetzt: Kein zusätzliches Kong erforderlich. Caddy bleibt Reverse‑Proxy vor der App.
- Supabase‑Stack (self‑hosted/CLI) bringt intern ggf. Kong für die Supabase‑Dienste mit – das betrifft nicht den App‑Traffic.
- Später optional: Kong‑Policies (CORS/HSTS/Rate‑Limit) vor App/API, wenn Anforderungen steigen. Nicht Teil dieses Schritts.

## Offene Fragen
- supabase‑py als Abhängigkeit vs. schlanke HTTP‑Calls? (Präferenz: supabase‑py v2, falls stabil verfügbar; sonst HTTP)
- Deploy‑Ziel: Produktion ebenfalls self‑hosted mit gleichem Stack?

## Definition of Done
- Storage lokal läuft (Bucket vorhanden), Adapter eingebunden, API‑Tests grün.
- Ops‑Doku vorhanden; ENV‑Variablen dokumentiert; kein API‑Contract‑Change.
