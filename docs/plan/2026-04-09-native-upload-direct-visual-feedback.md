# Lernraum: Native Datei-Uploads direkt über das visuelle Modell auswerten

## Reparaturplan – 2026-04-09 15:15

- Problem:
  - `native`-Aufgaben erlauben heute Text oder Upload.
  - Datei-Uploads laufen aber technisch über `upload -> OCR -> textbasierte Auswertung -> Rückmeldung`.
  - Das ist für lange Handschrift hilfreich, verliert aber bei Diagrammen, Mindmaps und kreativen Darstellungen relevante visuelle Information.
- Zielbild:
  - `native + Text` bleibt textbasiert.
  - `native + Datei/Bild` wird direkt durch das visuelle Modell ausgewertet.
  - Der OCR-Schritt entfällt für neue `native`-Upload-Submissions vollständig.
  - `text_body` darf bei diesen visuell direkt ausgewerteten Uploads leer bleiben, ohne UI-/API-Fehler auszulösen.
- Technischer Ansatz:
  - Kein neuer öffentlicher Task-Typ.
  - Submission-Versuche bekommen intern einen Analysemodus:
    - `text_direct`
    - `visual_direct`
    - `ocr_text` (nur Legacy-/Sonderpfade)
  - Das Routing liegt im Worker, nicht in einer separaten Frontend-Sonderlogik.
  - `analyze_visual(...)` aus dem bestehenden Feedback-Adapter wird für `native`-Uploads wiederverwendet.

## Geplante Red-Tests

- Worker:
  - `native + image/file` ruft `analyze_visual(...)`, nie `vision_adapter.extract(...)`
  - `text_body` bleibt nach erfolgreicher Analyse `null`
- OpenAPI:
  - Submission-Endpoint dokumentiert den direkten visuellen Pfad für `native`-Uploads
  - `LearningSubmission.text_body` erlaubt explizit leere Werte nach `completed` für visual-direct Uploads
- Frontend:
  - Lernraum-History rendert `completed`e Datei-Abgaben ohne `text_body` stabil weiter

## Umsetzungsstand – 2026-04-09 15:15

- Offen:
  - Worker-Routing noch OCR-basiert für `native + Upload`
  - OpenAPI/Referenzdocs behaupten noch implizit, dass Datei-Abgaben immer eine Textrepräsentation liefern
- Risiken:
  - Teaching-/Learner-Detailansichten dürfen `completed + file/image + text_body=null` nicht als Fehler interpretieren
  - Für sehr lange handschriftliche Fließtexte kann der direkte VLM-Pfad schwächer sein als OCR
- Verifikation nach Umsetzung:
  - `./.venv/bin/pytest -q backend/tests/test_learning_worker_visual_dspy_pipeline.py backend/tests/test_openapi_learning_native_upload_visual_contract.py`
  - `cd frontend && npm test -- --run src/lib/components/learning-unit/LearningSubmissionWorkspace.test.ts`
  - `cd frontend && npm run check`
  - `docker compose up -d --build frontend`
