# Plan: DSPy structured output for learning feedback

## Context
- Aktuelle DSPy-Pipeline liefert JSON als Freitext; Parser `_parse_to_v2` muss den Text normalisieren und fällt bei Formatabweichungen auf Stubs zurück.
- DSPy 3.0.3 unterstützt strukturierte OutputFields, womit Analyse- und Feedbackmodule direkt Python-Objekte liefern könnten.
- Ziel: Eine robuste Zwei-Stufen-Pipeline (Analyse → Rückmeldung) ohne JSON-Freitext, damit Kriterienwerte und Feedback zuverlässig durchgereicht werden.

## Zielbild
1. **Analyseprogramm** (`CriteriaAnalysisProgram`):
   - Inputs: `student_text_md`, `criteria`, optional `teacher_instructions_md`, `solution_hints_md`.
   - Outputs (DSPy OutputFields): `overall_score` (0–5) und `criteria_results` (Liste von Objekten mit `criterion`, `max_score`, `score`, `explanation_md`).
   - Rückgabe als Python-Dict, keine JSON-Strings.
2. **Rückmeldungsprogramm** (`FeedbackSynthesisProgram`):
   - Inputs: `student_text_md`, `criteria`, `analysis_dict`, optional `teacher_instructions_md`.
   - Output: pädagogisch wertvoller Fließtext ohne Listen (angelehnt an docs/research/feedback_science.md).
3. **Adapter**:
   - Bevorzugt DSPy-Structured-Output und setzt `parse_status=parsed_structured`.
   - Fallback auf vorhandene Ollama-/Stub-Pfade bleibt unverändert.
4. **Telemetrie & DX**:
   - Logging (`learning.feedback.*`) zeigt Backend + `parse_status`.
   - Optional: `internal_metadata.parse_status` für interne Auswertungen (kein öffentliches API-Feld).

## Kompatibilität (DSPy 3.0.3)
- Strukturierte Outputs erfordern einen strukturierten Adapter: Wir verwenden `dspy.JSONAdapter`, damit DSPy die OutputFields gemäß Typannotationen parst und validiert.
- OutputFields definieren die Struktur über Typannotationen (z. B. `list[CriterionItem]`), nicht über separate `json_schema`‑Parameter.
- LM‑Konfiguration: `dspy.configure(lm=dspy.LM(f"ollama/{AI_FEEDBACK_MODEL}"), adapter=dspy.JSONAdapter())`. So können wir lokale Ollama‑Modelle nutzen und zugleich strukturierte Ausgaben erzwingen.

## BDD-Szenarien
1. **Happy Path (mit Kriterien)**  
   - Given eine Aufgabe mit Kriterien und optionalen Lösungshinweisen  
   - When der Learning-Worker eine Einreichung verarbeitet  
   - Then `analysis_json` enthält für jedes Kriterium die vom Modell gelieferten Scores/Begründungen, `parse_status=parsed_structured`, `feedback_md` ist Fließtext nach Vorgaben.
2. **Keine Kriterien**  
   - Given eine Aufgabe ohne Kriterien  
   - When der Worker die Einreichung verarbeitet  
   - Then es wird keine Analyse erzeugt (`analysis_json={}`), trotzdem entsteht eine Rückmeldung; `parse_status=skipped`, keine Fehlermeldung für Schüler.
3. **Teilweise fehlerhafte Modellantwort**  
   - Given das Analysemodell lässt Felder (z. B. `max_score`) aus  
   - Then die Normalisierung füllt sinnvolle Defaults ohne auf Stub zurückzufallen, Logging weist auf Normalisierung hin.
4. **Modell- oder Timeout-Fehler**  
   - Given der DSPy-Aufruf schlägt fehl  
   - Then der Worker behandelt es als TransientError (Retry) oder markiert Submission als fehlgeschlagen gemäß bestehender Regeln; es werden keine leeren Rückmeldungen gespeichert.

## Arbeitspakete
0. **Iteration 1 (KISS, umgesetzt)**
   - Parser-/Fallback-Defaults angepasst: Fehlende Kriterien erhalten nun `score=0` (statt 6). Damit entstehen keine fälschlich neutralen Bewertungen ohne Evidenz.
   - Tests ergänzt: Parser-Tests prüfen `score=0` für fehlende Kriterien und deterministische Fallbacks.
   - Keine API-Änderungen; reine Normalisierung, minimales Risiko.

1. **Signaturen & Typen (bereitgestellt)**
   - `backend/learning/adapters/dspy/types.py`: `CriterionResult`, `CriteriaAnalysis` Dataclasses kapseln das strukturierte Payload.
   - `backend/learning/adapters/dspy/signatures.py`: OutputFields annotiert (z. B. `list[CriterionResult]`, `CriteriaAnalysis`), kompatibel zu DSPy 3.0.3 JSONAdapter.
   - Ziel: Der Adapter erhält Python‑Objekte anstatt Freitext‑JSON.

2. **DSPy‑Programme (bereitgestellt, zu finalisieren)**
   - `backend/learning/adapters/dspy/programs.py`: `run_structured_analysis`/`run_structured_feedback` rufen `dspy.Predict(Signature)` auf und liefern strukturierte Daten/Prosa.
   - Weiterhin vorhanden: Legacy‑Runner für den Fallback (einphasige JSON‑Antworten), aber nicht mehr „first choice“.

3. **Option 3 – Strukturierten Pfad erzwingen (dieser Schritt)**
   - Zentrale Konfiguration: Im Worker‑Bootstrap `dspy.configure(lm=dspy.LM(f"ollama/{AI_FEEDBACK_MODEL}"), adapter=dspy.JSONAdapter())` setzen (einmalig beim Start).
   - Modellpolitik: In `.env`/Doku empfehlen wir ein kompatibles Modell (z. B. `llama3.1` oder `qwen2.5:7b-instruct`). Zu kleine Modelle (z. B. `gemma3:4b`) führen häufig zu JSON‑Fallback.
   - „Strict mode“ im Adapter: Wenn der JSONAdapter in den Logics auf „json_object“-Fallback geht, protokollieren wir `parse_status=structured_fallback` und behandeln optional als TransientError (Retry) statt still den Legacy‑Pfad zu nehmen. KISS‑Variante: zunächst nur klares Logging + Metriken.
   - Telemetrie: Zwingend `feedback_backend=dspy`, `parse_status=parsed_structured|structured_fallback|analysis_fallback|analysis_error` loggen.

4. **Tests (TDD)**
   - Unit: Structured‑Happy‑Path (bereits vorhanden) → `parsed_structured` erwartet.
   - Adapter: Test für „structured_fallback“ (simulierter JSONAdapter‑Fallback) → klarer Log‑Eintrag, kein „silent“ Wechsel ohne Sichtbarkeit.
   - Worker‑E2E (lokal): Mock‑DSPy liefert strukturierte Daten → DB ≠ Stub und `parse_status=parsed_structured`.
   - Optional E2E (RUN_OLLAMA_E2E=1): mit kompatiblem Modell; ansonsten skippt der Test.

5. **Validierung & Doku**
   - Make‑Targets/Doku: `make ai-pull-feedback` zieht empfohlenes Modell; `.env.example` verweist auf kompatibles Default.
   - README/Docs: kurzer Abschnitt „Structured Outputs mit DSPy (3.0.3)“ inkl. Troubleshooting („JSONAdapter fallback“ → Model wechseln oder Prompt vereinfachen).

## Definition of Done
- Alle Tests grün (inkl. Worker-E2E).
- Neue strukturierte DSPy‑Ausgaben landen in `analysis_json` / Feedback‑UI ohne Stubs.
- Logs/Telemetry zeigen `feedback_backend=dspy, parse_status=parsed_structured` (kein stiller Legacy‑Fallback mehr).
- Worker initialisiert DSPy global mit `dspy.JSONAdapter` und dem konfigurierten Ollama‑Modell.
- Plan‑Dokument aktualisiert, Code kommentiert (Warum/Wie, Parameter, Berechtigungen).

---

## Ergänzungen: KISS, Wartbarkeit, nächste konkrete Schritte

### Prompting‑Prinzipien (einheitlich, wartbar)
- Evidenz‑Regel (Analyse): „Bewerte jedes Kriterium ausschließlich anhand expliziter Belege im Schülertext. Fehlen Belege → Score 0. Gib eine kurze, objektive Begründung und zitiere die relevante Passage (oder ‚kein Beleg gefunden‘).“
- Trennung von Kontext: Lösungshinweise und Lehrer‑Instruktionen sind nur Kontext für die Analyse, sie fließen nicht in die Bewertung ein und dürfen nicht in der Rückmeldung zitiert werden.
- Rückmeldung als Fließtext: Keine Listen, zwei klar erkennbare Abschnitte in Prosa: „Das hast du gut gemacht …“ und „Das kannst du beim nächsten Mal verbessern …“.
- Datenschutz: Schülertext 1:1 an das LLM, aber niemals im Log speichern; nur anonymisierte/aggregierte Telemetrie.

### Maintainability (KISS)
- Keine separaten Prompt‑Builder mehr: Die Anweisungen leben direkt in den Signature‑Docstrings.
- Zwei Signatures als Single Source of Truth:
  - `CriteriaAnalysisSignature`: Enthält vollständige Instruktion (Evidenz‑Regel, Kontexttrennung, Datenschutz‑Hinweis).
  - `FeedbackSynthesisSignature`: Enthält vollständige Instruktion (pädagogische Prosa, keine Listen, zwei Abschnitte).
- Änderungen am Prompt erfolgen ausschließlich durch Anpassen der Docstrings dieser Signatures; Programmlogik bleibt unverändert.
- Tests prüfen Verhalten (strukturierte Ausgaben, Prosa‑Feedback), nicht exakte Wortlaute.

### Actionable Checklist (Iteration 2 – Struktur erzwingen, minimal invasiv)
1) Worker‑Bootstrap: DSPy global konfigurieren
   - Datei: `backend/learning/workers/process_learning_submission_jobs.py`
   - Einmalig beim Start: `dspy.configure(lm=dspy.LM(f"ollama/{AI_FEEDBACK_MODEL}"), adapter=dspy.JSONAdapter())`.
   - Log beim Start: `learning.feedback.dspy_configured model=... adapter=JSONAdapter`.
2) Adapter‑Pfad bevorzugt strukturiert
   - Datei: `backend/learning/adapters/dspy/feedback_program.py`
   - Reihenfolge: structured → legacy‑json → stub. Setze `parse_status=parsed_structured` bei Erfolg; `structured_fallback` bei Adapter‑Fallback.
3) Evidence‑Defaults
   - Datei: `backend/learning/adapters/local_feedback.py` (bzw. Normalisierer)
   - Wenn ein Kriterium fehlt/leer → `score=0`, `explanation_md="kein Beleg gefunden"`.
4) Telemetrie verschärfen
   - Einheitliche Log‑Keys: `feedback_backend`, `parse_status`, `program=analysis|feedback`, `duration_ms`.
   - Bei `structured_fallback` klarer Hinweis im Log; optional Retry‑Signal (vorerst nur Logging/Kennzahl).
5) Make‑Targets und Doku
   - `make ai-pull-feedback` zieht empfohlenes Modell (z. B. `qwen2.5:7b-instruct` oder `llama3.1`), Vision bleibt separat.
   - `.env.example`/Docs aktualisieren: `AI_FEEDBACK_MODEL`, `AI_VISION_MODEL=qwen2.5vl:3b` (ohne Bindestrich), Hinweise zu kleinen Modellen (JSON‑Fallback).

### Tests (präzise, minimal)
- Unit (structured happy): `backend/tests/learning_adapters/test_feedback_program_dspy_structured.py`
  - Erwartet `parse_status=parsed_structured`, korrektes Mapping der Criteria.
- Unit (fallback sichtbar): `.../test_feedback_program_dspy_structured.py::test_structured_fallback_logs`
  - Simulierter JSONAdapter‑Fallback → `parse_status=structured_fallback` geloggt; kein Silent‑Success.
- Parser‑Normalisierung: bereits vorhanden, ergänzt um „kein Beleg gefunden“.
- Worker‑E2E (lokal, mock DSPy): `backend/tests/test_learning_worker_e2e_local.py`
  - Analysen landen in DB, Feedback ist Prosa, kein Stub, `parse_status=parsed_structured`.
- Akzeptanzfall: Text „Ich habe keine Ahnung …“
  - Erwartung: Alle Kriterien `score=0`, Erklärungen verweisen auf fehlende Evidenz; Feedback ist empathische Prosa mit Verbesserungshinweisen.

### Risiken & Abfederung
- Risiko: Kleinere Modelle verfehlen strukturierte Ausgaben → `structured_fallback`.
  - Maßnahme: Sichtbares Logging, Make‑Target zum Model‑Pull, Doku‑Hinweise; optional später Retry/Backoff.
- Risiko: Prompt‑Drift
  - Maßnahme: Zentrale Prompt‑Builder + Verhaltenstests statt String‑Vergleiche.

### Abschlusskriterien ergänzt
- Sichtbarer Nachweis im Log innerhalb von 10 Minuten nach Neustart: `learning.feedback.dspy_configured`.
- Manuelle Einreichung zeigt in DB `internal_metadata->>'parse_status' = 'parsed_structured'` und realistische `analysis_json`.
