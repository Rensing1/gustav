Title: Vision: Bilddaten an das Modell übergeben (images-Parameter)

Datum: 2025-11-05
Autor: GUSTAV Team (Lehrer/Entwickler)
Status: Implementiert (TDD-gestützt); keine API/DB-Änderungen

Kontext
- Symptom: Bei Bild-/PDF-Abgaben zeigte die UI häufig generische Modell-Ablehnungen (z. B. „I'm sorry, but I can't assist with that.“), obwohl der Worker erfolgreich Jobs verarbeitete.
- Ursache: Der lokale Vision-Adapter rief den Ollama-Client ohne visuelle Eingaben auf (kein `images`-Argument). Viele Vision-Modelle benötigen den Bildinhalt explizit, sonst reagieren sie wie reine Text-Modelle.

User Story
- Als Schüler möchte ich, dass aus meinen Bild-Abgaben wirklich Text extrahiert wird, damit ich zeitnah sinnvolle Ergebnisse in der Historie sehe.
- Als Lehrer möchte ich, dass der Worker deterministisch arbeitet und Modelle korrekt bedient, damit die Lernenden konsistentes Feedback erhalten.

BDD-Szenarien (Given–When–Then)
1) Image Happy Path
   - Given eine Bildabgabe (mime=image/png|image/jpeg) mit verifizierbarem `storage_key` und korrektem `sha256`
   - When der Worker den Vision-Schritt ausführt
   - Then liest der Adapter die Bytes, base64-kodiert sie und übergibt sie als `images=["<b64>"]` an den Client
   - And Then das Modell liefert Markdown-Text (keine generische Ablehnung)

2) PDF (MVP)
   - Given eine PDF-Abgabe (mime=application/pdf)
   - When der Vision-Schritt ausgeführt wird
   - Then erfolgt weiterhin eine textbasierte Prompt-Zusammenfassung (kein `images`-Feld in dieser Iteration)

3) Client-Kompatibilität
   - Given ein Ollama-Client ohne `images`-Parameter in der Signatur
   - When der Adapter aufgerufen wird
   - Then fällt er sicher auf den alten Aufruf ohne `images` zurück (Prompt-only), ohne zu crashen

4) Fehlerfälle vor dem Modellaufruf
   - Given Speicherpfad außerhalb von `STORAGE_VERIFY_ROOT`, fehlende Datei, Größen- oder Hash-Mismatch
   - Then klassifiziert der Adapter dies als permanente Fehler und ruft das Modell nicht auf

API-Vertrag
- Keine Änderungen (interner Worker/Adapter-Fix; bestehende Learning-API bleibt unverändert).

Datenbank / Migration
- Keine Änderungen.

Tests (TDD)
- Neu: `backend/tests/learning_adapters/test_local_vision_images_param.py`
  - Erzeugt eine kleine PNG-Testdatei unter `STORAGE_VERIFY_ROOT`.
  - Patcht einen Fake-Ollama-Client, der `images` akzeptiert und aufzeichnet.
  - Erwartung: Adapter gibt genau ein Base64-Bild an den Client und erhält Markdown.

Implementierung
- Datei: `backend/learning/adapters/local_vision.py`
  - Liest Bildbytes nach erfolgreicher Verifikation und kodiert sie mit Base64.
  - Prüft via `inspect.signature`, ob der Client ein `images`-Argument unterstützt.
  - Ruft `client.generate(..., images=[b64])` nur bei JPEG/PNG auf; sonst Fallback ohne `images`.
  - Bewahrt Kompatibilität (positional Konstruktor `ollama.Client(self._base_url)`).

Sicherheit & Datenschutz
- Keine Rohdatenlogs der Schülerabgaben; Base64-Daten nur im Arbeitsspeicher weitergereicht.
- Pfad-, Größen- und Hash-Prüfungen verhindern Missbrauch/Path-Escapes.

Risiken / Nacharbeiten
- PDF: Optional später echte Extraktion statt textbasierter Zusammenfassung.
- Große Bilder: Beobachten, ob zusätzliche Größenlimits/Chunking nötig sind.
- Modelle: `.env` konsistent halten (z. B. `AI_VISION_MODEL=qwen2.5-vl:3b` oder `llama3.2-vision`).

