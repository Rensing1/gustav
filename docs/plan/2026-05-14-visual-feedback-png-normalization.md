# Minimaler Plan: Visual-Feedback PNG-Diagnose und Nutzerhinweis

## Summary

Der konkrete Reprofall ist ein gültiger, großer Screenshot-PNG-Upload, der beim Produktionsprovider als HTTP 429 / `rate_limited` abgewiesen wurde. Die lokale Dev-Umgebung nutzt einen anderen Provider, deshalb wird hier bewusst keine Live-Provider-Verifikation und keine automatische Bildnormalisierung als Blindfix eingeführt.

Der kleine Fix verbessert stattdessen die Diagnose und die Nutzerführung: GUSTAV sendet direkte PNG/JPEG-Uploads unverändert an den Visual-Feedback-Provider. Wenn der Provider einen screenshot-artigen PNG-Input mit 429 abweist, wird dieser Fall intern als `image_too_complex_for_provider` klassifiziert, öffentlich aber weiter als bestehendes `feedback_failed` gespeichert. Schüler sehen eine konkrete deutsche Handlungsanweisung, einen kleineren Ausschnitt hochzuladen.

## Key Changes

- In `backend/learning/adapters/local_feedback.py` werden providergebundene Bilddaten nicht mehr automatisch umcodiert.
- Der Adapter sammelt PII-freie technische Diagnosedaten für den aktuellen Provider-Input: MIME-Typ, Base64-Länge, Bytegröße und bei PNG Breite/Höhe.
- Provider-429 bleibt für normale Fälle transient `FeedbackTransientError("provider_rate_limited")`.
- Provider-429 für screenshot-artige PNGs wird permanent `FeedbackPermanentError("image_too_complex_for_provider")`, damit der Worker nicht denselben deterministisch scheiternden Input mehrfach sendet.
- Der Worker behält den öffentlichen Fehlercode `feedback_failed`, speichert aber `feedback_last_error="image_too_complex_for_provider"` als interne Diagnose.
- SSR und Svelte-UI mappen diese interne Diagnose auf: "Das Bild ist wahrscheinlich zu groß oder zu komplex. Bitte lade einen kleineren Ausschnitt hoch, zum Beispiel nur die Zeichnung statt des ganzen Bildschirms."

## Public Interfaces

- Keine Änderung an `api/openapi.yml`.
- Keine Änderung am `learning_submissions.error_code`-Enum.
- Keine DB-Migration.
- Kein neuer öffentlicher API-Fehlercode.
- Die bestehenden internen Felder `vision_last_error` und `feedback_last_error` werden im Frontend typisiert und für UI-Copy ausgewertet.

## Test Plan

- Failing Tests zuerst:
  - Großer PNG-Input bleibt beim Provider-Aufruf `data:image/png` und wird nicht heimlich in JPEG umgewandelt.
  - Simulierter Provider-429 für großen PNG-Input wird zu `FeedbackPermanentError("image_too_complex_for_provider")`.
  - Simulierter Provider-429 für kleinen PNG-Input bleibt transient `provider_rate_limited`.
  - Worker speichert öffentlich `feedback_failed`, aber intern `feedback_last_error="image_too_complex_for_provider"`.
  - SSR und Svelte-UI zeigen die konkrete deutsche Upload-Hilfe und leaken den internen Code nicht.
- Verifikation:
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py backend/tests/test_learning_worker_feedback_error_mapping.py backend/tests/test_learning_ui_feedback_failure_messages.py`
  - `.venv/bin/pytest -q backend/tests/test_learning_worker_jobs.py -k complex_image_provider_admission`
  - `npm run test -- LearningSubmissionWorkspace.test.ts`

## Assumptions

- Ein Provider-429 auf exakt demselben großen PNG ist nach der bisherigen Reproduktion inputbedingt genug, um nicht sofort erneut denselben Input zu senden.
- Automatisches Cropping ist ohne Aufgaben-/Bildverständnis riskant, weil es relevante Randinformationen entfernen kann.
- Automatisches JPEG-Transcoding könnte beim Produktionsprovider helfen, ist aber ohne denselben Provider in Dev nicht belastbar validierbar.
- Lange PDFs bleiben ein separates Robustheitsthema. Dieser Fix klassifiziert nur direkte screenshot-artige PNG-Uploads im Visual-Feedback-Pfad.

## Follow-up

- Mit Produktionsprovider oder einem äquivalenten Staging-Provider messen, ob JPEG-Transcoding, Downscaling oder Nutzer-Cropping die bekannte Reproduktion zuverlässig löst.
- Falls daraus ein automatischer Provider-Bounds-Fix entsteht, zuerst einen neuen TDD-Plan mit klaren Bildqualitäts- und PDF-Grenzen schreiben.
