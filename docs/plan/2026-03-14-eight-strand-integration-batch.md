# Plan: Integrationsbatch fuer 8 Themenstraenge

Status: umgesetzt (2026-03-14)
Datum: 2026-03-14

## Abschluss
Abgeschlossen wurden in diesem Batch:
- Teaching Live Student Overview Review-Fixes
- Teaching Live H5P-Score `x/y`
- Learning Submit-Spamschutz
- Deterministische Feedback-Analysefehler als terminaler Worker-Fall
- Modularer File-Preview-Fallback
- Snapshot MIME Hardening fuer `.sb3` und `.hex`
- Student-Graph-Strang verifiziert
- Dokumentarischer Abschluss fuer Keycloak-, Scratch- und Calliope-Follow-ups

## Batch-Verifikation
- `backend/tests/test_teaching_live_h5p_matrix_cell_rendering.py`
- `backend/tests/test_teaching_live_unit_summary_api.py`
- `backend/tests/test_teaching_live_unit_delta_api.py`
- `backend/tests/test_teaching_live_unit_ui_ssr.py`
- `backend/tests/test_learning_ui_htmx_submit.py`
- `backend/tests/learning_adapters/test_local_feedback_dspy.py`
- `backend/tests/test_learning_worker_jobs.py`
- `backend/tests/test_learning_worker_security.py`
- `backend/tests/test_learning_worker_error_codes.py`
- `backend/tests/test_learning_modular_unit_page_ui.py`
- `backend/tests/migration/test_import_snapshot_backup.py`
- `backend/tests/test_student_modular_workspace_js_contract.py`
- `backend/tests/test_student_graph_view_sync_contract.py`
- `backend/tests/test_keycloak_theme_files.py`
- Scratch-/Calliope-Regressionen:
  - `backend/tests/test_learning_calliope_hex_upload_only_api.py`
  - `backend/tests/test_learning_ui_calliope_hex_upload_only.py`
  - `backend/tests/test_openapi_calliope_hex_contract.py`
  - `backend/tests/test_learning_scratch_sb3_upload_only_api.py`
  - `backend/tests/test_learning_ui_scratch_upload_only.py`
  - `backend/tests/test_scratch_sb3_evidence_v2.py`

## Ziel
Die seit 2026-02 identifizierten Themenstraenge sollen in einem gemeinsamen
Integrationsbatch technisch und dokumentarisch abgeschlossen werden, ohne
einen weiteren lokalen Integrationsbranch zu erzeugen.

## Leitentscheidungen
- Arbeitsstand: bestehender Branch `feature/teaching-live-student-overview`
- Lieferform: ein Integrationsbranch, ein spaeterer PR
- Done-Definition: Code integriert, relevante Tests gruen, Plan-/Ticketstatus
  sauber aktualisiert
- Bereits funktional erledigte Straenge werden nicht neu gebaut, sondern nur
  verifiziert und dokumentarisch sauber geschlossen
- Side-Branches werden selektiv integriert; keine blinden Merge-Historien

## Batch-Inhalt
1. Teaching Live
   - Student-Overview-Review-Fixes
   - H5P-Score `x/y` in der Live-Matrix
2. Learning Submit-Spamschutz
3. DSPy-/Worker-Hardening fuer deterministische Analysefehler
4. Modularer File-Preview-Fallback
5. Snapshot MIME Hardening fuer `.sb3` und `.hex`
6. Student-Graph-Optimierungen aus dem vorhandenen Feature-Branch
7. Dokumentarischer Abschluss fuer Keycloak Backlink Hardening
8. Dokumentarischer Abschluss fuer Scratch- und Calliope-Follow-ups

## TDD-Reihenfolge
1. Fehlende Plan- und Statusdokumente anlegen
2. Pro Themenblock rote Tests schreiben
3. Minimal implementieren oder selektiv vorhandene Branch-Arbeit integrieren
4. Relevante Tests gruen ziehen
5. Status in Plan-/Ticketdokumenten aktualisieren

## Verifikation
- Gezielte Testlaeufe pro Themenblock waehrend der Umsetzung
- Danach `make verify`
- Zusaetzlich `make docker-validate`, falls Compose-/Keycloak-Code betroffen ist
