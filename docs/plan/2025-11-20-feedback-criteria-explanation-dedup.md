# Ticket: Duplicate „Bezug“-Texte in criteria.v2-Auswertung entfernen

## User Story
Als Lernender möchte ich in der Aufgaben-Historie je Kriterium nur eine klare Überschrift sehen und darunter eine knappe Begründung, damit die Auswertung nicht doppelt wirkt und ich schneller verstehe, was verbessert werden muss.

## BDD-Szenarien (Given-When-Then)
- Happy Path – Erklärung vorhanden: Given eine criteria.v2-Auswertung mit `explanation_md="Kein Beleg gefunden."`, When der Parser normalisiert und die UI rendert, Then wird die Erklärung ohne angehängtes „(Bezug: …)“ angezeigt und der Titel steht nur in der Überschrift.
- Edge – Erklärung leer: Given ein Kriterium ohne `explanation_md`/`explanation`, When normalisiert wird, Then erhält es die Standard-Erklärung „Kein Beleg im Schülertext gefunden.“ und kein „(Bezug: …)“.
- Edge – Modell wiederholt Kriterium bereits: Given `explanation_md` enthält schon den Kriteriumsbezug (z.B. „Fehlt Bezug zum Risiko …“), When normalisiert wird, Then bleibt der Text unverändert (keine weitere Dopplung).
- Fehlerfall – Score fehlt: Given ein Kriterium ohne Score, When gerendert, Then wird nur der Titel + Erklärung gezeigt (Badge entfällt), ohne Zusatztext.
- Regression – UI: Given die History-Fragment-Route liefert criteria.v2, When gerendert, Then erscheint kein „(Bezug:“ in der Explanation und der Titel ist nicht doppelt enthalten.

## API / OpenAPI
- Keine Vertragsänderung: bestehender Endpunkt liefert weiterhin `analysis_json` im Schema `criteria.v2`; nur der Inhalt von `explanation_md` wird angepasst (keine Duplication).

## Datenbank / Migration
- Keine Schemaänderung notwendig; Persistenzfeld `analysis_json` bleibt unverändert.

## Testplan (TDD)
1) Pytest ergänzen (bestehender UI-Test `test_ui_history_fragment_renders_criteria_v2_badges_accessible`) um Assertion, dass `explanation_md` kein „(Bezug:“ enthält und der Kriteriumsname nicht 1:1 wiederholt wird.
2) (Optional separater Unit-Test für Parser) – vorerst UI-sichtbarer Test ausreichend, da Ziel das gelieferte Fragment ist.
3) Implementierung: Normalisierungslogik in `backend/learning/adapters/dspy/feedback_program.py` so anpassen, dass keine automatische „(Bezug: …)“-Anfügung passiert; Default: „Kein Beleg im Schülertext gefunden.“.
4) Tests laufen lassen: `.venv/bin/pytest -q backend/tests/test_learning_ui_student_submissions.py::test_ui_history_fragment_renders_criteria_v2_badges_accessible`.

## Risiken / Annahmen
- Annahme: UI zeigt weiterhin Titel separat, daher Entfernen der Zusatzkette ist UX-gewünscht.
- Risiko: Andere Konsumenten von `analysis_json` erwarten den Bezugstext; aktueller Scope beschränkt sich auf Lernenden-UI. Beobachten, ob Lehrer-Views ebenfalls betroffen sind (hier kein Zusatz bekannt).
