# GUSTAV Plan — 2025-11-06 — PDF Submission Pipeline QC Improvements

## Kontext
- Schüler reichen Aufgaben zunehmend als PDF ein. Die bestehende Pipeline (Upload → PDF-zu-Bild → Preprocessing → Vision → Feedback → UI) ist funktional, aber Testabdeckung für Preprocessing und UI-Rückmeldung nach AI-Feedback ist lückenhaft.
- Felix benötigt nachvollziehbare Tests, damit Lehrkräfte und Lernende auf reproduzierbare Ergebnisse vertrauen können.
- Clean Architecture, DSGVO-Konformität und FOSS-Lesbarkeit bleiben oberste Leitprinzipien.

## Ziele
1. Vertraglich festhalten, welche Status- und Fehlercodes die PDF-Pipeline liefert (OpenAPI + Migration-Entwurf).
2. TDD für Preprocessing-Kantenfälle (mehrseitige PDFs, defekte Dateien, zu große Dateien).
3. Sicherstellen, dass die Schüler-UI nach Abschluss der Analyse Feedback und Seitenvorschauen rendern.

## User Story
- Als verantwortliche*r Lehrer*in möchte ich, dass eine von Schüler*innen hochgeladene PDF-Abgabe zuverlässig durch alle Verarbeitungsschritte (Upload, Konvertierung, Analyse, Feedback) läuft und der aktuelle Zustand jederzeit korrekt im UI sichtbar ist, damit ich Rückmeldungen geben kann und Schüler*innen wissen, ob ihre Abgabe erfolgreich verarbeitet wurde oder noch Aufmerksamkeit braucht.

## BDD-Szenarien
- *Given* eine berechtigte Schüler-Sitzung mit freigeschalteter Aufgabe, *when* der/die Schüler*in ein gültiges PDF unterhalb der Größenbegrenzung hochlädt und einreicht, *then* der Server speichert den Upload-Metadatensatz, stößt die PDF-Vorverarbeitung an, setzt `analysis_status=pending` und legt einen Worker-Job an.
- *Given* eine berechtigte Schüler-Sitzung, *when* der/die Schüler*in ein PDF oberhalb des erlaubten Limits einreicht, *then* der Server lehnt die Anfrage mit `400` ab und kein Job wird erzeugt.
- *Given* eine pending PDF-Abgabe mit gültigem Speicher-Objekt, *when* die PDF-zu-Bild-Konvertierung fehlschlägt (z. B. defekte Datei), *then* der Vorverarbeitungs-Use-Case markiert die Abgabe mit `analysis_status=failed` und `error_code=input_corrupt`, speichert keinen Page-Preview und löscht den Job.
- *Given* eine pending PDF-Abgabe, *when* der Renderer meldet einen nicht unterstützten Inhalt (z. B. verschlüsselte PDF), *then* der Fehler wird als `input_unsupported` aufgezeichnet und der Worker erzeugt kein Folge-Feedback.
- *Given* eine Abgabe in Status `extracted` mit gespeicherten Page-Previews, *when* der Vision-Adapter den Text erfolgreich extrahiert, *then* der Worker füllt `text_body`, ergänzt `analysis_json` und ruft den Feedback-Adapter auf.
- *Given* eine Abgabe in Status `extracted`, *when* der Vision-Adapter transient fehlschlägt, *then* der Worker plant einen Retry (Job bleibt offen, `attempt_nr` erhöht sich) und `analysis_status` bleibt `extracted`.
- *Given* eine Abgabe in Status `extracted`, *when* der Vision-Adapter permanent fehlschlägt (z. B. unlesbares Bild), *then* die Abgabe wird mit `analysis_status=failed` und passendem `error_code` markiert und der Job entfernt.
- *Given* Vision-Ergebnis vorhanden, *when* der Feedback-Adapter Text und Kriterien verarbeitet, *then* `feedback_md` und `analysis_json` enthalten ein vollständiges `criteria.v2`-Objekt mit Scores und Erklärungen.
- *Given* eine Abgabe mit Status `completed`, *when* der/die Lehrer*in oder Schüler*in die Aufgaben-Historie aufruft, *then* das UI zeigt Page-Previews, extrahierten Text, Feedback und Datum sortiert nach Versuch.
- *Given* eine Abgabe mit Status `failed` und `error_code=input_corrupt`, *when* der/die Schüler*in die Historie öffnet, *then* das UI zeigt eine verständliche Fehlermeldung und markiert, dass kein Feedback verfügbar ist.

## Nicht-Ziele
- Keine neue Feature-Flag-Logik oder Umgebungssonderwege.
- Kein opt-in/slow Test: alle Tests müssen im regulären Suite-Lauf green werden.
- Keine Performance-Optimierung der Vision-/Feedback-Adapter (nur Tests & minimaler Code zum Green werden).

## Work Items
1. **Contract-First** — *abgeschlossen*
   - `api/openapi.yml` enthält `analysis_status=extracted` und alle `input_*` Fehlercodes (siehe Zeile 874).
   - Migration `20251106185006_learning_worker_accept_input_codes.sql` erweitert Constraint & `learning_worker_update_failed`, Supabase `migration up` bereits gelaufen.
2. **TDD Preprocessing** — *abgeschlossen*
   - Szenarien (Happy Path, korrupt, oversize) liegen in `backend/tests/test_learning_pdf_preprocessing_usecase.py`.
   - Use Case `PreprocessPdfSubmissionUseCase` minimal umgesetzt (Statuswechsel + Storage-Persistenz).
3. **Worker/Repo Anbindung** — *abgeschlossen*
   - Neuer Test `backend/tests/test_learning_worker_error_codes.py` prüft, dass `learning_worker_update_failed` die `input_*` Codes akzeptiert.
   - `DBLearningRepo.list_submissions` liefert `vision_last_error`/`feedback_last_error` mit, sodass UI Fehlerdetails rendern kann.
4. **TDD UI Update** — *abgeschlossen*
   - `backend/tests/test_learning_ui_student_submissions.py::test_ui_history_shows_pdf_failure_message` deckt Fehlermeldung + Code in der Historie ab.
   - SSR-Historie (`backend/web/main.py`) stellt `analysis-error` Abschnitt mit Fehlercode & sanitisiertem Detailtext dar.
5. **Dokumentation & Review** — *offen*
   - Docstrings/Inlinedoku für Preprocessing/Worker nachziehen; Review-Notizen (Fehlercode-Mapping für Nutzertext) noch ausstehend.
6. **Submission Flow QA** — *abgeschlossen*
   - UI-Submit-Tests erzwingen `ok=submitted` im Redirect, sodass API-Fehler nicht mehr still bleiben.
   - Worker-E2E nutzt echte Ollama/DSPy-Adapter, sobald `RUN_OLLAMA_E2E` und `RUN_OLLAMA_VISION_E2E` gesetzt sind; fehlende Dienste führen zu reproduzierbaren Testfehlern.

## Risiken & Gegenmaßnahmen
- **Konvertierungs-Abhängigkeiten**: Wir mocken die kostspielige PDF→Image-Konvertierung deterministisch.
- **RLS/Policies**: Tests laufen gegen echte Test-DB mit bestehenden Policies; Setup muss Anmeldedaten korrekt nutzen.
- **UI-Tests Flakiness**: Verwenden wir SSR-HTML-Assert mit klaren Selektoren/Marker-Klassen.

## Tests
- `.venv/bin/pytest -q backend/tests/test_learning_preprocessing_pdf_cases.py`
- `.venv/bin/pytest -q backend/tests/test_learning_ui_pdf_feedback_display.py`
- Relevante bestehende Suites (`backend/tests/test_learning_pdf_processing_hook.py` etc.) sicher grün nach Anpassungen.
