# Plan: Vision-Extraktion stabilisieren (Uploads/Proxy/Adapter)

Datum: 2025-11-08
Autor: Codex (mit Felix)
Status: Entwurf

## Kontext / Problem
- Symptom im UI: Für ein Bild (ex_submission.jpg) erscheint als extrahierter Text nur „I'm sorry, but I can't assist with that.“
- Erwartung: OCR/Transkription des handschriftlichen deutschsprachigen Textes.

## Beobachtungen
- Learning-Worker-Env (Container): `AI_BACKEND=local`, `LEARNING_VISION_ADAPTER=backend.learning.adapters.local_vision`, `OLLAMA_BASE_URL=http://ollama:11434`, `AI_VISION_MODEL=qwen2.5vl:3b`.
- Worker-Logs zeigen wiederholt `POST http://ollama:11434/api/generate "200 OK"` → Ollama wird aufgerufen.
- DB: Neueste `learning_submissions.kind='image'` → `analysis_status=completed`; `text_body` enthält Ablehnungssatz.
- Direkter Nachtest: Bild aus Supabase geladen und lokal an Ollama gesendet (`images=[b64]`) → korrekte Transkription in Markdown. Modell und `images`-Pfad funktionieren grundsätzlich.

## Hypothese (Root Cause)
1) Beim konkreten Job lagen dem Vision-Adapter keine Bildbytes vor (Upload noch nicht geschrieben oder nicht lesbar), dennoch wurde das Modell ohne `images` aufgerufen → generische Refusal-Antwort wurde als Ergebnis gespeichert.
2) Der Same-Origin Upload-Proxy `/api/learning/internal/upload-proxy` weicht derzeit vom „Lokal = Prod“-Prinzip ab: In Nicht-Prod liefert er eine „Soft-200“ (Digest) bei Upstreamfehlern, statt 502. Dadurch glaubt der Client, der Upload sei erfolgreich, obwohl kein Objekt existiert. Das erzeugt ein Zeitfenster ohne reale Bytes.

## Ziel(e)
- Vision-Aufrufe für Bild/PDF nur dann durchführen, wenn tatsächlich Bytes vorliegen (lokal oder via Supabase fetchbar). Sonst als transienten Fehler markieren und retryen.
- Sichtbarkeit/Diagnose verbessern (Logging/Telemetrie), ob `images` angehängt wurden und wie viele Bytes gelesen wurden.
- Prod-Parität herstellen: Upload-Proxy liefert bei Upstreamfehlern immer 502 (keine „Soft-200“), identisch in allen Umgebungen. Tests, die weiches Akzeptieren brauchen, nutzen den dokumentierten Dev-Stub (`/api/learning/internal/upload-stub`) explizit per Flag. Keine Verhaltensunterschiede zwischen Dev/Test/Prod.

## User Story
Als Lehrkraft möchte ich, dass Bild-/PDF-Einreichungen zuverlässig transkribiert werden, damit Lernende konsistentes, korrektes Feedback erhalten – auch wenn es zeitweise zu Verzögerungen beim Speichern oder Abrufen der Datei kommt.

## BDD-Szenarien (Given-When-Then)
1) Happy Path (Bild vorhanden)
   - Given eine Bild-Submission mit verfügbarem Objekt (lokal oder über Supabase abrufbar)
   - When der Learning-Worker den Vision-Schritt ausführt
   - Then wird das Bild mit `images=[b64]` an das Vision-Modell übergeben und der extrahierte Markdown-Text gespeichert.

2) Transient: Bild noch nicht verfügbar
   - Given eine Bild-Submission, deren Objekt (noch) nicht lesbar ist
   - When der Vision-Adapter Bytes laden möchte
   - Then wirft er `VisionTransientError("image_unavailable")` und der Job wird mit Backoff erneut versucht; kein Ablehnungstext wird persistiert.

3) Proxy-Upstream-Fehler (prod-paritätisch)
   - Given der Upload-Proxy kann die Supabase-URL nicht erreichen
   - When der Browser PUT an `/api/learning/internal/upload-proxy` sendet
   - Then erhält der Client 502 (kein Soft-200) — identisch in Dev/Test/Prod; Fehler ist früh sichtbar.

4) Dev-Stub (explizit aktiviert)
   - Given `ENABLE_DEV_UPLOAD_STUB=true`
   - When der Browser PUT an `/api/learning/internal/upload-stub?storage_key=...` sendet
   - Then werden die Bytes unter `STORAGE_VERIFY_ROOT` geschrieben und `{sha256, size_bytes}` zurückgegeben (für Tests/E2E).

## API / OpenAPI
- Keine API-Vertragsänderung vorgesehen. Verhalten ändert sich serverseitig (Adapter/Proxy), Endpunkte bleiben unverändert.
- Der Upload-Proxy bleibt ein interner Same-Origin-Endpunkt; der Dev-Stub ist im Vertrag dokumentiert und bleibt standardmäßig deaktiviert.
- Governance: Änderungen respektieren Contract-First; da keine neuen Felder/Status-Codes nach außen exponiert werden, bleibt `api/openapi.yml` unverändert.

## Migrationen (DB)
- Keine Schemaänderungen erforderlich.

## TDD-Plan
1) Tests ergänzen (Pytest, lokal = prod)
   - Vision: „fehlende Bytes“ → Adapter wirft `VisionTransientError("image_unavailable")`, Worker markiert Retry (Status bleibt `pending`), kein „Refusal“-Text wird gespeichert.
   - Vision: „Bytes vorhanden (jpeg/png/pdf)“ → Adapter übergibt `images=[b64]` an das Modell; Antwort ist nicht leer; `analysis_status=completed` und `text_body` gefüllt.
   - Vision: „leere Modellantwort“ → als transient werten (Retry), keine Persistenz leerer/ablehnender Texte.
   - Proxy (prod-paritätisch): Bei Upstreamfehler (z. B. `requests.put` Exception oder Upstream ≥ 300) → 502 in allen Umgebungen; kein Digest im Body.
   - Upload-E2E ohne externen Storage: Mit `ENABLE_DEV_UPLOAD_STUB=true` PUT an `/api/learning/internal/upload-stub?storage_key=...` → `{sha256, size_bytes}` retour, Datei unter `STORAGE_VERIFY_ROOT` liegt vor.

2) Minimal-Implementierung
   - `backend/learning/adapters/local_vision.py`
     - Reihenfolge: lokal lesen (wenn `STORAGE_VERIFY_ROOT` gesetzt) → falls nicht vorhanden, Supabase GET → nur bei vorhandenen Bytes `images=[...]` setzen. Wenn beides fehlschlägt → `VisionTransientError("image_unavailable")`.
     - Prompt leicht präzisieren („OCR assistant … German possible … do not refuse.“).
     - Optionales INFO-Log/Telemetry: `model`, `used_images` (bool), `bytes_read` (int).
   - `backend/web/routes/learning.py` (Upload-Proxy)
     - Soft-200 entfernen: Bei Exceptions oder Upstream-Status ≥ 300 immer 502 zurückgeben (prod-paritätisch). Für Tests/E2E, die weiche Annahme benötigen, stattdessen den dokumentierten Dev-Stub (`/api/learning/internal/upload-stub`) mit Flag nutzen.

3) Fehlerklassifikation im Adapter schärfen
   - „missing_file“ bei gesetztem `STORAGE_VERIFY_ROOT` nicht als permanent behandeln; erst Supabase-GET versuchen. Falls weiterhin keine Bytes → `VisionTransientError("image_unavailable")`.

4) Refactor/Absicherung
   - Kleine Hilfsfunktion für Byte-Ladevorgang (lokal/Supabase) im Adapter extrahieren (KISS, Single Responsibility).
   - Kurze Docstrings und Inline-Kommentare im Adapter.

## Test-Matrix (konkret)
- Vision Adapter
  - fehlende Datei lokal + remote: Transient (Retry), kein Persistieren.
  - vorhandene Datei: `images` gesetzt, Antwort nicht leer, Persistieren OK.
  - leere Modellantwort: Transient (Retry), kein Persistieren.
- Upload Proxy
  - Upstream ok: 2xx Durchleitung, Digest/Metadaten wie bisher.
  - Upstream down/≥300/Exception: 502 in Dev/Test/Prod (gleiches Verhalten).
- Dev-Stub
  - Flag aus: 404/disabled.
  - Flag an: schreibt Bytes, liefert `{sha256, size_bytes}`.

## Risiken / Mitigations
- Längere Wartezeiten durch Retries bei Storage-Verzögerungen → Backoff ist vorhanden; Logging macht Ursachen sichtbar.
- Tests, die sich bisher auf „Soft-200“ stützten → auf Dev-Stub umstellen; CI setzt Flag gezielt und bleibt prod-paritätisch im übrigen Verhalten.

## Akzeptanzkriterien
- Reale Bild-Submission führt konsistent zu sinnvollem extrahiertem Markdown (keine generische Ablehnung).
- Fehlt das Objekt, wird kein „Refusal“-Text gespeichert; der Worker versucht erneut.
- Proxy verhält sich in Dev realistisch (502 bei Upstreamfehlern); Tests bleiben grün mit Test-Flag.

## Umsetzungsschritte (kurz)
1) Tests schreiben (Vision fehlende Bytes → transient retry; Proxy 502 bei Upstreamfehler; Dev-Stub-basierte Upload-E2E).
2) Adapter anpassen (Byte-Ladepfad: lokal → remote → transient; Prompt, Logging).
3) Proxy anpassen (Soft-200 vollständig entfernen), Compose/CI so belassen, optional Dev-Stub in Tests aktivieren.
4) Manuelles E2E: Datei einreichen, Logs prüfen (`used_images=true`, `bytes_read>0`), Submission wird erst nach echten Bytes analysiert.

## Prod-Parität (Lokal = Prod)
- Keine „Dev-only“-Sonderpfade im Verhalten: Proxy antwortet identisch in allen Umgebungen (502 bei Fehlern). Der Dev-Stub ist ein explizit aktivierbares Feature, kein versteckter Soft‑Pfad.
- Migrationen/ENV/Netz entsprechen Prod; Tests nutzen die gleiche DB-Struktur. Upload-Verifikation ist über gemeinsame ENV (z. B. `REQUIRE_STORAGE_VERIFY`) konsistent steuerbar.
- Guardrail (AGENTS.md): Jede Änderung muss Tests passieren, die dieselben Kommandos in Dev/Prod verwenden (Docker Compose, Supabase Migrationen, Pytest). Keine Sonderfälle in Codepfaden für lokal.

## Implementierungs-Referenzen (Dateien/Zeilen)
- Upload-Intents (Schüler): `api/openapi.yml:4665`
- Dev Upload-Stub (dokumentiert): `api/openapi.yml:4766`
- Proxy-Route (intern): `backend/web/routes/learning.py:1159`
- Soft-200-Zweige (entfernen): `backend/web/routes/learning.py:1186`, `backend/web/routes/learning.py:1194`
- Vision Adapter Bytes-Handling: `backend/learning/adapters/local_vision.py:120`, `:139`, `:188`, `:205`
- Verifikations-Policy/ENV: `backend/storage/learning_policy.py:31`
- Worker-Retry (Transient): `backend/learning/workers/process_learning_submission_jobs.py:260`

## Rollout / Validierung
- Unit/Integration Tests ausführen: `.venv/bin/pytest -q`
- Compose-Stack: `docker compose up -d --build`; `supabase status` prüfen.
- E2E Smoke: Bild uploaden → sicherstellen, dass `bytes_read>0` geloggt wird, `used_images=true`, `analysis_status=completed` mit sinnvollem Text. Bei fehlenden Bytes → Retry statt Ablehnung.

## Notizen
- Keine OpenAPI- oder Migrationsänderungen – ausschließlich Verhaltenshärtung.
- Modelle bereits vorhanden; `AI_VISION_MODEL` bleibt bei `qwen2.5vl:3b` (funktioniert in Repro).
