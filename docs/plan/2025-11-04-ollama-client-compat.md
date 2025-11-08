# Plan: Ollama-Client-Kompatibilität in Adaptern

Kontext:
- Symptom: Keine KI-Rückmeldung, Worker requeued Jobs. Logs: `ollama client unavailable: No module named 'ollama'` (initial), später `psycopg3 is required ...` und nach Fix der Abhängigkeiten weiterhin kein Ergebnis.
- Ursache: Adapter konstruieren `ollama.Client(base_url=...)`. Realer Client erwartet positional/`host`. Tests nutzten einen Fake, der `base_url` tolerierte.

User Story:
- Als Lehrer möchte ich, dass nach einer Abgabe die KI-Auswertung zuverlässig läuft, damit ich zeitnah Feedback sehe.

BDD-Szenarien (Given-When-Then):
- Given ein Host-only `ollama.Client(host=None)`, When der Vision-Adapter läuft, Then liefert er Markdown und Metadaten (kein Fehler).
- Given ein Host-only `ollama.Client(host=None)`, When der Feedback-Adapter läuft, Then liefert er `criteria.v2`-Analyse und Markdown.
- Given ein Zeitüberschreitungssignal, When das Modell aufgerufen wird, Then klassifiziert der Adapter dies als transienten Fehler.

API / OpenAPI:
- Keine API-Änderung (interner Worker/Adapter-Fix). Kein Vertrag betroffen.

Datenbank / Migration:
- Keine Schemaänderung nötig.

Tests (TDD):
- Neu: `backend/tests/learning_adapters/test_local_adapters_ollama_client_signature.py` (host-only Fake-Client, erzwingt positional Konstruktion).
- Bestehende Adaptertests bleiben unverändert grün.

Update 2025-11-05 — Vision-Bilderweiterung
- Ergänzung: Der Vision-Adapter übergibt bei `image/jpeg` und `image/png` nun Base64-Bilddaten über das `images`-Argument, sofern der Client dies unterstützt.
- Rückfall: Fehlt das `images`-Argument in der Client-Signatur, wird ohne `images` aufgerufen (kompatibles Verhalten).
- Test: `backend/tests/learning_adapters/test_local_vision_images_param.py` prüft, dass `images=[<b64>]` gesetzt und zurück-dekodierbar ist.

Implementierung:
- `backend/learning/adapters/local_vision.py`: `ollama.Client(self._base_url)` (positional) statt `base_url=`.
- `backend/learning/adapters/local_feedback.py`: analog.
- Dockerfile: Python-Paket `ollama` nicht mehr hart versioniert.

Risiken / Nacharbeiten:
- Start-Up-Probe für Ollama im Worker in Betracht ziehen (Healthcheck).
- Test-Fakes perspektivisch so gestalten, dass sie sowohl `host` als auch `base_url` akzeptieren (robuster, aber derzeit durch neuen Test abgedeckt).
