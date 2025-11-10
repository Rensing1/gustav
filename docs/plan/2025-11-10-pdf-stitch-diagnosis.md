# Plan: Diagnose und beheben von `pdf_images_unavailable` bei PDF‑Einreichungen

Status: Umsetzung abgeschlossen (Render fix deployed)  
Owner: Learning/AI  
Datum: 2025‑11‑10

## Ausgangssituation (Beobachtungen)
- Worker‑Logs zeigen wiederholt:
  - `learning.vision.pdf_ensure_stitched action=fetch_remote size=...` (Original‑PDF wird erfolgreich aus Supabase geladen)
  - direkt danach: `Vision transient error … pdf_images_unavailable` (mehrfacher Retry, am Ende `vision_failed`).
- Keine Logzeile `action=persist_derived` → das Rendern+Stitchen ist fehlgeschlagen bzw. lieferte `None`.
- pypdfium2 ist im Worker importierbar (Container‑Check: OK).  
  Daher ist die wahrscheinlichste Fehlerstelle: `process_pdf_bytes(...)` (Render) schlägt zur Laufzeit fehl.
- DB‑Abfrage aus dem Worker‑Container zeigte Jobs, aber die zugehörige Submission war nicht lesbar (vermutlich RLS/Schema‑Pfad). Das erschwert direkte Einsicht in `storage_key` und Metadaten.

## Hypothesen (geordnet nach Wahrscheinlichkeit)
1) Fetch liefert keine gültigen PDF‑Bytes (z. B. HTML/JSON‑Fehlerseite trotz 200):
   - Falscher Objektpfad oder Bucket; wir strippen `submissions/` bedingt → Pfad könnte abweichen.
   - Content‑Type wird nicht geprüft; pypdfium2 kann den Stream nicht öffnen → Render liefert `None`.
2) PDF ist gültig, aber Render wirft `PdfRenderError` (spezielle PDF‑Eigenschaften, beschädigte Datei, Annotation‑Flags):
   - Wir fangen die Exception ab und geben `None` zurück → `pdf_images_unavailable`.
3) RLS/DB‑Inkonsistenz: Job und Submission liegen in unterschiedlichem Schema/DB‑Instanz, sodass Diagnose erschwert ist (nicht die Ursache, aber ein Hindernis).

## Ziel
Verlässlich: PDF wird remote geladen → als gültiges PDF erkannt → Seiten gerendert → gestitcht → genau ein Vision‑Aufruf mit `images=[1]` → kein `pdf_images_unavailable` mehr.

## BDD‑Szenarien (Given–When–Then)
1) Gültiges PDF (nur remote verfügbar)
   - Given ein PDF liegt nur in Supabase (keine lokalen Artefakte)
   - When der Worker den Job verarbeitet
   - Then `fetch_remote`, `render`, `persist_derived` werden geloggt und es erfolgt ein einzelner Modellaufruf mit `images=[1]`.

2) Falscher Inhalt (z. B. HTML statt PDF)
   - Given Supabase antwortet 200, Content ist aber kein `%PDF-`
   - When der Worker das PDF lädt
   - Then wird `wrong_content` geloggt und der Job als transient mit `vision_failed/wrong_content` neu eingeplant.

3) Renderfehler
   - Given pypdfium2 wirft `PdfRenderError`
   - When process_pdf_bytes aufgerufen wird
   - Then wird `render_error=<code>` geloggt und der Job transient neu eingeplant.

## Maßnahmen (KISS, prod‑ready)
1) Logging/Telemetry schärfen (minimal‑invasiv):
   - Vor Render: Prüfen, ob Bytes mit `%PDF-` beginnen; sonst `wrong_content` loggen.
   - Bei Exception in `process_pdf_bytes`: Exceptionklasse/Message anonymisiert loggen (`render_error=...`).
   - Bei `page_bytes==[]`: `render_no_pages` loggen.

2) Content‑Validierung (sicher):
   - Wenn kein `%PDF-` header → keine Render‑Versuche; klassifiziere als transient (`wrong_content`) mit Retry.

3) Pfad‑Robustheit (Bucket/Pfad):
   - Telemetrie zusätzlich um `bucket=obj_bucket`, `object_key=obj_path` erweitern (ohne PII), um Fehladressierungen zu erkennen.

4) Tests (gezielt, ohne schwere Abhängigkeiten):
   - Unit: Remote‑Fetch liefert HTML → Adapter meldet `wrong_content` (transient), kein Modelaufruf.
   - Unit: `process_pdf_bytes` wirft → Adapter loggt `render_error` und liefert transient.
   - Integration (Mock): Erfolgsweg (zwei Seiten) → ein `images=[1]` Aufruf.
   - Optional (env‑guarded): kleiner PDF‑E2E mit echtem pypdfium2 in CI (RUN_PDFIUM_E2E=1).

## Nicht‑Ziele
- Kein Dev‑Only‑Bypass. Verhalten ist identisch in Lokal/Prod.
- Keine Änderung am API‑Contract.

## Risiken und Mitigation
- Unterschiedliche Bucket‑Layouts/`storage_key`‑Formate: Über Telemetrie offenlegen, kurzfristig Assertions/Tests ergänzen.
- Große PDFs: Speicher/Render‑Zeit höher; akzeptiert (Produktentscheidung „einfach“), ggf. später Limit/Streaming einbauen.

## Nächste Schritte
1) Verifikation in Logs/DB nach frischer PDF‑Einreichung: Erwartete Logcodes `fetch_remote`, ggf. `wrong_content`/`render_error`/`render_no_pages` oder `persist_derived`.
2) Worker‑E2E durchsichtig halten: bei `pdf_images_unavailable` nun in Logs Differenzierung vorhanden, Ursache ableitbar.
3) Optional: First‑page‑only Fallback evaluieren, falls bestimmte PDFs regelmäßig bei PDFium scheitern (separate Plan‑Datei).

## Warum war das Rendern blockiert?
- pypdfium2 erwartet `page.render(scale=..., draw_annots=...)`. Wir übergaben bis eben ein Low‑Level `flags`‑Argument, das im High‑Level Helper nicht existiert → `_parse_renderopts` warf `TypeError`, die wir als `render_failed_on_page_0` sahen.
- Nach Umstellung auf scale/draw_annots erzeugt der Worker wieder Seiten und kann sie stitchen; `process_pdf_bytes` funktioniert auch innerhalb des Containers.
