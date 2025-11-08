# Plan: Optionale Ollama-Integrationstests (Connectivity & Vision)

Datum: 2025-11-06
Autor: Lehrkraft/Entwickler (GUSTAV)

## Kontext
- Die aktuelle Testsuite deckt Vision- und Feedback-Schritte breit ab, verwendet dabei jedoch Fakes/Monkeypatches (deterministisch, netzwerkfrei).
- Es fehlt bewusst ein echter Roundtrip gegen einen laufenden lokalen Ollama-Dienst, um Flakiness in CI zu vermeiden.
- Wunsch: Eine optional aktivierbare Integrationsschicht, die bei Bedarf echte Konnektivität und Modell-Verfügbarkeit prüft – standardmäßig aber sauber geskippt wird.

## Ziel
Eine zusätzliche, explizit markierte Testsuite, die echte Anfragen an einen lokal laufenden Ollama-Dienst stellt, um:
- Konnektivität (`OLLAMA_BASE_URL`) zu validieren,
- Modellverfügbarkeit (z.B. `AI_FEEDBACK_MODEL`, `AI_VISION_MODEL`) zu prüfen,
- den Vision-Pfad inkl. `images=[…]` Parameter stichprobenartig zu verifizieren.

Diese Tests laufen nur, wenn ein neues Flag gesetzt ist und verweigern externe Hosts (Security First).

## User Story
Als Entwickler/Operator möchte ich optional überprüfen, ob unser lokaler Ollama-Dienst erreichbar ist und die benötigten Modelle bereitstehen, damit ich vor einem manuellen E2E-Test/Release sicher sein kann, dass die KI-Integration funktionsfähig ist.

## BDD-Szenarien (Given-When-Then)
1) Connectivity (Feedback)
- Given `RUN_OLLAMA_E2E=1` und eine lokale `OLLAMA_BASE_URL` (localhost/127.0.0.1/ollama)
- When `ollama.Client(...).generate(model=AI_FEEDBACK_MODEL, prompt=...)` aufgerufen wird
- Then erhält der Test eine Antwort mit `dict['response']` (nicht leer)

2) Modell nicht gepullt
- Given `RUN_OLLAMA_E2E=1` aber das Modell ist nicht vorhanden
- When `generate` aufgerufen wird
- Then wird der Test mit `pytest.skip(...)` übersprungen und zeigt eine klare Pull-Anweisung (`ollama pull <MODEL>`)

3) Standard: aus
- Given `RUN_OLLAMA_E2E` ist nicht gesetzt (oder `!= 1`)
- Then werden alle `ollama_integration`-Tests standardmäßig geskippt

4) (Optional) Vision-Bildpfad
- Given `RUN_OLLAMA_VISION_E2E=1` und ein kleines PNG-Beispiel (lokal oder aus Supabase fetched)
- When der Vision-Adapter ein `generate(..., images=[<b64>])` anstößt
- Then kommt eine valide Antwort zurück und der Adapter protokolliert Metadaten `raw_metadata.adapter in {"local","local_vision"}`

## Design-Entscheidungen
- Neuer pytest-Marker: `ollama_integration` (in `pytest.ini` registrieren)
- Gating über ENV-Flags:
  - `RUN_OLLAMA_E2E=1` schaltet reine Connectivity-Tests frei
  - `RUN_OLLAMA_VISION_E2E=1` schaltet optionale Bildpfad-Tests frei
- Host-Sicherheit: Tests akzeptieren nur `localhost`, `127.0.0.1` oder Compose-Dienst `ollama` (keine externen Hosts wie `example.com`).
- Modelle:
  - Feedback: nutzt `AI_FEEDBACK_MODEL` (zwingend). Ist die Variable leer/nicht gesetzt oder das Modell nicht gepullt, wird mit Anleitung (`ollama pull ${AI_FEEDBACK_MODEL}`) geskippt.
  - Vision: nutzt `AI_VISION_MODEL` (zwingend). Ist die Variable leer/nicht gesetzt oder das Modell nicht gepullt, wird mit Anleitung (`ollama pull ${AI_VISION_MODEL}`) geskippt.
- Fehlerpolitik: keine harten Netzwerk-Fehlschläge – bei fehlenden Modellen oder nicht erreichbarem Dienst → `pytest.skip(...)` mit klarer Anleitung.
- Timeouts: konservativ (z.B. 10–15s), um Hänger zu vermeiden.

## Änderungen (Umriss)
1) `pytest.ini`: Marker `ollama_integration` ergänzen (Warnungen vermeiden)
2) Neuer Test (konnektiv): `backend/tests/ai/test_ollama_integration.py`
   - prüft `generate` gegen `AI_FEEDBACK_MODEL`
   - validiert Host, Flag, Antwortstruktur
3) Optionaler Vision-Test: `backend/tests/ai/test_ollama_vision_integration.py`
   - nutzt das reale Testbild `backend/tests/ex_submission.jpg` (JPG)
   - base64‑encodet die Datei und ruft `generate(..., images=[...])`
   - prüft eine nicht‑leere Antwort (Blackbox: nur End‑Response validieren)
4) Dokumentation: Kurzabschnitt in `README.md` (lokal laufen lassen, Flags setzen)

## Voraussetzungen & Setup
- Laufende lokale Umgebung:
  - `docker compose up -d --build`
  - `docker compose exec ollama ollama pull ${AI_FEEDBACK_MODEL}`
  - `docker compose exec ollama ollama pull ${AI_VISION_MODEL}` (für Vision-Test)
- Empfohlene ENV:
  - `AI_FEEDBACK_MODEL` (z.B. `llama3.1:8b`)
  - `AI_VISION_MODEL` (z.B. `llama3.2-vision`)
  - `OLLAMA_BASE_URL` (z.B. `http://localhost:11434` oder Compose-intern `http://ollama:11434`)

## Sicherheitsüberlegungen (DSGVO/Security First)
- Keine externen Hosts zulassen; nur lokale/Compose-Hosts.
- Keine personenbezogenen Inhalte in den Prompts der Integrations-Tests.
- Tests sind optional und standardmäßig aus.

## Risiken & Abwägungen
- Flakiness bei hoher Auslastung von GPU/CPU → mitigiert durch Skips/Timeouts.
- CI-Laufzeit → standardmäßig aus; nur lokal gezielt einschalten.

## Schritt-für-Schritt Umsetzung (DoD)
1) `pytest.ini` um Marker `ollama_integration` erweitern
2) Konnektivitätstest anlegen (`backend/tests/ai/test_ollama_integration.py`)
3) Optionalen Vision-Test anlegen (`backend/tests/ai/test_ollama_vision_integration.py`)
4) README ergänzen (Anleitung: Flags, `ollama pull`, Aufrufbeispiele)
5) Manuelle Verifikation lokal durchführen (siehe unten)

## Manuelle Verifikation
1) Modelle bereitstellen:
   - `docker compose exec ollama ollama pull ${AI_FEEDBACK_MODEL}`
   - `docker compose exec ollama ollama pull ${AI_VISION_MODEL}`
2) Flags setzen und Tests starten:
   - `export RUN_OLLAMA_E2E=1`
   - `pytest -q -m ollama_integration` (nur Konnektivität)
   - Optional Vision: `export RUN_OLLAMA_VISION_E2E=1` und `pytest -q -m ollama_integration -k vision`

## Rollback / Deaktivierung
- Flags nicht setzen → Tests sind automatisch geskippt.
- Marker kann in CI global exkludiert werden (z.B. `-m "not ollama_integration"`).
