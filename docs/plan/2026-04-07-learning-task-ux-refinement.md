# Lernaufgaben in der Inhaltsansicht verfeinern

## Zusammenfassung
- Die Schüler-Aufgabenkarte wird so nachgeschärft, dass sie didaktisch klarer und technisch konsistenter funktioniert.
- `Letzter Versuch` bleibt der zentrale Verlaufsblock mit Tabs `Abgabe`, `Rückmeldung` und `Auswertung`.
- `Rückmeldung einholen` und `Endgültig abgeben` erzeugen beide eine KI-Rückmeldung und die vollständige Auswertung.
- `feedback` zählt nicht gegen `max_attempts`; nur `submit` verbraucht einen finalen Versuch.

## Wichtige Änderungen
- **Frontend-Aufgabenkarte**
  - `Auswertung` zeigt die echten `criteria_results` aus `analysis_json` vollständig inline.
  - `Weitere Versuche` zeigt weiterhin nur frühere Abgaben, ohne Rückmeldung und Auswertung.
  - Der Pending-Hinweis für Feedback/finale Abgabe sitzt im Block `Letzter Versuch`.
  - Während ein Feedback-/Analyse-Durchlauf läuft, bleibt der Editor sichtbar, aber gesperrt.
  - Nach `Rückmeldung einholen` bleibt der Editor offen und gesperrt.
  - Nach `Endgültig abgeben` schließt der Editor; der Status und das Ergebnis erscheinen im Verlaufsblock.
  - Nach Abschluss erscheint wieder der CTA `Erneut bearbeiten`, solange keine Limits greifen.

- **Submission-Semantik**
  - `intent=feedback` erzeugt weiterhin einen Submission-Datensatz und Analysejob, zählt aber nicht gegen das finale Versuchslimit.
  - `intent=submit` zählt gegen `max_attempts`.
  - Der API-Vertrag in `api/openapi.yml` dokumentiert diese Semantik explizit.
  - Es gibt keine Schema- oder Migrationsänderung.

## Testplan
- **Frontend**
  - `LearningTaskCard.test.ts`
    - `Auswertung` rendert vollständige Kriterien mit Erklärung.
    - Pending-Zustand erscheint im Block `Letzter Versuch`.
    - Während Pending sind Editor und Aktionen gesperrt.
    - Nach finaler Abgabe ist der Editor geschlossen; nach Feedback bleibt er sichtbar.
    - Frühere Versuche zeigen nur Abgaben.
- **Frontend-Route**
  - `page.server.test.ts`
    - `feedback` bleibt lokal und hält den Editor-Kontext offen.
    - `submit` signalisiert der Seite, den Editor nach dem Request zu schließen.
- **Backend/API**
  - `test_learning_api_contract.py`
    - Feedback-Anfragen erhöhen den finalen Versuchszähler nicht.
    - `max_attempts` wird nur durch finale Abgaben ausgeschöpft.
    - Die bestehende Idempotenz bleibt erhalten.

## Annahmen
- `Endgültig` bedeutet didaktisch „bewusst abgegeben“, nicht automatisch „nie wieder bearbeitbar“.
- Neue Bearbeitungen bleiben erlaubt, solange `max_attempts` für finale Abgaben nicht erreicht ist.
- `feedback` bleibt ein echter Snapshot mit Analyse, aber kein final zählender Versuch.
