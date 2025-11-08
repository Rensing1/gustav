Title: Vision — PDF zu Bildern + Bildvorverarbeitung vor dem Vision-Modell

Datum: 2025-11-05
Autor: GUSTAV Team (Lehrer/Entwickler)
Status: Geplant (TDD-first)

Kontext
- Felix’ Vorgabe: Bei PDF-Abgaben alle Seiten in Bilder umwandeln. PNG/JPG und gerenderte PDF-Seiten werden vorverarbeitet (z. B. Kontrast erhöhen) und danach dem Vision-Modell als Bilder übergeben. Keine Sorge um Performance, keine Seitengrenzen nötig.
- Vorarbeiten: „images=[<b64>]“-Fix und Remote-Fetch aus Supabase sind bereits umgesetzt; PDFs werden aktuell noch nicht gerendert/verarbeitet.

User Story
- Als Schüler möchte ich, dass PDF- und Bildabgaben in gut lesbare Bilder aufbereitet und an das Vision‑Modell gegeben werden, damit der extrahierte Text zuverlässig und ohne manuelles Nacharbeiten erscheint.

BDD-Szenarien (Given-When-Then)
1) PNG/JPG — Preprocessing angewandt (Happy Path)
   - Given eine PNG/JPG-Abgabe unter `STORAGE_VERIFY_ROOT`
   - When der Vision-Adapter läuft
   - Then wird das Bild vorverarbeitet (z. B. Grayscale, leichte Kontrastanhebung wie CLAHE) und als Base64 über `images=[...]` an das Modell übergeben.

2) PDF — Alle Seiten gerendert (Happy Path)
   - Given eine PDF-Abgabe unter `STORAGE_VERIFY_ROOT` mit N Seiten
   - When der Vision-Adapter läuft
   - Then werden alle N Seiten zu Bildern gerendert, jeweils vorverarbeitet und als `images=[<b64_page1>, ..., <b64_pageN>]` an das Modell übergeben.

3) Remote-Only Datei (Optional, wenn lokal nicht verfügbar)
   - Given die Datei liegt nicht unter `STORAGE_VERIFY_ROOT`, aber in Supabase-Storage
   - When der Vision-Adapter läuft
   - Then werden die Bytes via Service-Role geladen, PDF→Bilder gerendert (für PDF), vorverarbeitet und als `images=[...]` übergeben.

4) Fehlerhafte Bildvorverarbeitung (Robustheit)
   - Given eine PNG/JPG/PDF-Abgabe
   - And die Vorverarbeitungsroutine wirft einen Fehler
   - When der Vision-Adapter läuft
   - Then fällt er auf „unverarbeitet“ zurück und sendet die Rohbytes in `images=[...]`, ohne den Job abstürzen zu lassen.

5) Client ohne `images`-Support (Kompatibilität)
   - Given eine PNG/JPG/PDF-Abgabe
   - And der `ollama.Client.generate` akzeptiert kein `images`-Argument
   - When der Vision-Adapter läuft
   - Then ruft er die Text-Signatur ohne `images` auf (Fallback) und markiert dies in den Metadaten.

API-Vertrag (OpenAPI)
- Keine Änderungen. Die Logik liegt im internen Worker/Adapter (keine neuen HTTP-Endpunkte).

Datenbank / Migration
- Keine Änderungen erforderlich.

Tests (TDD geplant)
- Unit: PNG/JPG werden vorverarbeitet (Hook wird aufgerufen), `images=[...]` enthält genau ein b64-Bild; Fallback, wenn Preprocessing fehlschlägt.
- Unit: PDF mit N Seiten → Renderer liefert N Bilder, alle werden (best-effort) vorverarbeitet und in `images=[...]` weitergegeben.
- Unit: Client ohne `images`-Parameter → Fallback ohne `images`, Metadaten vermerken den Fallback.
- Optional: Remote-Fetch-Pfad für PDF (httpx-Fake liefert PDF-Bytes → Rendering → `images=[...]`).

Risiken / Hinweise
- Performance: Nicht priorisiert (keine Seitengrenzen). Dennoch Logging der verarbeiteten Seitenzahl und Bytegröße zur Beobachtung.
- Qualität: Vorverarbeitung dezent halten (Grayscale, leichte Kontrastanhebung/CLAHE, ggf. sanfte Binarisierung). Kein aggressives Schärfen, um Artefakte zu vermeiden.
- Datenschutz/Sicherheit: Keine Speicherung der gerenderten Seiten dauerhaft; nur In-Memory/Temp. Keine Rohdaten in Logs (nur Längen/Meta).

Akzeptanzkriterien
- PNG/JPG und PDF-Abgaben liefern konsistent nicht-leere, sinnvoll extrahierte Texte; Vision-Client erhält `images=[...]` mit allen Seiten (für PDF).
- Tests für Happy Path und Fallbacks sind grün; UI-Polling zeigt wie gehabt pending→completed.

Nächste Schritte
1) Failing Tests schreiben (pytest) für Preprocessing-Hook, PDF→Bilder, Fallbacks.
2) Minimal-Implementierung im `local_vision`-Adapter (ohne Over-Engineering, nur testgrün).
3) Code-Review gegen Projektprinzipien (KISS, Security, Clean Architecture), danach gezielte Refactors.

