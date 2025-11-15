# Plan: Learning History Autorefresh + DSPy Feedback Parsing

Datum: 2025-11-08  
Autor: Codex (mit Felix)  
Status: In Arbeit

## Kontext / Problem
- **UI:** Die Lern-Historie pollt alle 2 s solange der neueste Versuch `analysis_status ∈ {pending, extracted}` ist. `_build_history_entry_from_record` setzt `<details open>` nur anhand des Query-Parameters `open_attempt_id` (oder automatisch für den neuesten Eintrag). Öffnet der Nutzer beim Polling manuell einen älteren Versuch, verschwindet dessen `open`-Attribut sofort nach dem nächsten Refresh → Rückmeldungen lassen sich nicht mehr vollständig lesen.
- **Feedback:** Worker-Logs zeigen `feedback_backend=dspy`, in der Datenbank landen aber weiterhin die deterministischen Stub-Texte (`**Rückmeldung** … Stärken: klar benannt …`). Die `criteria_results` enthalten ebenfalls die Default-Werte (Score 6, Standard-Erklärung). Ursache: `_parse_to_v2` erhält Modelltexte, die nicht als JSON parsebar sind, und fällt deshalb auf den Fallback zurück. Ohne zusätzliche Logs ist unklar, welche Antworten DSPy/Ollama liefern.

## Ziel(e)
1. Nutzer:innen können während des Pollings einen beliebigen Versuch geöffnet lassen; die UI respektiert diese Auswahl trotz automatischer Refreshes.
2. Der DSPy-Pfad übernimmt echte Modellantworten (Markdown + criteria.v2). Wir bekommen Telemetrie, warum Parsing fehlschlägt, und schreiben nur noch fallback-Feedbacks, wenn wirklich kein Modell-Output vorliegt.

## User Story
Als Schülerin möchte ich, dass mein ausgewählter Versuch offen bleibt, selbst wenn GUSTAV im Hintergrund weitere Ergebnisse nachlädt, damit ich die AI-Rückmeldung komplett lesen kann.

Als Lehrkraft möchte ich echte, kriteriumsbasierte Hinweise sehen, sobald DSPy aktiviert ist, damit ich Verläufe nachvollziehen und Vertrauen in die KI gewinnen kann.

## BDD-Szenarien
1. **UI – Nutzer öffnet älteren Versuch**
   - Given `analysis_status` des neuesten Versuchs ist `pending` und HTMX pollt das History-Fragment,
   - When der Student klickt einen älteren Versuch auf,
   - Then bleibt genau dieser `<details>`-Block nach jedem Poll offen (und die Polling-Logik unterdrückt kein Feedback).

2. **UI – Polling endet**
   - Given der neueste Versuch wechselt von `pending` zu `completed`,
   - When der nächste Refresh ausgelöst wird,
   - Then wird der Polling-Timer deaktiviert und der zuletzt geöffnete Versuch bleibt offen.

3. **DSPy – Modell liefert JSON**
   - Given `dspy` liefert gültiges JSON inkl. `feedback_md`,
   - When `analyze_feedback` läuft,
   - Then `feedback_md` und `analysis_json` in `learning_submissions` entsprechen der Modellantwort (keine Stub-Texte).

4. **DSPy – Modell liefert Fließtext**
   - Given das Modell antwortet mit reinem Markdown/Prosa (kein JSON),
   - When `_parse_to_v2` ausgeführt wird,
   - Then wird die Antwort mit `json_repair` (oder DSPy-Structured Output) in `criteria.v2` transformiert oder ein Warn-Log mit anonymisiertem Ausschnitt geschrieben, bevor der Fallback greift.

5. **Telemetry – Parsingfehler sichtbar**
   - Given `_parse_to_v2` scheitert,
   - When der Fallback triggert,
   - Then erscheint ein strukturiertes Log `learning.feedback.dspy_parse_failed` mit abgeschnittenem Modell-Output (PII-frei), um das Problem in Ops zu debuggen.

## Technischer Ansatz
- **UI**
  - Clientseitig tracken, welcher `<details>`-Block zuletzt geöffnet wurde (z. B. per JS-Hook oder `hx-trigger="toggle"`-Event ⇒ `hx-vals` mit `open_attempt_id=<ID>`).
  - Beim nächsten Poll die ID des offenen Blocks an den Server senden, damit `_build_history_entry_from_record` denselben Eintrag mit `open` rendert.
  - Optional: Während Polling und `open_attempt_id != latest_id` `hx-trigger` pausieren, bis der Nutzer wieder den jüngsten Versuch öffnet (verhindert Flackern).

- **DSPy**
  - Kurzfristig: `_parse_to_v2` logging erweitern, um klar zu sehen, welches Payload nicht parsebar ist.
  - Mittel-/Langfristig: DSPy Programme (`signatures.py`, `programs.py`) nutzen Structured Output, damit das Modell garantiert JSON liefert (DSPy `dsp.Type` + `dspy.ChainOfThought`), statt per `_lm_call` rohes Markdown zu generieren.
  - Tests erweitern: Worker-E2E liest `feedback_md` aus DB und prüft, dass es nicht mit dem Stub-Text identisch ist, sobald `dspy` gemockt wird.

## Fortschritt (Stand 2025-11-08)
- ✅ UI-Persistenz (Schritt 3): History-Fragment und TaskCard rendern jetzt `data-submission-id`, `data-open-attempt-id`, `hx-vals` und den gemeinsamen `hx-on`-Handler. `gustav.js` speichert beim Toggle die geöffnete Submission-ID, sodass Polling denselben Versuch offen lässt. Unit-Test `backend/tests/test_learning_ui_auto_refresh.py` deckt die neue Struktur ab und läuft grün.
- ✅ Logging & DSPy (Schritte 1 & 2): `_parse_to_v2` loggt jetzt anonymisierte Modellantworten bei JSON-Fehlern (`learning.feedback.dspy_parse_failed`), `FeedbackResult.parse_status` landet im Adapter-Log, und die neuen Module `backend/learning/adapters/dspy/{signatures,programs}.py` kapseln den strukturierten Output. Worker-E2E schreibt die DSPy-Markdown-Ausgabe unverändert in die DB (kein Stub mehr).
- ✅ Zwei-Phasen-DSPy: `feedback_program` ruft nun zuerst `_run_analysis_model` (liefert strukturiertes `criteria.v2`), normalisiert das Ergebnis und übergibt es an `_run_feedback_model`, damit die sprachliche Rückmeldung immer auf derselben Analyse basiert. Neue Signaturen (`FeedbackSynthesisSignature`), Programme (`FeedbackSynthesisProgram`) sowie Parser- und Worker-Tests sichern die Pipeline. Telemetrie differenziert `analysis_fallback`, `feedback_fallback` usw.
- ✅ Zielgerichtete Regressionstests: `pytest backend/tests/learning_adapters/test_feedback_program_dspy_parser.py`, `backend/tests/learning_adapters/test_feedback_program_dspy.py` und der Worker-E2E (`pytest backend/tests/test_learning_worker_e2e_local.py -k dspy`) laufen grün.
- ✅ Breitere Regression (Schritt 4): Komplette Test-Suite (`.venv/bin/pytest -q -rs`) inkl. UI- und Worker-Szenarien sowie die optionalen Ollama/Supabase/Keycloak-E2Es liefen grün (Vision-Test nutzt jetzt `qwen2.5vl:3b`). Manuelle Verprobung erfolgt beim nächsten Deploy wie gewohnt.

## Schritte (offen)
_(keine – Plan abgeschlossen; manueller Check findet im nächsten regulären Deploy-Slot statt)._

## Erweiterungsplan: DSPy als echter Zwei-Phasen-Prozess

Ziel: Auswertung (Kriterienanalyse) und Rückmeldung (sprachliche Empfehlung) getrennt über DSPy laufen lassen, jeweils mit eigenen Signaturen/Modulen und echten `dspy.OutputField`s, damit strukturierte Antworten nicht mehr „per Prompt“ erzwungen werden müssen.

### User Story
Als Lehrkraft möchte ich, dass GUSTAV zuerst eine nachvollziehbare Analyse („welches Kriterium bekommt welchen Score?“) erstellt und erst anschließend eine sprachliche Rückmeldung generiert, die sich eindeutig auf diese Analyse bezieht. So kann ich jede Phase separat prüfen und im Fehlerfall gezielt optimieren.

### BDD-Szenarien (Auszug)
1. **Analyse getrennt von Feedback**
   - Given eine Submission mit drei Kriterien,
   - When das DSPy-Analyseprogramm läuft,
   - Then entsteht ein JSON mit `criteria_results`, das von der Feedback-Phase unverändert übernommen wird.
2. **Feedback nutzt Analyse**
   - Given eine vorhandene Analyse mit Scores und Begründungen,
   - When das DSPy-Feedbackprogramm aufgerufen wird,
   - Then verweist der erzeugte Markdown-Text auf konkrete Kriterien und Scores (z. B. „Inhalt: 8/10 …“).
3. **Fallback pro Phase**
   - Given die Analyse liefert kein valides JSON,
   - When der Worker fortfährt,
   - Then wird nur die Analyse mit Defaults ersetzt, während die Feedback-Phase trotzdem einen Text erzeugt (basierend auf den Ersatzdaten).

### Technische Umsetzung
1. **Signaturen**
   - `FeedbackAnalysisSignature` bleibt bestehen, erhält aber echte DSPy-Felder (Input `student_text_md`, `criteria`; Output `criteria_results_json` + optional `analysis_log`).
   - Neue `FeedbackSynthesisSignature` (Input: `analysis_json`, `student_text_md`; Output: `feedback_md`, `hints_md`).
2. **Programme/Module**
   - `backend/learning/adapters/dspy/programs.py` erweitert zu zwei Modulen:
     1. `CriteriaAnalysisProgram` (ruft LLM, erzwingt JSON über DSPy OutputFields).
     2. `FeedbackSynthesisProgram` (separater Prompt für sprachliche Hinweise).
   - Beide Programme kapseln die LM-Aufrufe; Tests können jeden Runner separat mocken.
3. **Adapter-Pipeline**
   - `local_feedback._LocalFeedbackAdapter.analyze` ruft zuerst Analyseprogramm, normalisiert Ergebnis (`criteria.v2`), speichert es.
   - Anschließend ruft es das Feedbackprogramm mit dem normalisierten JSON, damit Rückmeldungen garantiert auf den endgültigen Werten basieren.
   - Telemetrie unterscheidet `analysis_parse_status` und `feedback_parse_status`.
4. **Tests**
   - Unit-Tests für beide Programme (jeweils JSON-Passthrough, Logging).
   - Integrationstest: DSPy-Analyse liefert Werte, Feedbackprogramm referenziert sie (assert auf Markdown-Inhalt).
   - Worker-E2E erweitert: sowohl Analyse- als auch Feedback-Phase werden verifiziert (DB enthält analysierte Kriterien + referenzierende Rückmeldung).
5. **Migration/Docs**
   - Keine Schemaänderung nötig, aber `docs/ARCHITECTURE.md` + Plan-Dokument aktualisieren (Beschreibung der Zwei-Phasen-Verarbeitung).
   - `.env`-/README-Hinweis: Für echte DSPy-Läufe müssen beide Module aktiviert sein (`AI_BACKEND=local`, `AI_FEEDBACK_MODEL`, `OLLAMA_BASE_URL` gesetzt, `dspy-ai` installiert).

### Rollout-Strategie
1. Direktes Austauschen der Pipeline (Ein-Phasen-Variante entfernen, sobald zwei Phasen implementiert und getestet sind).
2. Nach erfolgreichem Testlauf UI/Worker-Dokumentation aktualisieren und Deploy durchführen.
