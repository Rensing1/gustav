# 2025-11-17 – Testregressionen nach Must-Fix-Welle

Status: In Arbeit

## Kontext
- Nach Abschluss der Must-Fix-Arbeiten (#0–3) wurde die gesamte Test-Suite via `.venv/bin/pytest -q` erneut ausgeführt.
- Ergebnis: 2 Fehler (`backend/tests/test_learning_routes_helpers.py::test_current_environment_prefers_settings_over_env`, `backend/tests/test_learning_vision_pdf_stitched_fallback.py::test_pdf_without_stitched_or_original_raises_transient`).
- Schnelldiagnose:
  1. `_current_environment` respektiert `SETTINGS.override_environment` nicht mehr → Regression im Priorisieren der konfigurierten Umgebung gegenüber `GUSTAV_ENV`.
  2. PDF-Fallback wirft `VisionTransientError("remote_fetch_failed")` statt des erwarteten `pdf_images_unavailable`-Codes, wenn weder stitched PNG noch Seitenbilder existieren.

## User Story
> Als Maintainer möchte ich, dass die bestehenden Helper-Tests wieder grün sind, damit Deployment-sichere Regressionen ausgeschlossen und die Must-Fix-Änderungen stabil sind.

## BDD-Szenarien
1. **Given** `SETTINGS.override_environment("prod")`, **When** `_current_environment()` aufgerufen wird, **Then** das Ergebnis ist `prod`, unabhängig von `GUSTAV_ENV`.
2. **Given** ein PDF ohne `derived`-Cache und ohne `internal_metadata.page_keys`, **When** `adapter.extract()` ausgeführt wird, **Then** der Adapter wirft `VisionTransientError("pdf_images_unavailable")` und loggt das Ereignis entsprechend.

## Umsetzungsschritte
1. Analyse + Tests für `_current_environment` (vorhandene Tests rot belassen, ggf. ergänzen).
2. Code-Änderung im Helper/Config, sodass Overrides wieder Vorrang haben.
3. Tests für PDF-Stitched-Fallback konkretisieren (ggf. neuen Test ergänzen) → Sicherstellen, dass Fehlercode `pdf_images_unavailable` entsteht.
4. Adapter-Update, das `VisionTransientError("pdf_images_unavailable")` priorisiert, wenn gar keine PDF-Images verfügbar sind.
5. Dokumentation/Plan aktualisieren und relevante Tests erneut ausführen (`backend/tests/test_learning_routes_helpers.py`, `backend/tests/test_learning_vision_pdf_stitched_fallback.py`).

## Risiken
- Änderungen am Environment-Helper könnten andere Call-Sites beeinflussen (daher nur Prioritätslogik anfassen, Tests breit halten).
- PDF-Fallback darf Remote-Fehler nicht komplett unterdrücken (nur wenn kein Bildmaterial vorhanden ist, soll `pdf_images_unavailable` erscheinen).

## Offene Fragen
- Müssen zusätzliche Telemetrie-Felder (`reason`) dokumentiert werden? → Prüfen nach Implementierung.

## Fortschritt
- 2025-11-17: `_current_environment` priorisiert nun vorhandene Modul-Overrides vor `GUSTAV_ENV`. Neuer Test `backend/tests/test_learning_routes_helpers.py::test_current_environment_prefers_loaded_module_when_imports_fail` beschreibt das Szenario (Import-Fehler → override greift). Code aktualisiert (`backend/web/routes/learning.py`) und Testlauf `.venv/bin/pytest backend/tests/test_learning_routes_helpers.py -q` grün.
- 2025-11-17: PDF-Stitched-Fallback behandelt fehlende Derived/Remote-Daten wieder als `VisionTransientError("pdf_images_unavailable")`. Neue Testdeckung (`backend/tests/test_learning_vision_pdf_stitched_fallback.py::test_pdf_remote_page_fetch_untrusted_host_degrades_to_unavailable`) + aktualisierte Basistests. Adapter-Änderungen (`backend/learning/adapters/local_vision.py`) protokollieren Remote-Fehler, fallen bei `untrusted_host`/`remote_fetch_failed` auf den generischen Error zurück. Verifiziert via `.venv/bin/pytest backend/tests/test_learning_vision_pdf_stitched_fallback.py -q`.
- 2025-11-17: Ableitungspfad für PDF-Remote-Bilder unterscheidet jetzt zwischen `untrusted_host` (→ degrade, `pdf_images_unavailable`) und anderen HTTP/Redirect-Fehlern (→ `VisionTransientError("remote_fetch_failed")`). Regressionstest `backend/tests/learning_adapters/test_local_vision_pdf_cached_paths.py::test_pdf_remote_fetch_redirect_logs_reason` wieder grün.
- 2025-11-17: Tests, die ausschließlich lokale Speicherpfade nutzen (`test_learning_vision_pdf_stitched_fallback.*`, `test_learning_vision_pdf_images_param.py`, Worker-Flow), löschen Supabase-Env-Variablen explizit, damit sie nicht von globalen SRK-Konfigurationen beeinflusst werden. Verhindert flüchtige `remote_fetch_failed`-Errors bei voll-konfigurierten Dev-Umgebungen.
