# Teststrategie: Supabase Storage

Ziele:
- Korrektheit (Upload/Finalize/Download/Delete), Robustheit, Sicherheit, Idempotenz, Performance.

Ebenen und Abdeckung:
- Unit Adapter (ohne Netzwerk)
  - presign_upload/presign_download: Feldnormalisierung (url/expires_at), Header‑Echo, TTL‑Range.
  - head_object: Mapping size/mimetype (inkl. Parameter), tolerante Fallbacks.
  - delete_object: remove([path]) korrekt, Fehlerpropagation. Disposition inline/attachment.
  - Negative: unerwartete Client‑Formate → RuntimeError.
- Contract Adapter (Mock‑HTTP)
  - Feldnamens‑Varianten (signed_url|url, data‑Wrapper). Fehlende expires_at → Service‑Fallback.
  - Fehler‑Mapping: 4xx/5xx → Exceptions (API mappt zu 503, falls konfiguriert).
- Service Layer
  - Sanitizing von Dateinamen/Segmenten (Unicode, Leerstrings; keine Traversal). MIME/Size/TTL‑Checks.
  - SHA256‑Pattern. Finalize: size≠intent.size → delete + 400; MIME mit Parametern akzeptiert.
  - Download: disposition inline/attachment; ungültig → 400. Fehlendes expires_at → server‑seitiger Fallback.
- Repository/DB
  - Intent‑Lebenszyklus, Unique‑Constraints (material_id, storage_key), consumed_at, RLS/Ownership, atomare Finalize.
- API (FastAPI)
  - Upload‑Intent → Finalize → Download‑URL → Delete, inkl. 502 bei Storage‑Delete‑Fehler (vorhanden, erweitert).
  - Fehlerpfade: Adapter nicht konfiguriert (503), ungültige UUIDs (400), unbekannt (404).
- Integration (lokales Supabase)
  - Markiert (RUN_SUPABASE_E2E=1): echter Upload via signed URL, Finalize, Download, Delete, Privatheit, TTL‑Ablauf.

Implementiert:
- Adapter‑Unit‑Tests: `backend/tests/test_supabase_storage_adapter.py`
- Service‑Fallbacks: `backend/tests/test_materials_service_download_fallback.py`
- API (in‑memory Repo): zusätzliche Fallback‑Fälle in `backend/tests/test_teaching_materials_files_api.py`
- E2E‑Skeleton: `backend/tests/test_supabase_storage_e2e.py` (skipped ohne ENV)

Marker & Gating:
- Integrationstests laufen nur mit `RUN_SUPABASE_E2E=1` und gesetzten `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`.

Hinweis:
- Keine Geheimnisse in Logs; Buckets privat; kurze TTLs (Upload 3 min, Download 45 s).
