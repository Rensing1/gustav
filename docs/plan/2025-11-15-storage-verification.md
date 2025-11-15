# 2025-11-15 – Storage Verification Hardening

Status: umgesetzt

## Kontext
- Must-Fix 3 aus `docs/plan/2025-11-14-PR-fix3.md`: Storage-Verification-Konfiguration ist schwer zu interpretieren (`require_remote` steuert mehrere Pfade, Rückgabecodes wie `"skipped"`, `"hash_unavailable"` oder `"download_exception"` sind unklar).
- Ziel: Klare Semantik für die Verifikation von Supabase-Uploads, getrennte Flags für HEAD-vs-Download, eindeutigere Result-Enums und bessere Dokumentation/tests.

## User Story
> Als Learning-Operator möchte ich, dass `verify_storage_object_integrity` klar dokumentiert ist, differenzierte Rückgabecodes liefert und nur notwendige Remote-Fetches ausführt, damit Fehlerszenarien (Host-Mismatch, Hash fehlt, Redirect) zuverlässig erkannt und protokolliert werden können.

## BDD-Szenarien
1. **Happy Path – HEAD + Hash passt**  
   - **Given** `require_remote_head=True`, Supabase antwortet mit `Content-Length`, `Etag=sha256`  
   - **When** `verify_storage_object_integrity` läuft  
   - **Then** es liefert `verified=true`, `reason="match_head"`, ohne Download.

2. **Edge – Hash fehlt, Download erlaubt**  
   - **Given** `require_remote_head=True`, HEAD liefert kein Hash, aber `allow_download_fallback=True`  
   - **When** die Funktion ausgeführt wird  
   - **Then** sie streamt bis zur Limitgröße, berechnet SHA256 und gibt `verified=true`, `reason="match_download"` zurück.

3. **Edge – Redirect im Download**  
   - **Given** HEAD erfolgreich, aber Download liefert 302  
   - **When** `verify_storage_object_integrity` mit Download-Fallback läuft  
   - **Then** reason=`"download_redirect"`, Ergebnis `verified=false`, `recoverable=true`.

4. **Fehler – Host-Mismatch**  
   - **Given** die URL verweist auf einen nicht whitelisted Host  
   - **When** `verify_storage_object_integrity` ausgeführt wird  
   - **Then** sie bricht mit `verified=false`, `reason="untrusted_host"` ab und loggt den Vorfall, ohne Netzaufruf.

5. **Fehler – MIME-Check**  
   - **Given** `mime_type` übergeben, aber nicht in der erlaubten Liste  
   - **When** verifiziert wird  
   - **Then** `VisionPermanentError` (oder klarer Fehler) signalisiert, dass Upload verworfen wird.

## API / Vertrag
- Keine Änderungen an `api/openapi.yml`, da Storage-Verifikation intern verwendet wird (Worker/Web).

## Datenmodell / Migration
- Keine Schemaänderungen.

## Teststrategie (Red → Green)
1. **Unit Tests** (`backend/tests/test_storage_verification.py` o.ä.):
   - HEAD-only Erfolg, Download-Fallback Erfolg, Redirect/HTTP Fehler, Host-Mismatch, MIME-Verbot.
   - Tests prüfen neue Result-Enum/NamedTuple (z.B. `StorageVerifyResult(status="match_head")`).
2. **Adapter/Integration Tests**:
   - Worker-/Learning-Tests sicherstellen, dass neue Rückgabecodes korrekt behandelt und geloggt werden.

## Tasks
1. Tests schreiben/erweitern (HEAD/Download/Hostcases).  
2. `backend/storage/verification.py` refaktorieren: getrennte Flags, klarer Result-Typ, Logging, MIME-Whitelist.  
3. Adaptionen in Learning-Web/Worker, wenn sie Result-Felder auswerten.  
4. Dokumentation & Changelog aktualisieren.

## Risiken
- Änderungen am Result-Typ betreffen mehrere Call-Sites (Learning-Web, Worker, Tests). Sorgfältig refaktorieren.  
- Download-Fallback darf Service-Role-Key nicht loggen; Logging muss sanitized bleiben.

## Fortschritt 2025-11-15
- Tests `backend/tests/test_storage_verification_helper.py` und bestehende Streaming-Suite decken nun `match_head`, `match_download`, Redirect/Host-Fehler und MIME-Checks ab.
- `verify_storage_object_integrity` verifiziert MIME-Allowlist, unterscheidet Rückgabecodes und propagiert Download-Fehler klar.
- Changelog + Referenzen aktualisiert; PR-Plan (`docs/plan/2025-11-14-PR-fix3.md`) Fortschritt dokumentiert.
