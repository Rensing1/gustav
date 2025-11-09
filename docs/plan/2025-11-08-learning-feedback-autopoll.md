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
- ⏳ Logging & DSPy (Schritte 1 & 2): Noch offen – `_parse_to_v2` loggt weiterhin nicht, Structured-Output-Pfade fehlen, Worker-E2E persistiert Stub-Feedback.
- ⏳ Regressionstests (Schritt 4): Bisher nur das UI-Teilziel getestet; Worker-E2E folgt, sobald DSPy-Anpassungen implementiert sind.

## Schritte (offen)
1. Logging & Diagnostics
   - `_parse_to_v2`: anonymisierten Ausschnitt des Modelloutputs loggen, wenn JSON-Parsing scheitert.
   - Worker-Log-Dashboard anreichern (`feedback_backend=dspy`, `parse=failed|ok`).

2. DSPy Structured Output
   - Neue Module `backend/learning/adapters/dspy/signatures.py`, `.../programs.py`.
   - Tests: Parser akzeptiert reale DSPy-Ergebnisse, Worker-E2E prüft `feedback_md` ungleich Stub.

3. Regressionstests
   - Unit + E2E: `pytest -k learning_ui` + Worker.
   - Manuelle Verifikation (lokale Submission, Polling beobachten, DB-Eintrag prüfen).
