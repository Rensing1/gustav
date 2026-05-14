# Minimaler Plan: Visual-Feedback PNG-Normalisierung und Diagnose

## Summary

Ziel ist ein kleiner, überprüfbarer Fix für das offene Rate-Limit-Ticket: Große PNG-Screenshots werden vor dem Vision-Provideraufruf providerfreundlich normalisiert, statt die originale große PNG-Data-URI direkt an Mistral zu senden. Es gibt keine DB-Migration, keine neuen öffentlichen API-Fehlercodes, keine neuen ENV-Variablen und keine Frontend-Änderung.

## Key Changes

- In `backend/learning/adapters/local_feedback.py` wird vor `visual_feedback_program.analyze_visual_feedback(...)` eine kleine Normalisierungsfunktion eingeführt:
  - Nur `image/png` wird normalisiert, wenn Breite oder Höhe über `1280 px` liegt oder die Base64-Payload sehr groß ist.
  - Vor jedem Decode/Resize gilt ein hartes Pixelbudget von `16_000_000` Pixeln für direkte PNG-Uploads. Hochkomprimierte Hochpixel-PNGs werden als `input_too_large` abgelehnt, damit der Worker nicht unnötig große Raster in den RAM lädt.
  - Transparente PNGs werden vor der JPEG-Ausgabe auf weißem Hintergrund compositet, damit versteckte RGB-Werte transparenter Pixel den Provider-Input nicht schwarz verfälschen.
  - Gestitchte PDF-Seitenbilder (`application/pdf` im Visual-Feedback-Pfad) laufen durch denselben Provider-Data-URI-Helper wie direkte PNG-Uploads, aber mit einem separaten festen Pixelbudget von `64_000_000` Pixeln.
  - Pillow-Decompression-Warnungen, die zur Exception werden, gelten als `input_too_large` und dürfen nicht in den Fallback auf das Original-PNG laufen.
  - Ausgabeformat ist fest `image/jpeg`, RGB, Qualität `85`, maximale Kantenlänge `1280`.
  - Kleine PNGs und vorhandene JPEGs bleiben unverändert.
- Die bestehende Signatur-/Storage-Validierung bleibt unangetastet; Normalisierung passiert erst nach erfolgreichem Laden valider Bildbytes.
- Provider-Rate-Limits werden im Adapter intern als `FeedbackTransientError("provider_rate_limited")` klassifiziert, aber noch nicht als neuer API-/DB-Code veröffentlicht.
- PII-freie Logs erfassen nur technische Diagnosewerte: ursprünglicher MIME-Typ, originale Bytegröße, normalisierter MIME-Typ, normalisierte Bytegröße, Bildmaße, Provider-Status `429`/Rate-Limit-Klasse. Keine Dateinamen, Storage-Keys, User-IDs, Prompts oder Bildinhalte.

## Public Interfaces

- Keine Änderung an `api/openapi.yml`.
- Keine Änderung am `learning_submissions.error_code`-Enum.
- Keine Änderung an `.env.example` oder `docker-compose.yml`.
- Keine Änderung am Frontend-Verhalten.

## Test Plan

- Failing Test zuerst in `backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py`:
  - Ein großes PNG wird geladen, normalisiert und als `data:image/jpeg;base64,...` an `analyze_visual_feedback` übergeben.
  - Das JPEG ist kleiner als die ursprüngliche PNG-Data-URI und hat keine Kante über `1280 px`.
- Ergänzende Regression:
  - Ein kleines PNG bleibt `data:image/png`.
  - Ein JPEG bleibt `data:image/jpeg`.
  - Falsche Bildbytes bleiben weiterhin `invalid_upload_content`.
- Rate-Limit-Klassifikation in `backend/tests/learning_adapters/test_local_feedback_dspy.py`:
  - Simulierter `litellm.RateLimitError` wird zu `FeedbackTransientError("provider_rate_limited")`.
- Review-Regressionsschutz:
  - Ein valides, klein komprimiertes Hochpixel-PNG wird vor der Provider-Normalisierung als `input_too_large` abgelehnt.
  - Ein großes transparentes PNG mit verstecktem schwarzem Hintergrund wird vor der JPEG-Ausgabe auf Weiß compositet; sichtbarer dunkler Inhalt bleibt dunkel.
  - Ein großes gestitchtes PDF-PNG wird im Visual-Feedback-Pfad ebenfalls als `data:image/jpeg;base64,...` an den Provider übergeben.
  - Ein normales zweisekitiges A4-PDF-Stitching (`2480x7016`) darf vor dem Provider-Aufruf downscalen; ein extremes PDF-Stitching über `64_000_000` Pixeln bleibt `input_too_large`.
  - Eine als Exception behandelte `Image.DecompressionBombWarning` wird zu `FeedbackPermanentError("input_too_large")`.
  - Der Worker übernimmt `FeedbackPermanentError("input_too_large")` als bestehenden Fehlercode `input_too_large`.
- Verifikation:
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py backend/tests/learning_adapters/test_local_feedback_dspy.py`
  - `.venv/bin/pytest -q backend/tests/test_learning_worker_feedback_error_mapping.py`
  - `.venv/bin/pytest -q backend/tests/test_learning_worker_jobs.py -k feedback`
  - `make verify`

## Docs And Ticket

- `docs/tickets/learning-visual-feedback-provider-rate-limit-2026-05-12.md` nach erfolgreicher Umsetzung ergänzen:
  - Status noch nicht „vollständig gelöst“, sondern „minimaler Repro-Fix umgesetzt“.
  - Klar dokumentieren: Ursache beim Provider bleibt nicht vollständig erklärt; die bekannte Reproduktion wird durch Normalisierung vermieden.
- `docs/references/learning_ai.md` kurz ergänzen:
  - Visual Feedback normalisiert große PNG-Screenshots providerseitig vor dem Modellaufruf.
  - Das Original bleibt unverändert im Storage.

## Assumptions

- Die Schwellenwerte bleiben bewusst als Code-Konstanten festgelegt: `1280 px`, `16_000_000` Pixel, JPEG-Qualität `85`, große Base64-Payload ab ca. `300000` Zeichen.
- Wenn nach der PNG-Normalisierung weiter reproduzierbare `429` auftreten, folgt ein zweites, separates Ticket für öffentliche Error-Codes, längeren Backoff und Operator-Requeue.
