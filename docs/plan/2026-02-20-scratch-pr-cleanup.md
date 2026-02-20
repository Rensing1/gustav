# Plan: PR-Cleanup — Scratch SB3 Pipeline (Wartbarkeit + Konsistenz)

Datum: 2026-02-20  
Status: Implemented (Cleanup abgeschlossen; ready for review)

## Kontext / Problem
Der Scratch-SB3-PR hat die Kernfunktionalität bereits geliefert (Scratch Tasks, SB3 Upload, deterministische Evidence v2).
Vor dem Merge gab es jedoch ein paar wartbarkeitskritische Punkte:

- **Doppelte Upload-Intent JS-Pipelines** (`gustav.js` *und* `learning_upload.js`) → driftende Logik, schwer zu debuggen.
- **Artefakt-Reload-Endpoint ohne UI** (historischer „Neu laden“-Mechanismus) → unnötige Oberfläche ohne klaren Nutzen.
- **Frontend-Code-Qualität**: Tab-Indentation und kaputte Einrückung in `gustav.js` erschweren Reviews und führen zu noisy diffs.

## Ziel(e)
1. Genau **eine** Quelle der Wahrheit für den Learning Upload-Flow (Upload-Intents + PUT + Hidden Fields).
2. Keine toten/teil-implementierten UI-Features im SSR-Raum („Neu laden“).
3. Review-freundlicher Frontend-Code (kein Tabs, konsistente Indentation).
4. Tests und Dokumentation bleiben konsistent mit dem Ist-Stand.

## Entscheidungen
- Upload-JS wird konsolidiert auf **`backend/web/static/js/gustav.js`**.
  - `learning_upload.js` wird entfernt.
- Der SSR-Endpoint `/learning/.../submissions/{id}/artifact` wird **komplett entfernt**.
  - Bei Problemen mit Artefakten hilft ein normaler Seiten-Reload.

## Umsetzung (konkret)
- Layout: entfernt `learning_upload.js` aus dem `<head>`.
- Layout: Cache-Buster für `gustav.js` erhöht (damit Clients garantiert die neue Upload-Logik laden).
- `learning_upload.js`: Datei entfernt.
- `gustav.js`:
  - Tabs/Indentation bereinigt (konsistente Spaces).
  - MIME-Fallback für `.sb3` bleibt erhalten (wenn Browser kein `file.type` liefert).
  - `requestIntentAndUpload` gibt den tatsächlich verwendeten MIME zurück (statt `file.type`).
- Tests:
  - Contract-Test: Layout darf `learning_upload.js` nicht mehr laden.
  - Contract-Test: `gustav.js` darf keine Tab-Zeichen enthalten.
  - Contract-Test: Artefakt-Reload-Endpoint ist entfernt (404).
- Hygiene:
  - `sb3_validation`: ZIP wird über Context Manager geschlossen.
  - `sb3_validation`: SB3ValidationError-Codes werden nicht von einem generischen `except Exception` überschrieben.
  - `local_vision`: SB3 MIME-Konstante wird zentral importiert (Drift vermeiden).

## Akzeptanzkriterien / Checks
- `pytest` (Minimum, fokussiert):
  - `backend/tests/test_layout_assets_cleanup.py`
  - `backend/tests/test_frontend_js_style_contract.py`
  - `backend/tests/test_learning_submission_artifact_reload_removed.py`
- `pytest` (empfohlen, Scratch-relevant):
  - `backend/tests/test_learning_ui_scratch_upload_only.py`
  - `backend/tests/test_learning_scratch_sb3_upload_only_api.py`
  - `backend/tests/learning_adapters/test_local_vision_sb3.py`
  - `backend/tests/test_scratch_sb3_evidence_v2.py`
- Manuell (Smoke):
  - Scratch Task: `.sb3` auswählen → Upload vorbereitet → Abgeben → Evidence sichtbar.
  - Visual Task: PNG/PDF auswählen → Abgeben.

Ergebnis (lokal):
- `pytest` (Auswahl oben): grün (35 Tests).
