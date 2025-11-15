# 2025-11-15 – Local Vision Adapter Hardening

Status: geplant

## Hintergrund
- Bezug: `docs/plan/2025-11-14-PR-fix3.md`, Must-Fix 1 & 2 („Local-Vision-Adapter zu komplex/unsicher“, „Supabase-Download härten“).
- Beobachtung: `_download_supabase_object` akzeptiert aktuell nur Host, ignoriert Port, fasst Redirects/HTTP-Fehler unscharf zusammen, liefert keine Telemetrie → Audit schwierig, SSRF-Risiko.
- Ziel: Download-Helper vereinfachen, Sicherheitschecks (Host+Port, Scheme, Redirects, Größenlimit) klar dokumentieren, Logging/Testabdeckung verbessern.

## User Story
> Als Betreiber:in des KI-Workers möchte ich, dass der Vision-Adapter nur Dateien von explizit erlaubten Supabase-Endpunkten lädt, Fehlerevents klar unterscheidet und verständlich dokumentiert ist, damit wir Remote-Fetches sicher auditieren können.

## BDD-Szenarien
1. **Happy Path – erlaubter Host/Port**  
   - **Given** `SUPABASE_URL=https://supabase.example.com:443` und Service-Role-Key gesetzt  
   - **When** `_download_supabase_object` wird mit einem Objekt-Key aufgerufen  
   - **Then** HTTP 200 Bytes werden gestreamt, die Größe überschreitet nicht das Limit, der Rückgabestatus lautet `"ok"` und die Bytes werden an den Vision-Adapter weitergereicht.

2. **Edge – Host/Port-Mismatch**  
   - **Given** `SUPABASE_URL=https://supabase.example.com:443`  
   - **When** der Helper konstruiert eine URL mit Host `supabase-evil.example.com` oder Port 444  
   - **Then** er bricht mit `"untrusted_host"` ab, ohne `httpx` zu öffnen.

3. **Edge – Redirect**  
   - **Given** HTTP-Client liefert 302 auf ein anderes Ziel  
   - **When** `_download_supabase_object` verarbeitet die Antwort  
   - **Then** der Helper gibt `(None, "redirect")` zurück, der Adapter behandelt dies als `VisionTransientError` und loggt den Grund.

4. **Edge – Response > Limit**  
   - **Given** `LEARNING_MAX_UPLOAD_BYTES=32`  
   - **When** beim Streamen mehr als 32 Bytes ankommen  
   - **Then** der Helper stoppt sofort mit `"size_exceeded"`, ohne weitere Bytes zu puffern.

5. **Fehler – HTTP ≥ 400**  
   - **Given** Supabase liefert 403  
   - **When** `_download_supabase_object` läuft  
   - **Then** der Helper liefert `(None, "http_error:403")` (differenzierter Code), Adapter wandelt es in `VisionTransientError` mit Logging.

## API / Vertrag
- Keine Änderungen an `api/openapi.yml` (rein interner Worker-Adapter).

## Datenmodell / Migration
- Keine Schemaänderungen erforderlich.

## Teststrategie (Red → Green)
1. **Unit/Adapter Tests**  
   - Erweitere `backend/tests/learning_adapters/test_local_vision_remote_fetch.py` oder neues Modul, um Host/Port/Scheme/Redirect/Size/Error-Szenarien abzudecken. Tests erwarten differenzierte Fehlercodes/Logging.
2. **Helper Tests**  
   - Falls nötig, separaten Test für `_storage_base_and_hosts` (z.B. akzeptiert https://host:port, sammelt Host+Port-Kombination).

Alle neuen Tests zunächst rot (aktuelles Verhalten unzureichend), danach minimaler Code-Fix.

## Tasks
1. Tests erweitern/neu schreiben (Host+Port, Redirect, Fehlercodes).  
2. `_download_supabase_object` refaktorieren: Host+Port-Whitelist, klarere Rückgabewerte, Logging, Timeout-Konstanten.  
3. Ergänzende Docstrings/Inline-Kommentare hinzufügen (Warum/Permissions).  
4. `docs/references/learning_ai.md` + `docs/CHANGELOG.md` aktualisieren, Befehle `supabase migration up`/`pytest -k vision` dokumentieren.

## Risiken
- Service-Role-Keys dürfen nicht geloggt werden → Logging muss sensible Header ausschließen.
- Strengere Host-Prüfung darf legitime Deployments nicht blockieren: Tests definieren klar SUPABASE_URL/SUPABASE_PUBLIC_URL, Ports müssen übereinstimmen.

