Title: Vision — Ablehnungs-Ausgaben bei Bild/PDF, Ursachenanalyse und nächste Schritte

Datum: 2025-11-05
Autor: GUSTAV Team (Lehrer/Entwickler)
Status: Teil-Behoben (Images-Parameter & Remote-Fetch umgesetzt); PDF-Extraktion ausstehend

Kontext / Problem
- Symptom JPG: Nach Abgabe erscheint als „extrahierter Text“ oft „I'm sorry, but I can't assist with that.“
- Symptom PDF: „Sure, please upload the PDF file.“
- Beobachtung: In Ollama direkt liefert das Vision‑Modell sinnvolle Ergebnisse.

Erkenntnisse (Logs & Code)
- Worker‑Logs: POST http://ollama:11434/api/generate → 200 OK (Vision/Feedback werden erreicht).
- Ollama‑Logs: Modelle geladen (z. B. llama3.2:1b, qwen2.5vl:3b).
- Vorheriger Adapter‑Stand: Bei Bild/PDF wurde `ollama.Client.generate(...)` ohne Bilddaten aufgerufen → viele Vision‑Modelle antworten dann generisch/unhilfreich.
- Dev/Proxy‑Pfad: Dateien liegen häufig in Supabase (Proxy) und nicht lokal. Ohne `STORAGE_VERIFY_ROOT`‑Mapping sind Bytes im Worker nicht lesbar.

Ursache
1) Images fehlten: Vision‑Adapter übergab dem Modell keine Bilddaten (Parameter `images=[<base64>]`).
2) Dev‑Pfad/Proxy: Bilddateien lagen nur im Object‑Storage, nicht im Container‑Dateisystem; der Adapter las daher keine Bytes.
3) PDF ist (noch) kein Bild: Das aktuelle Minimal‑Design übergibt keine PDF‑Seiten als Images und führt auch keine lokale PDF‑Textextraktion aus.

Beschlossene/umgesetzte Änderungen (Red→Green)
- TDD: `backend/tests/learning_adapters/test_local_vision_images_param.py` — stellt sicher, dass `images=[<b64>]` gesetzt wird.
- TDD: `backend/tests/learning_adapters/test_local_vision_remote_fetch.py` — wenn lokal kein File, per Service‑Role aus Supabase laden und als `images` weitergeben.
- Adapter: `backend/learning/adapters/local_vision.py`
  - JPEG/PNG: Base64‑Bilddaten generieren und an `generate(..., images=[...])` übergeben (nur wenn die Client‑Signatur es unterstützt; sonst Fallback ohne `images`).
  - Remote‑Fetch: Falls lokal nicht verfügbar, Retrieval via `GET {SUPABASE_URL}/storage/v1/object/submissions/{storage_key}` mit `SUPABASE_SERVICE_ROLE_KEY`.
  - Prompt verschärft (keine Refusals/Disclaimer).
- Dev‑Compose: Gemeinsames Volume `./.tmp/dev_uploads` und `STORAGE_VERIFY_ROOT=/app/.tmp/dev_uploads` für Web und Worker.

Aktueller Stand
- Bild‑Abgaben (JPG/PNG): Modell erhält nun die Bildbytes → deutlich weniger generische Ablehnungen; extrahierter Text erscheint in der Historie.
- PDF‑Abgaben: Weiterhin nur textbasierte Prompt‑Zusammenfassung (kein echtes PDF‑Parsing); daher gelegentlich generische Antworten.

User Story
- Als Schüler möchte ich, dass Bild‑ und PDF‑Abgaben zuverlässig in Text überführt werden, damit ich ohne Neustart der Seite Ergebnisse und Feedback sehen kann.

BDD‑Szenarien (Given‑When‑Then)
1) Bild (Happy Path)
- Given eine JPG/PNG‑Abgabe mit gültigen Metadaten
- When der Worker den Vision‑Schritt ausführt
- Then liest der Adapter Bildbytes (lokal oder remote) und übergibt `images=[<b64>]` an das Modell; der Verlauf zeigt den erkannten Text.

2) Datei nur im Storage (Remote‑Fetch)
- Given die Datei liegt nicht unter `STORAGE_VERIFY_ROOT`
- When der Vision‑Adapter läuft
- Then werden die Bytes via Supabase‑GET geladen; Modell erhält `images=[<b64>]`.

3) PDF (MVP‑Istzustand)
- Given eine PDF‑Abgabe
- When der Vision‑Adapter läuft
- Then erfolgt kein echtes Parsing; das Ergebnis kann generisch ausfallen.

API‑Vertrag
- Keine Änderungen (interner Worker/Adapter‑Fix; HTML‑SSR/REST unverändert).

Datenbank / Migration
- Keine Änderungen.

Tests (TDD)
- Bereits umgesetzt: s. o. (`test_local_vision_images_param.py`, `test_local_vision_remote_fetch.py`).
- Geplant (für PDF‑Phase): Unit‑Test für PDF‑Text‑Extraktion (Parser‑Stub), E2E‑Test: PDF → Verlauf zeigt extrahierte Textzeilen.

Risiken / Sicherheit
- Service‑Role‑Fetch: Zugriff auf Storage‑Objekte erfolgt serverseitig per Service‑Role (keine Client‑Exponierung). Zeitouts/403/404 werden still toleriert (kein Crash), aber im Meta vermerkt.
- Performance: Große Bilder → evtl. Downscaling/Byte‑Limit, Timeouts erhöhen.
- Datenschutz: Keine Rohdatenlogs; nur Längen/Meta.

Nächste Schritte (geplant)
1) PDF‑Textextraktion (Minimal)
   - Variante A (leicht): Plain‑Text mit `pypdf`/`pdfminer.six` extrahieren (ohne OCR). Pros: keine Bildkonvertierung, schnell; Cons: eingebettete Scans liefern wenig.
   - Variante B (später): PDF‑Seiten zu Bildern rendern (z. B. `pdftoppm`/`Pillow`) und als `images` an Vision senden. Pros: einheitlicher Pfad; Cons: Zusatzabhängigkeiten/CPU.
   - TDD: Unit‑Test “PDF liefert nicht‑leeren Text”, E2E “PDF→pending→completed mit Text im Verlauf”.

2) Robustheit/Beobachtbarkeit
   - Logging: Adapter‑Meta `bytes_read`/`remote_fetch=true/false` in Worker‑Logs sichtbarer machen (LOG_LEVEL).
   - Env‑Dokumentation: README/Runbook-Hinweis zu `STORAGE_VERIFY_ROOT`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.

3) Modell/Config‑Hygiene
   - Sicherstellen, dass `AI_VISION_MODEL` auf ein VL‑Modell zeigt (z. B. `qwen2.5-vl:3b` oder `llama3.2-vision`).
   - Optional: Resize/Limit für sehr große Bilder vor Übergabe an das Modell.

Akzeptanzkriterien (für Abschluss der PDF‑Phase)
- PDF‑Abgaben zeigen konsistent sinnvollen, nicht‑leeren extrahierten Text (ohne “please upload…”).
- Unit‑/E2E‑Tests grün; UI‑Polling zeigt den Wechsel von pending→completed ohne Reload.

