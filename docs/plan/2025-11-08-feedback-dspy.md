# Plan: DSPy-basiertes Feedback aktivieren

Datum: 2025-11-08
Autor: Codex (mit Felix)
Status: Entwurf

## Kontext / Problem
- Aktuell liefert der Feedback-Adapter (`backend/learning/adapters/local_feedback.py`) statische Rückmeldungen.
- Der DSPy-Pfad existiert theoretisch (`backend/learning/adapters/dspy/feedback_program.py`), wird aber nie genutzt, weil `dspy` sowie das benötigte LM-Binding nicht installiert/konfiguriert sind.
- Folge: Lernende erhalten keine adaptive Rückmeldung; alle Kriterienbewertungen sind Platzhalter.

## Ziel(e)
- DSPy real betreiben, sodass sowohl Rückmeldung als auch Auswertung (criteria.v2-Analyse) komplett modellgestützt erfolgen.
- Vision-Aufrufe bleiben direkt an Ollama (kein DSPy für OCR), um die Pipeline klar zu trennen.
- Sicherstellen, dass Rückmeldungen strukturierte `criteria.v2`-Analysen enthalten und textuelle Hinweise aus dem Modell nutzen.
- Fallback (Ollama/stub) bleibt verfügbar, greift jedoch ausschließlich, wenn der DSPy-Aufruf zur Laufzeit scheitert (Konfigurationsfehler, Timeout, Parsingproblem).

## User Story
Als Lehrkraft möchte ich, dass das KI-Feedback echte lernstandsbasierte Hinweise generiert, damit meine Schülerinnen und Schüler nachvollziehen können, was sie verbessern sollen.

## BDD-Szenarien (Given-When-Then)
1. **Happy Path – DSPy aktiv**
   - Given `dspy` ist installiert und die vorhandenen Ollama-ENV (`AI_FEEDBACK_MODEL`, `OLLAMA_BASE_URL`, ggf. Key) sind gesetzt
   - When der Learning-Worker ein Feedback samt Auswertung (criteria.v2) für ein Markdown-Text mit Kriterien erzeugt
   - Then ruft der Adapter das DSPy-Programm auf und beide Artefakte (Feedback + Analyse) stammen aus dem DSPy-Output (nicht aus Stub-Defaults).

2. **Fallback – DSPy-Konfigurationsfehler**
   - Given `dspy` ist installiert, aber `AI_FEEDBACK_MODEL` oder die Ollama-Host-Konfiguration fehlt
   - When ein Feedback erzeugt wird
   - Then der Adapter dokumentiert den Konfigurationsfehler, fällt auf den bisherigen Ollama-Pfad zurück und liefert weiterhin gültige `criteria.v2`-Strukturen.

3. **Fehlerhafte DSPy-Antwort**
   - Given DSPy liefert ungültiges JSON
   - When der Adapter versucht, das Ergebnis zu parsen
   - Then er nutzt den deterministischen Fallback (gleiches Verhalten wie heute) und protokolliert ein WARN-Log.

4. **Timeout/Exception im DSPy-Aufruf**
   - Given das DSPy-Programm löst einen Timeout aus
   - When der Adapter das Feedback berechnet
   - Then der Worker klassifiziert den Fehler als transient, plant einen Retry und markiert die Submission nicht als failed.

## API / OpenAPI
- Keine Änderungen am externen Vertrag (`api/openapi.yml`). Feedback bleibt Teil der bestehenden Submission-Flows.

## Migrationen (DB)
- Keine Schemaänderungen nötig.

## Technisches Konzept
- **Grundannahme**
  - DSPy ist fester Bestandteil der Deployment-Pipeline; fehlende Installationen gelten als Konfigurationsfehler, nicht als legitimer Betriebszustand.
  - `AI_BACKEND` bleibt auf `local`, der Feedback-Adapter entscheidet ausschließlich anhand der Runtime, ob DSPy erfolgreich ausgeführt werden kann; schlägt DSPy fehl, greift der deterministische Fallback.
- **Iteration 1 – DSPy-Programmierung**
  - Implementiere `backend/learning/adapters/dspy/feedback_program.py` als echtes DSPy `Program` (Structured Output + LM Binding via Ollama/HTTP) statt `_lm_call`.
  - Modellkonfiguration über die bestehenden ENV (`AI_FEEDBACK_MODEL`, `OLLAMA_BASE_URL`, Timeouts); Validierung der ENV gehört in diese Iteration.
  - Output Parsing weiterhin über `_parse_to_v2`, ergänzt um Telemetrie/Logging bei Schemafehlern.
- **Iteration 2 – Adapter Integration**
  - `backend/learning/adapters/local_feedback.py` nutzt DSPy standardmäßig; gelingt der Aufruf nicht, fällt der Adapter explizit auf den bestehenden Ollama-/Stub-Pfad zurück.
  - Fehler im DSPy-Pfad werfen `FeedbackTransientError`, damit der Worker einen Retry plant (keine stille Unterdrückung).
- **Iteration 3 – Deployment & Observability**
  - Poetry/requirements um `dspy`, ggf. `transformers` und benötigte Provider ergänzen; Lockfile aktualisieren.
  - Docker-Compose / ENV-Doku: wiederhole die bestehenden Ollama-ENV (`AI_FEEDBACK_MODEL`, `OLLAMA_BASE_URL`, Timeout) und markiere sie als zwingend für DSPy.
  - Telemetrie für Pfadwechsel (`feedback_backend=dspy|fallback`), damit Ops Fehlkonfigurationen sofort erkennt.

## TDD-Plan
1. **Tests schreiben**
   - DSPy-Programme/Signatures (neu):
     - Tests für `EvaluateCriteriaProgram` und `GenerateFeedbackProgram` (Variante 2, echte DSPy-Signatures mit typisiertem Output).
     - Sicherstellen, dass beide Programme die LM-Bindung über `OLLAMA_BASE_URL`/`AI_FEEDBACK_MODEL` nutzen.
     - `EvaluateCriteriaProgram`: bei leichten Abweichungen (z. B. `score="4.0"`, fehlende Criterion) muss die Nachvalidierung clampen/auffüllen und `schema="criteria.v2"` garantieren.
     - `GenerateFeedbackProgram`: darf keine Rohtext-Zitate enthalten und muss sich auf Kriterien/Analyse beziehen (kurzes Markdown, 1–3 Bullet Points).
   - Adapter-Test (Happy Path): injiziere Fake-`dspy` + Fake-Programme, stelle sicher, dass `local_feedback.analyze` den DSPy-Zweig nimmt und kein Stub-Feedback produziert.
   - Adapter-Test (Konfigurationsfehler): simuliere fehlende `AI_FEEDBACK_MODEL`- oder Host-ENV → erwarte Fallback + WARN.
   - Worker-E2E-Test: Setze `AI_BACKEND=local`, monkeypatch DSPy, führe Submission durch → verifiziere, dass `analysis_json` den DSPy-Inhalt enthält.
2. **Implementierung minimal**
   - Dateien/Module:
     - `backend/learning/adapters/dspy/signatures.py`: `EvaluateCriteriaSignature`, `CriterionResult`, `GenerateFeedbackSignature`.
     - `backend/learning/adapters/dspy/programs.py`: `EvaluateCriteriaProgram`, `GenerateFeedbackProgram` mit `dspy.Predict(...)`.
     - `backend/learning/adapters/dspy/feedback_program.py`: Orchestrierung (erst Evaluate → Validate/Clamp → dann Generate; Rückgabe `(feedback_md, analysis_json)`).
   - Adapter bleibt KISS: nutzt DSPy, wenn ENV ok, andernfalls Fallback.
3. **Refactor & Logging**
   - Telemetrie/Logs ergänzen (`feedback_backend=dspy`), Timeout-Handling klären.

## DSPy-Design (Variante 2 – echte Signatures)

Module-Aufteilung:
- `signatures.py`: DSPy-Signatures/Typschablonen (Input/Output).
- `programs.py`: Kleine DSPy-Programme (`EvaluateCriteriaProgram`, `GenerateFeedbackProgram`).
- `feedback_program.py`: Orchestrierung, Validierung/Clamping, öffentliche API `analyze_feedback`.

Signatures (Kernfelder):
- `EvaluateCriteriaSignature`
  - Input: `text_md: str`, `criteria: list[str]`
  - Output: `schema: Literal["criteria.v2"]`, `score: int (0..5)`, `criteria_results: list[CriterionResult]`
- `CriterionResult`: `criterion: str`, `max_score: int`, `score: int`, `explanation_md: str`
- `GenerateFeedbackSignature`
  - Input: `text_md: str`, `criteria: list[str]`, `analysis: EvaluateCriteriaSignature`
  - Output: `feedback_md: str` (kompaktes Markdown, keine Rohtext-Zitate)

Orchestrierung:
1) `EvaluateCriteriaProgram.predict(...)` → Ergebnis validieren/klampen, fehlende Kriterien ergänzen, `schema="criteria.v2"` setzen.
2) `GenerateFeedbackProgram.predict(...)` → kurzes, handlungsorientiertes Feedback (keine Rohtext-Zitate), Bezug auf Kriterien/Analyse.
3) Rückgabe `(feedback_md, analysis_json)`.

KISS/Architektur:
- Web/Worker bleibt DSPy-agnostisch; nur `analyze_feedback` wird aufgerufen.
- Parser-Logik reduziert sich auf Validierung/Clamping (kein schweres Reparieren mehr), Robustheit bleibt via Fallback erhalten.

## Risiken / Mitigations
- **Dependency Weight**: DSPy benötigt ggf. weitere Pakete → über Poetry sauber deklarieren und Caching beachten; SBOM aktualisieren.
- **Performance**: DSPy-Aufruf darf Worker nicht blockieren → Timeout/Retry konfigurieren.
- **Security & Compliance**:
  - Keine Rohtexte loggen; Telemetrie anonymisieren.
  - Dokumentiere Netzwerk-/Zugriffsanforderungen, damit Deployments keine offenen Endpunkte konfigurieren.

## Umsetzungsschritte (High-Level)
1. Abhängigkeiten: `pyproject.toml` aktualisieren (dspy + optionale Provider) und `poetry lock` aktualisieren.
2. DSPy-Programm implementieren (echte LM-Anbindung, Parsing, Logging).
3. Feedback-Adapter anpassen (DSPy-Branch stabilisieren, Fallback pflegen).
4. Tests (Unit + Worker-E2E) rot → grün.
5. Doku: ggf. `docs/plan`/`docs/science` Abschnitt ergänzen, ENV-Variablen dokumentieren.

## Prod-Parität (Lokal = Prod)
- DSPy-Pfad nutzt dieselben ENV/Modelle wie Prod (kein Dev-Shortcut).
- Tests und Worker laufen auf denselben Befehlen (docker compose, supabase, pytest).
