# Plan: Learning Feedback UI & DSPy Prompt Hardening

Datum: 2025-11-10  
Autor: Codex (mit Felix)  
Status: Abgeschlossen (2025-11-09)

## Kontext / Problem
- **Stub-Auswertung:** Trotz aktiver DSPy-Pipeline zeigen die Karten „Auswertung“ weiterhin die generischen Defaults (Score 6/10, „Bezug zum Kriterium …“). Log-Auszüge (`feedback_backend=dspy`) und DB-Dumps (z. B. submission `497da435-94e1-5c47-9887-14eb42c06a7e`) belegen, dass `_parse_to_v2` zwar JSON parst, aber für jedes fehlende Feld die Fallback-Werte einsetzt.
- **Rückmeldung-Darstellung:** Die Markdown-Ausgabe landet unverändert im `<section class="analysis-feedback">`. Ohne Struktur (Überschrift, Absätze, Bullet-Komponenten) wirkt der Block wie „Stub-Text“, auch wenn der Inhalt echt ist.
- **Analysefortschritt-Karte:** `_render_submission_telemetry` erzeugt immer den Block „Analysefortschritt“ mit Versuchszählern. Für Schüler:innen ist das redundant und lenkt vom Feedback ab.
- **Aufgaben ohne Kriterien:** `dspy.feedback_program.analyze_feedback` beendet sich mit einem Hinweis „Bitte Kriterien definieren …“, sobald `criteria` leer ist (siehe unit `8414091c-3a09-4fe6-a510-36d45eeeb449`, task `229ec4cd-de53-4d9d-a78d-b70eee1fbec3`). Damit erhalten Schüler:innen überhaupt keine Rückmeldung, obwohl die Aufgabe bewusst frei formuliert ist.

## Ziel(e)
1. Auswertungskarten zeigen echte Modell-Scores/-Erklärungen statt Default-Platzhalter.
2. Die Rückmeldung wird als kurzer Fließtext (keine Listen) gerendert und unterscheidet sich klar von Stub-Texten.
3. Die Karte „Analysefortschritt“ verschwindet vollständig aus der Lernenden-Ansicht.
4. Aufgaben ohne Kriterien liefern trotzdem sinnvolles Feedback (Analyse ggf. leer, Feedback vorhanden).

## User Stories
- Als Schülerin möchte ich nach dem Absenden meiner Lösung reale Kriterienbewertungen sehen, damit ich nachvollziehen kann, was gut lief und wo ich nachbessern muss.
- Als Lehrer möchte ich Aufgaben auch ohne definierte Kriterien einsetzen können, ohne dass meine Schüler:innen Fehlermeldungen sehen.
- Als Produktverantwortlicher möchte ich nachvollziehen können, wie der Prompt aufgebaut ist, um gezielt an der AI-Qualität zu arbeiten.

## BDD-Szenarien
1. **DSPy liefert strukturierte Kriterien**
   - Given eine Aufgabe mit fünf Kriterien,
   - When die Worker-Pipeline den DSPy-Analyse-Call ausführt,
   - Then wird pro Kriterium ein Score + Begründung aus dem Modell übernommen (keine Default-Werte).
2. **Feedback-Block bleibt lesbar**
   - Given eine Submission mit Markdown-Feedback,
   - When das History-Fragment gerendert wird,
   - Then erscheint der Text als kurzer Fließtext innerhalb der Card-Komponente und kollidiert nicht mit HTMX-Layout.
3. **Analysefortschritt ausgeblendet**
   - Given eine Submission (egal welcher Status),
   - When das History-Fragment geladen wird,
   - Then enthält die Karte keine „Analysefortschritt“-Sektion mehr.
4. **Kein Kriterium → trotzdem Feedback**
   - Given eine Aufgabe ohne Kriterien,
   - When der Lernende eine Antwort abgibt,
   - Then speichert der Worker kein Auswertungsobjekt (leeres JSON `{}`) und erzeugt dennoch eine Rückmeldung ohne Fehlercode.
5. **Prompt-Dokumentation**
   - Given ein Product Manager fragt nach dem Aufbau,
   - When wir in die Docs schauen,
   - Then finden wir eine leicht verständliche Beschreibung der Analyse- und Feedback-Prompts (inkl. Input/Output-Felder).

## Technischer Ansatz
1. **Prompt-/DSPy-Härtung**
   - Dokumentiere den aktuellen Aufbau (`_build_analysis_prompt`, `_build_feedback_prompt`) inkl. Eingaben/Ausgaben im Plan + ggf. `docs/`.
   - Ersetze die freien JSON-Prompts durch echte DSPy-Signaturen & Programme, die `dspy.OutputField`s verwenden. Damit erzwingt DSPy strukturiertes JSON (Analysis) bzw. Markdown (Feedback).
   - Übergib dem Feedback-Adapter zusätzlich die Aufgabenstellung (`instruction_md`) und optionalen Lösungshinweise (`hints_md`) über die Job-Payload; der Worker reicht diese Felder nur an Adapter weiter, die sie unterstützen (introspektiv, abwärtskompatibel).
   - Passe `_parse_to_v2` an, damit fehlende Items den Parse-Status (`analysis_missing_items`) setzen und Telemetrie bessere Hinweise liefert.
   - Tests (erst rot): `backend/tests/learning_adapters/test_feedback_program_dspy.py` angepasst: „ohne Kriterien → Analysis = {} (leer), Feedback vorhanden“.
2. **UI-Überarbeitung**
   - Entferne `_render_submission_telemetry` aus `HistoryEntry.status_html` (oder leere Ausgabe), passe Tests (`backend/tests/test_learning_ui_student_submissions.py`).
   - `analysis-feedback`: LLM-Anweisung auf Fließtext (keine Listen) vereinheitlicht Darstellung.
   - Falls nötig, ergänze Frontend-Snippet-Tests (Snapshot) für neue Struktur.
3. **Kriterien-Optionalität**
   - Passe `analyze_feedback` an: Wenn `criteria` leer, führe trotzdem Analyse + Feedback aus (z. B. ersetze Liste temporär durch `[ "Gesamteindruck" ]` für den Prompt, entferne sie vor Persistenz oder markiere `analysis_json` explizit als leer).
   - Teste Worker-E2E mit `criteria=[]` (neuer Fall in `backend/tests/test_learning_worker_e2e_local.py`).
4. **Manuelle Prüfung**
   - Repliziere die letzte Aufgabe (`unit 8414..., task 229e...`) lokal, bestätige via DB und UI, dass Feedback jetzt ohne Kriterien erstellt und angezeigt wird.

## Deliverables
- Aktualisierte DSPy-Programme/Prompts + Tests.
- Überarbeitete UI-Komponenten ohne Analysefortschritt-Karte.
- Worker-/Adapter-Änderungen inkl. Tests (unit + E2E).
- Dokumentation des Prompt-Aufbaus (Plan + ggf. `docs/learning_feedback.md`).

## Tests & Checks
- `.venv/bin/pytest backend/tests/learning_adapters -k dspy`
- `.venv/bin/pytest backend/tests/test_learning_worker_e2e_local.py -k feedback`
- `.venv/bin/pytest backend/tests/test_learning_ui_student_submissions.py`
- Visueller Check im Browser (`/learning/courses/.../units/8414...`).
