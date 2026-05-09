# Plan: Filius `.fls` Upload + deterministische Evidence-Pipeline

Datum: 2026-05-01
Status: In Progress

## Live-Implementierungslog

Dieses Dokument dient während der Umsetzung als lebendes Kontextfenster.
Vor jedem TDD-Slice werden die relevanten bestehenden Codeabschnitte geprüft
und hier festgehalten. Ziel ist KISS/DRY/YAGNI: vorhandene Patterns werden
erweitert, neue Abstraktionen nur bei belegtem Nutzen eingeführt.

### 2026-05-07 — Slice 0: Branch und Arbeitsregeln

- Branch: `feature/filius-fls-upload-pipeline`.
- TDD-Regel: kein Produktionscode ohne vorherigen roten Test.
- Reporting: Zwischenbericht vor RED, nach erwartetem Fail, nach GREEN und bei Abweichungen.
- Fixture-Strategie: öffentliche Filius-Dateien werden geprüft; wenn Redistribution nicht eindeutig public-repo-tauglich ist, werden synthetische Minimal-Fixtures committed und öffentliche Dateien nur lokal validiert.

### 2026-05-07 — Slice 1: Contract/API-Start

- Geprüfte Codeabschnitte:
  - `backend/tests/test_openapi_calliope_hex_contract.py`
  - `backend/tests/test_learning_calliope_hex_upload_only_api.py`
  - `api/openapi.yml`
  - `backend/teaching/services/tasks.py`
  - `backend/web/routes/learning.py`
  - `backend/storage/learning_policy.py`
- Wiederverwendung:
  - Calliope/Scratch-Contracttests als Muster für Filius-RED-Tests.
  - Bestehende Learning-Upload-Policy und Upload-Intent-Branching statt neuer Plugin-Schicht.
- Minimale Änderung für diesen Slice:
  - Erst nur öffentliche API-/Task-/Upload-Intent-Erwartungen rot spezifizieren.
  - Danach OpenAPI und vorhandene Service-/Route-Guards additiv erweitern.
- Komplexitätsentscheidung:
  - Keine neue allgemeine Format-Registry in diesem Slice. Falls spätere Duplikation in Upload-Intent, Repo-Guard und UI sichtbar wird, wird sie gezielt nach Tests eingeführt.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_openapi_filius_fls_contract.py`
  - Ergebnis: 5 erwartete Fails wegen fehlendem `FiliusTaskConfig`, fehlenden `filius`-Enums, fehlendem FLS-MIME und fehlenden Filius-Fehlercodes.
- GREEN:
  - `api/openapi.yml` additiv um `FiliusTaskConfig`, `filius`-Enums, `filius`-Felder, FLS-MIME und Fehlercode-Beschreibungen erweitert.
  - `.venv/bin/pytest -q backend/tests/test_openapi_filius_fls_contract.py` -> 5 passed.

### 2026-05-07 — Slice 2: Teaching-Service `Task.kind=filius`

- Geprüfte Codeabschnitte:
  - `backend/tests/test_teaching_tasks_service_unit.py`
  - `backend/teaching/services/tasks.py`
- Wiederverwendung:
  - Filius folgt dem vorhandenen leeren Marker-Config-Muster von `scratch` und `calliope`.
- Minimale Änderung:
  - Keine neue Config-Basisklasse; eine kleine `_normalize_filius_config`-Funktion analog zu Scratch/Calliope reicht.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_teaching_tasks_service_unit.py -k filius`
  - Ergebnis: 4 erwartete Fails, weil `create_task`/`update_task` `filius` noch nicht als Keyword akzeptieren.
- GREEN:
  - `backend/teaching/services/tasks.py` minimal um `_normalize_filius_config`, `create_task(..., filius=...)` und `update_task(..., filius=...)` erweitert.
  - `.venv/bin/pytest -q backend/tests/test_teaching_tasks_service_unit.py -k filius` -> 4 passed.

### 2026-05-07 — Slice 3: Teaching-Web-Adapter

- Geprüfte Codeabschnitte:
  - `backend/web/routes/teaching.py` Payload-Modelle, Create-/Update-Weitergabe und `_serialize_task`.
- Wiederverwendung:
  - Bestehende Pydantic-Modelle und `_serialize_task`-Branches werden additiv erweitert.
- Minimale Änderung:
  - `filius` als optionales Payloadfeld, Weitergabe an `TasksService`, Allowlist des Fehlercodes und Serialisierung als leeres Marker-Objekt.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_teaching_filius_task_adapter.py`
  - Ergebnis: 3 erwartete Fails, weil Payloads/Serialisierung `filius` noch nicht kennen.
- GREEN:
  - `backend/web/routes/teaching.py` additiv um `filius` in Payloads, Service-Weitergabe, Fehlercode-Allowlist und `_serialize_task` erweitert.
  - `.venv/bin/pytest -q backend/tests/test_teaching_filius_task_adapter.py backend/tests/test_teaching_tasks_service_unit.py -k 'filius or not filius'` -> 25 passed.

### 2026-05-07 — Slice 4: Learning-Upload-Policy

- Geprüfte Codeabschnitte:
  - `backend/storage/learning_policy.py`
  - `backend/web/routes/learning.py`
- Wiederverwendung:
  - Bestehende `ALLOWED_FILE_MIME`/`DEFAULT_POLICY`-Struktur wird additiv erweitert.
- Minimale Änderung:
  - `FILIUS_FLS_MIME` als zentrale Konstante und Eintrag in `ALLOWED_FILE_MIME`.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_learning_filius_fls_upload_policy.py`
  - Ergebnis: erwarteter Fail, weil `application/x.filius.fls` noch nicht in `ALLOWED_FILE_MIME`/`DEFAULT_POLICY` enthalten ist.
- GREEN:
  - `backend/storage/learning_policy.py` um `FILIUS_FLS_MIME` und FLS-Datei-MIME erweitert.
  - `.venv/bin/pytest -q backend/tests/test_learning_filius_fls_upload_policy.py` -> 1 passed.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_learning_filius_fls_upload_intent.py`
  - Ergebnis: 1 erwarteter Fail, weil `Task.kind=filius` im Upload-Intent noch nicht FLS-only akzeptiert; Nicht-Filius-FLS wird bereits abgelehnt.
- GREEN:
  - `backend/web/routes/learning.py` um FLS-only Branch für `Task.kind=filius` und `.fls`-Storage-Key-Endung erweitert.
  - `.venv/bin/pytest -q backend/tests/test_learning_filius_fls_upload_policy.py backend/tests/test_learning_filius_fls_upload_intent.py` -> 3 passed.

### 2026-05-07 — Slice 5: FLS-Container-Validation

- Geprüfte Codeabschnitte:
  - `backend/storage/sb3_validation.py`
  - `backend/storage/makecode_hex_validation.py`
  - `backend/web/routes/learning.py` frühe SB3/HEX-Validation
- Wiederverwendung:
  - Eigenes kleines Storage-Validierungsmodul analog zu SB3 statt Parserlogik in der Route.
- Minimale Änderung:
  - ZIP bounded lesen, `projekt/konfiguration.xml` extrahieren, DOCTYPE/Entity/gefährliche XMLDecoder-Konstrukte ablehnen.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_filius_fls_validation.py`
  - Ergebnis: 6 erwartete Fails, weil `backend.storage.filius_validation` noch fehlt.
- GREEN:
  - `backend/storage/filius_validation.py` mit bounded ZIP-Lesen, `projekt/konfiguration.xml`-Extraktion und stabilen Fehlercodes ergänzt.
  - `.venv/bin/pytest -q backend/tests/test_filius_fls_validation.py` -> 6 passed.

### 2026-05-07 — Slice 6: Filius-Submission-Validation

- Geprüfte Codeabschnitte:
  - `backend/web/routes/learning.py` Submission-Finalisierung für SB3/HEX.
  - `backend/storage/filius_validation.py`.
- Wiederverwendung:
  - FLS folgt der bestehenden frühen SB3/HEX-Validation vor `CreateSubmissionUseCase`.
- Minimale Änderung:
  - Bei FLS-MIME Task-kind lesen, Nicht-Filius ablehnen, Storage-Bytes laden, `extract_configuration_xml_bytes` validieren.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_learning_filius_fls_submission_api.py`
  - Ergebnis: 3 erwartete Fails; gültige FLS persistiert bereits generisch, aber Invalid/Unavailable/Nicht-Filius-FLS fehlen.
- GREEN:
  - `backend/web/routes/learning.py` um frühe FLS-Validation vor Persistenz erweitert.
  - `.venv/bin/pytest -q backend/tests/test_filius_fls_validation.py backend/tests/test_learning_filius_fls_submission_api.py` -> 10 passed.

### 2026-05-07 — Slice 7: Repo-Guard-Matrix

- Geprüfte Codeabschnitte:
  - `backend/learning/repo_db.py` inline Task-kind/Submission-kind Guard.
  - `backend/tests/test_learning_repo_submission_mapping.py` als Muster für DB-freie Repo-Tests.
- Wiederverwendung:
  - Bestehende Guard-Matrix bleibt fachlich gleich und wird nur in eine pure Funktion verschoben, damit sie ohne DB testbar bleibt.
- Minimale Änderung:
  - `_validate_task_submission_kind(task_kind, submission_kind, mime_type)` ergänzt und in `create_submission` verwendet.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_learning_submission_kind_guard.py`
  - Ergebnis: erwarteter ImportError, weil die pure Guard-Funktion noch nicht existiert.
- GREEN:
  - `backend/learning/repo_db.py` um `_validate_task_submission_kind` erweitert und inline-Matrix dadurch ersetzt.
  - `.venv/bin/pytest -q backend/tests/test_learning_submission_kind_guard.py backend/tests/test_learning_repo_submission_mapping.py` -> 11 passed.

### 2026-05-07 — Slice 8: Erste Filius-Evidence

- Geprüfte Codeabschnitte:
  - `backend/scratch/sb3_evidence_v2.py`
  - `backend/makecode/hex_evidence_v1.py`
  - `backend/storage/filius_validation.py`
- Wiederverwendung:
  - Neues Formatmodul wie Scratch/MakeCode; keine generische Worker-Registry.
- Minimale Änderung:
  - Deterministischer Markdown-Rahmen mit festen Abschnitten, Projektversion und bekannten XMLDecoder-Klassen; keine Roh-XML-Ausgabe.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py`
  - Ergebnis: erwarteter Fail, weil `backend.filius.evidence_v1` noch fehlt.
- GREEN:
  - `backend/filius/evidence_v1.py` und `backend/filius/__init__.py` ergänzt.
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/test_filius_fls_validation.py` -> 7 passed.
- Abweichung:
  - Die aktuelle Evidence ist ein sicherer, deterministischer Grundrahmen mit Version und bekannten Filius-Klassen. Die im Zielbild geforderte vollständige fachliche Topologie-/Routing-/DNS-/Web-/Mail-Extraktion ist noch nicht abgeschlossen und bleibt als weiterer TDD-Ausbau offen.

### 2026-05-07 — Slice 9: Worker-Filius-Branch

- Geprüfte Codeabschnitte:
  - `backend/learning/adapters/local_vision.py` SB3- und HEX-Branches.
  - `backend/tests/learning_adapters/test_local_vision_makecode_hex.py`.
- Wiederverwendung:
  - Bestehende lokale/remote Storage-Lesehelper und `VisionResult`-Rückgabeform.
- Minimale Änderung:
  - FLS in `SUPPORTED_MIME` aufnehmen und einen Branch mit `backend.filius.evidence_v1.build_evidence_markdown_v1` ergänzen.
- RED:
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_vision_filius_fls.py`
  - Ergebnis: erwarteter Fail `unsupported mime: application/x.filius.fls`.
- GREEN:
  - `backend/learning/adapters/local_vision.py` um FLS-MIME und deterministischen Filius-Branch erweitert.
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_vision_filius_fls.py backend/tests/learning_adapters/test_local_vision_makecode_hex.py backend/tests/learning_adapters/test_local_vision_sb3.py` -> 3 passed.

### 2026-05-07 — Slice 10: Learning-UI Upload-only

- Geprüfte Codeabschnitte:
  - `frontend/src/lib/components/learning-unit/LearningSubmissionWorkspace.svelte`
  - `frontend/src/lib/components/learning-unit/LearningTaskCard.test.ts`
  - `frontend/src/lib/types/learning.ts`
  - `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.server.ts`
- Wiederverwendung:
  - Filius wird in die vorhandene upload-only Bedingung aufgenommen; kein neuer UI-Modus.
- Minimale Änderung:
  - Type-Union erweitern, upload-only für `filius`, Label `.fls-Datei hochladen`.
- RED:
  - `npm test -- --run src/lib/components/learning-unit/LearningTaskCard.test.ts`
  - Ergebnis: 1 erwarteter Fail; Filius zeigt noch den Text/Upload-Switch statt upload-only.
- GREEN:
  - `frontend/src/lib/types/learning.ts`, `frontend/src/lib/types/home.ts`, `LearningSubmissionWorkspace.svelte`, `LearningTaskCard.svelte` und Learning-Page-Server um Filius upload-only erweitert.
  - `npm test -- --run src/lib/components/learning-unit/LearningTaskCard.test.ts` -> 30 passed.

### 2026-05-07 — Slice 11: Supabase-Migrationen und lokale Bucket-Allowlist

- Geprüfte Codeabschnitte:
  - Calliope-Migrationen `20260223120000_*`, `20260223121000_*`, `20260223122000_*`.
  - `supabase/config.toml` Bucket `submissions`.
  - Storage-/Migration-Contracttests.
- Wiederverwendung:
  - Filius-Migrationen folgen exakt den additiven Calliope-Mustern.
- Minimale Änderung:
  - Drei neue Migrationen für Task-kind, Submission-MIME und Storage-Bucket-Allowlist; keine neuen Spalten.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_learning_storage_policy_contract.py backend/tests/test_storage_buckets_provisioning.py::test_local_supabase_config_allows_makecode_hex_in_submissions_bucket backend/tests/test_storage_buckets_provisioning.py::test_filius_storage_migration_updates_allowlist_additively backend/tests/test_filius_migrations_contract.py`
  - Ergebnis: 4 erwartete Fails wegen fehlender Filius-Migrationen und fehlendem FLS-MIME in `supabase/config.toml`.
- GREEN:
  - Drei additive Filius-Migrationen und `supabase/config.toml` Bucket-Allowlist ergänzt.
  - `.venv/bin/pytest -q backend/tests/test_learning_storage_policy_contract.py backend/tests/test_storage_buckets_provisioning.py::test_local_supabase_config_allows_makecode_hex_in_submissions_bucket backend/tests/test_storage_buckets_provisioning.py::test_filius_storage_migration_updates_allowlist_additively backend/tests/test_filius_migrations_contract.py` -> 6 passed.

### 2026-05-07 — Slice 12: Verstreute Upload-MIME-Mappings

- Geprüfte Codeabschnitte:
  - `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte`
  - `backend/web/main.py`
- Wiederverwendung:
  - Bestehende task-kind/Dateiendungs-Mappings werden nur additiv erweitert.
- Minimale Änderung:
  - Filius in `UploadTaskKind`, Svelte-MIME-Mapping, SSR-Upload-Form und Dateiendungs-MIME-Erkennung ergänzen.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_filius_upload_client_surface_contract.py`
  - Ergebnis: 2 erwartete Fails, weil die verstreuten Client-/SSR-Mappings Filius noch nicht enthalten.
- GREEN:
  - `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte` und `backend/web/main.py` additiv um `.fls`/`application/x.filius.fls` erweitert.
  - `.venv/bin/pytest -q backend/tests/test_filius_upload_client_surface_contract.py` -> 2 passed.

### 2026-05-07 — Slice 13: Snapshot-Import/Restore

- Geprüfte Codeabschnitte:
  - `backend/tools/import_snapshot_backup.py`
  - `backend/tests/migration/test_import_snapshot_backup.py`
- Wiederverwendung:
  - Bestehende lokale Bucket-Allowlist-Synchronisierung und Dateiendungs-MIME-Erkennung für `.sb3`/`.hex`.
- Minimale Änderung:
  - `application/x.filius.fls` in die Submission-Bucket-Allowlist aufnehmen und `.fls` beim Restore als Filius-MIME erkennen.
- RED:
  - `.venv/bin/pytest -q backend/tests/migration/test_import_snapshot_backup.py::test_sync_bucket_allowlists_adds_makecode_hex_for_submissions backend/tests/migration/test_import_snapshot_backup.py::test_guess_content_type_handles_snapshot_submission_extensions`
  - Ergebnis: 2 erwartete Fails; Restore-SQL enthielt FLS nicht und `.fls` fiel auf `application/octet-stream` zurück.
- GREEN:
  - `backend/tools/import_snapshot_backup.py` minimal um FLS-Allowlist und `.fls`-Suffix-Mapping erweitert.
  - `.venv/bin/pytest -q backend/tests/migration/test_import_snapshot_backup.py::test_sync_bucket_allowlists_adds_makecode_hex_for_submissions backend/tests/migration/test_import_snapshot_backup.py::test_guess_content_type_handles_snapshot_submission_extensions` -> 4 passed.

### 2026-05-07 — Slice 14: Filius-Evidence-Anzeige

- Geprüfte Codeabschnitte:
  - `frontend/src/lib/utils/submission-artifacts.ts`
  - `frontend/src/lib/components/learning-unit/LearningSubmissionArtifactView.svelte`
  - `frontend/src/lib/components/learning-unit/LearningTaskCard.test.ts`
  - `frontend/src/lib/components/learning-unit/LearningSubmissionWorkspace.test.ts`
  - `frontend/src/routes/live/+page.svelte`
- Wiederverwendung:
  - Bestehender Scratch/MakeCode-Artifact-Pfad; Filius wird als strukturierte Markdown-Evidence gerendert, keine neue Viewer-Komponente.
- Minimale Änderung:
  - `filius.evidence.v1` erkennen, Schema-Heading ausblenden, mit `filius-evidence`-Wrapper rendern und Live-Ansicht um Header-Stripping ergänzen.
- RED:
  - `npm test -- src/lib/utils/submission-artifacts.test.ts --run`
  - Ergebnis: 1 erwarteter Fail; `.fls` wurde vom Artifact-Parser noch ignoriert.
- GREEN:
  - `frontend/src/lib/utils/submission-artifacts.ts` und `LearningSubmissionArtifactView.svelte` um Filius erweitert.
  - `npm test -- src/lib/utils/submission-artifacts.test.ts --run` -> 3 passed.
  - `npm test -- src/lib/components/learning-unit/LearningTaskCard.test.ts src/lib/components/learning-unit/LearningSubmissionWorkspace.test.ts --run` -> 39 passed.
- Hinweis:
  - Die Frontend-Tests benötigen außerhalb der Sandbox localhost-Auflösung; der initiale Sandbox-Lauf brach mit `getaddrinfo EAI_AGAIN localhost` ab.

### 2026-05-07 — Slice 15: Legacy-Browser-Skript und Teaching-SSR-Create

- Geprüfte Codeabschnitte:
  - `backend/web/static/js/gustav.js`
  - `backend/web/main.py` SSR-Upload- und Task-Create-Hilfen.
- Wiederverwendung:
  - Bestehende Dateiendungs-Fallbacks und Task-kind-Payload-Branches werden additiv erweitert.
- Minimale Änderung:
  - Legacy-JS erkennt `.fls`, zeigt FLS-spezifische Fehlermeldung, SSR-Task-Create setzt `payload["filius"] = {}`.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_filius_upload_client_surface_contract.py`
  - Ergebnis: 1 erwarteter Fail; `backend/web/static/js/gustav.js` kannte FLS noch nicht.
- GREEN:
  - `backend/web/static/js/gustav.js` und `backend/web/main.py` additiv erweitert.
  - `.venv/bin/pytest -q backend/tests/test_filius_upload_client_surface_contract.py` -> 3 passed.

### 2026-05-07 — Slice 16: Gesamtverify-Folgearbeiten

- Geprüfte Codeabschnitte:
  - `backend/tests/test_openapi_teaching_unit_workspace_view_contract.py`
  - `backend/tests/test_storage_buckets_provisioning.py`
  - neue Filius-Migrationen in `supabase/migrations/`
- Befund:
  - Erster `make verify`-Lauf wurde durch undichte Filius-Tests verfälscht: `FakeLearningRepo` blieb global gesetzt und ließ spätere Learning-/H5P-/Live-Tests gegen den Fake laufen.
  - Nach Test-Isolation blieben zwei echte Folgepunkte: veraltete OpenAPI-Erwartung für `TeacherUnitNodeEditorTask.kind` und lokal noch nicht angewendete Storage-Bucket-Migration.
- Minimale Änderung:
  - Filius-Tests restaurieren Repo/Storage-/Validierungsstubs nach jedem Test.
  - Workspace-View-Contracttest um `filius` erweitern.
  - `supabase migration up` lokal ausführen, damit die DB-Allowlist dem Migrationsstand entspricht.
- Verifikation:
  - `.venv/bin/pytest -q backend/tests/test_learning_filius_fls_upload_intent.py backend/tests/test_learning_filius_fls_submission_api.py backend/tests/test_learning_h5p_access_check_api.py::test_learning_h5p_access_204_for_enrolled_student_and_released_task` -> 6 passed, 1 skipped.
  - `supabase migration up` -> `Local database is up to date.`
  - `make verify` -> passed:
    - Backend pytest: 1520 passed, 33 skipped.
    - H5P Node tests: 15 passed.
    - Supabase integration: 5 passed.
    - OpenAI-compatible endpoint smoke: 2 passed.
    - Docker/E2E: 13 passed.

### 2026-05-08 — Slice 17: Topologie-Evidence aus echter Filius-Fixture

- Geprüfte Codeabschnitte:
  - `backend/filius/evidence_v1.py`
  - `backend/storage/filius_validation.py`
  - `backend/tests/test_filius_evidence_v1.py`
  - `backend/tests/learning_adapters/test_local_vision_filius_fls.py`
  - inf-schule Lizenzseite: Inhalte grundsätzlich CC BY-SA 4.0 mit Namensnennung und Lizenzhinweis.
- Entscheidung:
  - `filius.evidence.v1` bleibt das öffentliche Schema.
  - Erste Qualitätsstufe: Nodes, Interfaces, Links und deterministisch abgeleitete IPv4-Netze; keine Diagnosehinweise.
  - Testfixture: echte `filius_ClientServer.fls` von inf-schule mit Attribution.
  - Golden-Test: erwartete Evidence als Markdown-Datei neben der Fixture.
- Minimale Änderung:
  - Neues reines Parser-Modul `backend/filius/topology.py`; `evidence_v1.py` rendert weiter Markdown.
  - Keine DNS/Web/Mail/Firewall-/manuelle Routing-Extraktion in diesem Slice.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py`
  - Ergebnis: 1 erwarteter Fail, weil die echte `filius_ClientServer.fls`-Fixture noch nur Klassenlisten statt Topologie-Evidence renderte.
- GREEN:
  - `backend/filius/topology.py` ergänzt: passive XMLDecoder-Auswertung für GUI-Knoten, Hardware-Klassen, Interface-Properties, Tooltip-Fallbacks für Netzmaske/Gateway/DNS, Kabel-Endpunkte und abgeleitete IPv4-Netze.
  - `backend/filius/evidence_v1.py` rendert Nodes, Interfaces, Links und abgeleitete Netze weiter unter `filius.evidence.v1`.
  - `backend/tests/fixtures/filius/inf-schule-clientserver/` enthält `.fls`, `ATTRIBUTION.md` und Markdown-Golden-File.
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py` -> 3 passed.
- Integrationssicherung:
  - `backend/tests/learning_adapters/test_local_vision_filius_fls.py` erweitert, damit der lokale Workerpfad für die echte Fixture Topologie-Evidence liefert.

### 2026-05-08 — Slice 18: Routing-Evidence aus Mehr-Netze-Fixture

- Geprüfte Codeabschnitte:
  - `backend/filius/topology.py`
  - `backend/filius/evidence_v1.py`
  - `backend/tests/test_filius_evidence_v1.py`
  - `backend/tests/learning_adapters/test_local_vision_filius_fls.py`
  - bestehende inf-schule Fixture-Struktur unter `backend/tests/fixtures/filius/inf-schule-clientserver/`
- Befund:
  - Filius speichert Router-Interfaces in `netzwerkInterfaces` teils als `void method="add"` mit enthaltenem `object class="filius.hardware.NetzwerkInterface"`. Der bisherige Parser las dort das umschließende `void` statt des Interface-Objekts.
  - Manuelle Routingtabellen liegen in `weiterleitungstabelle.manuelleTabelle` als String-Arrays mit Ziel-IP, Netzmaske, Next-Hop-IP und lokaler Interface-IP.
- Entscheidung:
  - Neue Fixture: echte inf-schule Datei `filius_mehrere_netze.fls` mit eigener `ATTRIBUTION.md`.
  - Evidence bleibt faktisch und knapp: keine Diagnose, keine Pfadsuche, keine didaktische Interpretation. Ausgegeben werden nur abgeleitete Netze und manuelle Routingzeilen mit stabilen synthetischen IDs.
  - `0.0.0.0`-Platzhalter-Interfaces werden als ungültig gezählt, erzeugen aber kein künstliches `0.0.0.0/24`-Netz.
- Minimale Änderung:
  - `_interface_objects` löst `void method="add"` korrekt auf echte Interface-Objekte auf.
  - `FiliusManualRoute` und `manual_routes` werden im vorhandenen Topologie-Modell ergänzt; keine neue Parser-Registry.
  - Renderer ergänzt im bestehenden Abschnitt `Routing` die Liste `manual_routes`.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py -k mehrere_netze`
  - Ergebnis: erwarteter Fail wegen fehlendem Golden-File bzw. fehlender Routing-Evidence.
- GREEN:
  - `backend/filius/topology.py` extrahiert Router-Interfaces, abgeleitete Netze und manuelle Routen.
  - `backend/filius/evidence_v1.py` rendert `manual_routes` unter `filius.evidence.v1`.
  - `backend/tests/fixtures/filius/inf-schule-mehrere-netze/` enthält `.fls`, `ATTRIBUTION.md` und Markdown-Golden-File.
  - Bestehendes Clientserver-Golden-File wurde nur um den neuen Parser-Note-Zähler `manual_routes: 0` ergänzt.
- Verifikation:
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py -k mehrere_netze` -> 2 passed, 3 deselected.
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py backend/tests/test_filius_fls_validation.py` -> 13 passed.
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_vision_filius_fls.py` -> 3 passed.
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py backend/tests/test_filius_fls_validation.py backend/tests/test_learning_filius_fls_submission_api.py` -> 18 passed.
  - `git diff --check` -> passed.
  - `make verify` -> passed:
    - Backend pytest: 1526 passed, 33 skipped.
    - H5P Node tests: 15 passed.
    - Supabase integration: 5 passed.
    - OpenAI-compatible endpoint smoke: 2 passed.
    - Docker/E2E: 13 passed.

### 2026-05-08 — Slice 19: DNS- und Web-Evidence

- Geprüfte Codeabschnitte:
  - `backend/filius/topology.py`
  - `backend/filius/evidence_v1.py`
  - `backend/tests/test_filius_evidence_v1.py`
  - `backend/tests/learning_adapters/test_local_vision_filius_fls.py`
  - reale Referenzdateien in `/tmp`: `filius_webserver.fls`, `dns0.fls`, `email0.fls`
- Befund:
  - `filius_webserver.fls` enthält WebServer-Prozesse, aber keine DNS-Konfiguration und kaum fachliche Webdatei-Inhalte.
  - `dns0.fls` enthält Webdateien, aber keinen DNS-Server.
  - `email0.fls` enthält einen DNS-Server und `/dns/hosts`, aber die Hosts-Datei ist leer.
- Entscheidung:
  - Für TDD wird eine kleine synthetische DNS+Web-Fixture genutzt, damit DNS-Server, `/dns/hosts`, WebServer, textuelle Webdateien, Binär-Webdateien und nicht erlaubte Pfade präzise abgedeckt werden.
  - DNS-Hosts werden in diesem Slice als sichere, bounded Dateiinhalte gerendert, nicht semantisch in Domain/IP-Paare zerlegt.
  - Web-Binärdaten werden nur als Metadaten mit Größe und SHA-256 gerendert.
- Minimale Änderung:
  - Das vorhandene Topologie-Modell wird um installierte Anwendungen und allowlist-gefilterte Filius-Dateisystemeinträge erweitert.
  - `evidence_v1.py` rendert `## DNS` und `## Web`; API, DB und Frontend bleiben unverändert.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py::test_filius_synthetic_dns_web_fixture_renders_safe_dns_and_web_evidence backend/tests/learning_adapters/test_local_vision_filius_fls.py::test_local_vision_filius_fls_returns_dns_web_evidence_for_synthetic_fixture`
  - Ergebnis: 2 erwartete Fails, weil `## DNS` und `## Web` noch `none` renderten.
- GREEN:
  - `backend/filius/topology.py` extrahiert allowlist-relevante Anwendungen (`DNSServer`, `WebServer`) und erlaubte Dateisystempfade (`/dns/hosts`, `/webserver/*`, `/www.conf/vhosts`).
  - `backend/filius/evidence_v1.py` rendert DNS-/Web-Anwendungen, Textdateiinhalte bounded und Binärdateien nur als Metadaten mit SHA-256.
  - `backend/tests/fixtures/filius/synthetic-dns-web/` enthält die kleine synthetische XML-Fixture und ein Markdown-Golden-File.
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py` -> 10 passed.
- Verifikation:
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py backend/tests/test_filius_fls_validation.py backend/tests/test_learning_filius_fls_submission_api.py` -> 20 passed.
  - `git diff --check` -> passed.
  - `make verify` -> passed:
    - Backend pytest: 1528 passed, 33 skipped.
    - H5P Node tests: 15 passed.
    - Supabase integration: 5 passed.
    - OpenAI-compatible endpoint smoke: 2 passed.
    - Docker/E2E: 13 passed.

### 2026-05-09 — Slice 20: Firewall-Evidence aus offizieller Filius-Fixture

- Geprüfte Codeabschnitte vor Implementierung:
  - `backend/filius/topology.py`: vorhandene Dataclasses, Anwendungsextraktion, XMLDecoder-Helfer, Dateisystem-Allowlist.
  - `backend/filius/evidence_v1.py`: stabile Abschnittsreihenfolge, Renderer für Routing/DNS/Web, Escape- und Truncation-Logik.
  - `backend/tests/test_filius_evidence_v1.py`: Golden-File-Konvention, Attribution-Tests, Roh-XML-/Passwort-Sicherheitsassertions.
  - `backend/tests/learning_adapters/test_local_vision_filius_fls.py`: End-to-end-Adapterpfad für deterministische Filius-Evidence.
  - `THIRD_PARTY_NOTICES.md` und bestehende Fixture-`ATTRIBUTION.md`: Provenance- und Lizenzkonventionen.
- Befund:
  - Bisherige lokale und inf-schule-Fixtures enthalten keine echten `FirewallRule`-Einträge.
  - Offizielle Filius-Beispieldatei `Internet_Komplett_mit_eMail_Webserver_Intranet_Portforwarding_Firewall_DHCP_DE.fls` aus dem Filius-GitLab-Repository enthält sechs echte Regeln unter `FirewallWebKonfig -> firewall -> ruleset -> FirewallRule`.
  - Filius speichert FirewallRule-Felder als XMLDecoder-Reflection-Form: `void class="filius.software.firewall.FirewallRule" method="getField"` mit anschließendem `void method="set"`.
- Entscheidung:
  - Für Firewall-Evidence wird eine unveränderte offizielle Filius-Fixture verwendet, gepinnt auf Commit `dcd965f6139baef4c27cc6d3cc34106f6bebda40`.
  - Synthetische Fixtures bleiben nur für gezielte Security-/Grenzfalltests vorgesehen.
  - GPLv3-Fixture-Provenance wird pro Fixture und in `THIRD_PARTY_NOTICES.md` dokumentiert.
- RED:
  - Golden-Test erwartet `## Firewall` mit aktivierter Firewall und sechs normalisierten Regeln.
  - Adaptertest erwartet, dass `local_vision` diese Firewall-Evidence durchreicht.
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py::test_filius_official_firewall_fixture_renders_real_rules backend/tests/test_filius_evidence_v1.py::test_filius_official_firewall_fixture_keeps_source_attribution backend/tests/learning_adapters/test_local_vision_filius_fls.py::test_local_vision_filius_fls_returns_firewall_evidence_for_official_fixture` -> erwartete Fails in Evidence-/Adaptertest, Attribution grün.
- GREEN:
  - `backend/filius/topology.py` ergänzt ein kleines Firewall-Modell und extrahiert nur passive, fachliche Felder.
  - `backend/filius/evidence_v1.py` rendert Firewall-Evidence deterministisch; Roh-XML, `idref` und Passwörter bleiben ausgeschlossen.
  - Fehlende `FirewallRule`-Felder werden anhand belegter Filius-Java-Defaults normalisiert: `action=DROP`, `port=*`, `protocol=TCP`.
  - Offizielle Fixture liegt unverändert unter `backend/tests/fixtures/filius/filius-official-firewall/` mit `ATTRIBUTION.md` und Golden File.
- Verifikation:
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py::test_filius_official_firewall_fixture_renders_real_rules backend/tests/test_filius_evidence_v1.py::test_filius_official_firewall_fixture_keeps_source_attribution backend/tests/learning_adapters/test_local_vision_filius_fls.py::test_local_vision_filius_fls_returns_firewall_evidence_for_official_fixture` -> 3 passed.
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py` -> 13 passed.
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py backend/tests/test_filius_fls_validation.py backend/tests/test_learning_filius_fls_submission_api.py` -> 23 passed.
  - `git diff --check` -> passed.
  - `make verify` -> passed:
    - Backend pytest: 1531 passed, 33 skipped.
    - H5P Node tests: 15 passed.
    - Supabase integration: 5 passed.
    - OpenAI-compatible endpoint smoke: 2 passed.
    - Docker/E2E: 13 passed.

### 2026-05-09 — Slice 21: E-Mail-Metadaten und offizielle App-Fixtures

- Geprüfte Codeabschnitte vor Implementierung:
  - `backend/filius/topology.py`: bestehende Dataclasses, App-Kind-Erkennung, installierte Anwendungen, XMLDecoder-Helfer.
  - `backend/filius/evidence_v1.py`: Abschnittsreihenfolge, `## Email`-Platzhalter, Safe-Text-Rendering.
  - `backend/tests/test_filius_evidence_v1.py` und `backend/tests/learning_adapters/test_local_vision_filius_fls.py`: Golden-File- und Adapter-Konventionen.
  - Filius-Quellklassen `EmailAnwendung.java`, `EmailServer.java`, `EmailKonto.java`, `Email.java`, `AddressEntry.java`.
  - Offizielle Filius-Beispiele `dns_server.fls`, `webserver.fls`, `email_komplett.fls`.
- Befund:
  - `email_komplett.fls` enthält Mailclient-Konten und Mailserver-Konten, aber keine gespeicherten `Email`-Nachrichten.
  - Die komplexe offizielle Firewall-Fixture enthält gespeicherte `Email`-Objekte; diese bleiben bewusst außerhalb dieses Slices.
  - `EmailKonto` persistiert `passwort`, `vorname` und `nachname`; diese Felder sind für Netzwerkdiagnose nicht erforderlich und werden nicht gerendert.
- Entscheidung:
  - Offizielle DNS-/Web-/E-Mail-Fixtures werden ergänzend aufgenommen; die synthetische DNS/Web-Fixture bleibt für Security-/Edge-Cases bestehen.
  - E-Mail-Evidence ist metadata-only: Mailclient, Mailserver, Domain, Benutzername, E-Mail-Adresse, POP3-/SMTP-Server und Ports.
  - Keine Vor-/Nachnamen, keine Passwörter, kein Roh-`konten.txt`, keine Betreffzeilen und keine Mailkörper.
- RED:
  - Offizielle DNS-/Web-Golden-Tests scheiterten erwartungsgemäß an Platzhalter-Golden-Files.
  - E-Mail-Golden- und Adaptertests scheiterten erwartungsgemäß, weil `## Email` noch `none` rendert.
- GREEN:
  - `backend/filius/topology.py` ergänzt E-Mail-Client-/Server-Modelle und passive Extraktion von `EmailAnwendung.kontoListe` und `EmailServer.listeBenutzerkonten`.
  - `backend/filius/evidence_v1.py` rendert `## Email` mit Accounts und Servermetadaten.
  - `EmailServer.mailDomain` nutzt den belegten Filius-Default `filius.de`, wenn die Domain nicht explizit persistiert ist.
  - Neue offizielle Fixture-Verzeichnisse enthalten `.fls`, `ATTRIBUTION.md` und Golden-Files für DNS, Web und E-Mail.
- Verifikation:
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py` -> 18 passed.
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py backend/tests/test_filius_fls_validation.py backend/tests/test_learning_filius_fls_submission_api.py` -> 28 passed.
  - `git diff --check` -> passed.
  - `make verify` -> passed:
    - Backend pytest: 1536 passed, 33 skipped.
    - H5P Node tests: 15 passed.
    - Supabase integration: 5 passed.
    - OpenAI-compatible endpoint smoke: 2 passed.
    - Docker/E2E: 13 passed.

### 2026-05-09 — Slice 22: Evidence-Qualität nach LLM-Evaluation

- Geprüfte Codeabschnitte vor Implementierung:
  - `backend/filius/topology.py`: E-Mail-Client-/Server-Extraktion, Dateisystem-Parser, App-Status.
  - `backend/filius/evidence_v1.py`: Parser-Notes, DNS-/Web-App-Rendering, E-Mail-Rendering.
  - `backend/tests/test_filius_evidence_v1.py`: Golden-File-Konvention und Security-Assertions.
  - `backend/learning/adapters/dspy/signatures.py` und `docs/references/LLM-Prompts.md`: Feedback-Synthesis-Prompt-Vertrag.
- Befund:
  - Die echte inf-schule-Datei `email_netzwerk.fls` speichert ältere E-Mail-Client-Konten nicht in `EmailAnwendung.kontoListe`, sondern als root-nahe Filius-Datei `konten.txt` im jeweiligen Client-Dateisystem.
  - Die Serverdatei `/mailserver/konten.txt` enthält ebenfalls Kontendaten, darf aber nicht roh gerendert werden; für Serverkonten bleibt `EmailServer.listeBenutzerkonten` die sauberere Quelle.
  - Die neuere offizielle Fixture `email_komplett.fls` nutzt `EmailAnwendung.kontoListe` und bleibt damit bereits abgedeckt.
  - `active: "unknown"` bei installierten Anwendungen wurde vom Feedback-LLM teils als möglicherweise inaktiver Dienst interpretiert. Tatsächlich ist die Installation belegt; nur der Aktivstatus ist in manchen Filius-Versionen nicht persistiert.
  - In der Routing-Evaluation erkannte die strukturierte Analyse fehlende Router-III-Routen, aber die Feedback-Synthese formulierte teilweise konkrete falsche Next-Hop-/Interface-Vorschläge.
- Entscheidung:
  - E-Mail-Client-Konten werden zusätzlich aus root-`/konten.txt` gelesen, bounded und ohne Passwörter/Vor-/Nachnamen/Rohdatei.
  - Parser-Notes bekommen einen Zähler für E-Mail-Clients ohne Konto, damit fehlende Client-Konfiguration ausdrücklich sichtbar ist.
  - DNS-/Web-App-Evidence unterscheidet künftig `installed: "true"` von `active` und `active_source`, ohne das Schema `filius.evidence.v1` zu ändern.
  - Der Feedback-Synthesis-Prompt wird gehärtet: konkrete technische Vorschläge nur bei eindeutiger Belegbarkeit; bei Unsicherheit allgemeiner formulieren.
- RED-Ziele:
  - Ein synthetischer Legacy-E-Mail-Test erwartet Client-Konten aus root-`konten.txt`.
  - Der bestehende DNS/Web-Golden-Test erwartet `installed` und `active_source`.
  - Ein Prompt-Contract-Test erwartet die neue Halluzinationsbremse in Signature und Referenzdoku.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py::test_filius_legacy_email_client_konten_file_renders_metadata_without_secrets backend/tests/test_filius_evidence_v1.py::test_filius_synthetic_dns_web_fixture_renders_safe_dns_and_web_evidence backend/tests/learning_adapters/test_signature_docstrings_match_prompt_reference.py::test_feedback_synthesis_contract_avoids_unverifiable_technical_suggestions` -> 3 erwartete Fails.
- GREEN:
  - `backend/filius/topology.py` liest ältere E-Mail-Client-Konten zusätzlich aus root-`/konten.txt` und ignoriert `/mailserver/konten.txt` für Client-Konten.
  - `backend/filius/evidence_v1.py` rendert `email_clients_without_accounts` sowie `installed`/`active_source` für DNS-/Web-Anwendungen.
  - `FeedbackSynthesisSignature` und `docs/references/LLM-Prompts.md` verbieten konkrete technische Werte, wenn sie nicht eindeutig aus Analyse oder Schülerabgabe belegt sind.
  - Golden-Files wurden aus dem Renderer neu erzeugt.
- Verifikation:
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py::test_filius_legacy_email_client_konten_file_renders_metadata_without_secrets backend/tests/test_filius_evidence_v1.py::test_filius_synthetic_dns_web_fixture_renders_safe_dns_and_web_evidence backend/tests/learning_adapters/test_signature_docstrings_match_prompt_reference.py::test_feedback_synthesis_contract_avoids_unverifiable_technical_suggestions` -> 3 passed.
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py backend/tests/learning_adapters/test_signature_docstrings_match_prompt_reference.py` -> 27 passed.
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py backend/tests/test_filius_fls_validation.py backend/tests/test_learning_filius_fls_submission_api.py backend/tests/learning_adapters/test_signature_docstrings_match_prompt_reference.py backend/tests/learning_adapters/test_feedback_program_dspy.py backend/tests/learning_adapters/test_feedback_program_dspy_prompt.py` -> 42 passed.
  - `git diff --check` -> passed.
  - `make verify` -> passed:
    - Backend: 1538 passed, 33 skipped.
    - Node/H5P: 15 passed.
    - Supabase/OpenAI-smoke: 2 passed.
    - E2E: 13 passed.

### 2026-05-09 — Slice 23: PR-Cleanup vor Review

- Geprüfte Codeabschnitte vor Implementierung:
  - `backend/filius/evidence_v1.py`: Text-Escaping und Markdown-Rendering für mehrzeilige Webserver-Dateien.
  - `backend/tests/test_filius_migrations_contract.py`: statische Migrationsvertragsprüfungen.
  - `backend/tests/test_third_party_notices_contract.py` und `THIRD_PARTY_NOTICES.md`: zentrale Third-Party-Notice-Verträge.
  - `supabase/migrations/*filius*.sql`: Filius-Migrationsnamen und Reihenfolge.
- Befund:
  - `git diff --check master...HEAD` fand trailing whitespace in generierten Filius-Golden-Files.
  - Zwei Filius-Migrationen nutzten ungültige Timestamp-Präfixe (`11:80:00`, `11:90:00`) und wirkten damit nicht wie `supabase migration new`.
  - Die zentralen Third-Party-Notices dokumentierten nur offizielle Filius-GPL-Fixtures, aber nicht die inf-schule-CC-BY-SA-Fixtures.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_filius_migrations_contract.py::test_filius_migration_names_use_valid_supabase_timestamps backend/tests/test_third_party_notices_contract.py::test_third_party_notices_document_filius_fixtures` -> 2 erwartete Fails.
  - `git diff --check master...HEAD` -> erwarteter Fail wegen trailing whitespace in Filius-Golden-Files.
- GREEN:
  - `_safe_text` trimmt Zeilenenden innerhalb mehrzeiliger Evidence-Felder; Golden-Files wurden aus dem Renderer neu erzeugt.
  - Filius-Migrationen wurden auf gültige, sortierte Timestamp-Präfixe umbenannt:
    - `20260507115800_unit_tasks_kind_filius.sql`
    - `20260507115900_learning_submissions_file_kind_filius_fls.sql`
    - `20260507120000_storage_submissions_bucket_allow_filius_fls.sql`
  - `THIRD_PARTY_NOTICES.md` dokumentiert jetzt zusätzlich inf-schule-Fixtures zentral und präzisiert den Filius-GPL-Hinweis.
  - Contract-Tests prüfen gültige Filius-Migrationstimestamps und zentrale Fixture-Notices.
- Verifikation:
  - `.venv/bin/pytest -q backend/tests/test_filius_migrations_contract.py backend/tests/test_third_party_notices_contract.py backend/tests/test_filius_evidence_v1.py` -> 19 passed.
  - `git diff --check master` -> passed.
  - `make verify` -> passed:
    - Backend: 1540 passed, 33 skipped.
    - Node/H5P: 15 passed.
    - Supabase: 5 passed.
    - OpenAI-smoke: 2 passed.
    - E2E: 13 passed.

### 2026-05-09 — Slice 24: Evidence-Konsistenz und MIME-Konstanten

- Geprüfte Codeabschnitte vor Implementierung:
  - `frontend/src/lib/components/learning-unit/LearningSubmissionArtifactView.svelte`: gemeinsames Rendering für Scratch-/Filius-Strukturansichten.
  - `frontend/src/lib/styles/app.css`: bestehende `.scratch-evidence`-Styles und fehlende Filius-Entsprechung.
  - `frontend/src/lib/utils/submission-artifacts.ts` und `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte`: Frontend-MIME-Entscheidungen für Spezialabgaben.
  - `backend/storage/learning_policy.py`, `backend/storage/*_validation.py`, `backend/web/routes/learning.py`, `backend/web/main.py`, `backend/learning/repo_db.py`, `backend/learning/adapters/local_vision.py`: Backend-MIME-Konstanten, Upload-Policy, Repo-Guard und Worker-Routing.
- Befund:
  - Filius-Evidence wurde mit `filius-evidence` gerendert, bekam aber nicht die bestehenden Strukturstyles von Scratch.
  - Filius-, Scratch- und MakeCode-MIME-Strings waren an mehreren Runtime-Stellen verteilt.
  - OpenAPI, Migrationen, Supabase-Config und Legacy-JS bleiben absichtlich literal-basiert, weil sie Verträge/Konfiguration bzw. ein separater Browser-Script-Kontext sind.
- RED:
  - `.venv/bin/pytest -q backend/tests/test_learning_storage_policy_contract.py` -> erwarteter Fail wegen fehlendem `backend.storage.mime_types`.
  - `npm test -- --run src/lib/utils/submission-artifacts.test.ts src/lib/components/learning-unit/LearningSubmissionWorkspace.test.ts` -> erwartete Fails wegen fehlendem `submission-mime-types.ts` und fehlender `structure-evidence`-Klasse.
- GREEN:
  - `backend/storage/mime_types.py` bündelt zentrale Learning-Upload-MIME-Konstanten und Allowlist-Sets.
  - Backend-Runtime-Module importieren Scratch/MakeCode/Filius/PDF/Image-MIMEs aus `mime_types.py`; Validator-Module behalten ihre bisherigen Konstantennamen als Re-Export-kompatible Imports.
  - `frontend/src/lib/utils/submission-mime-types.ts` bündelt die Svelte/TS-MIME-Konstanten für Upload- und Artifact-Fluss.
  - `LearningSubmissionArtifactView.svelte` rendert Struktur-Evidence mit gemeinsamer Klasse `structure-evidence` plus spezifischem Hook (`scratch-evidence`/`filius-evidence`).
  - `app.css` nutzt `structure-evidence` für die bisherigen Strukturstyles, damit Scratch und Filius konsistent dargestellt werden.
- Verifikation:
  - `.venv/bin/pytest -q backend/tests/test_learning_storage_policy_contract.py backend/tests/test_filius_upload_client_surface_contract.py backend/tests/test_learning_submission_kind_guard.py` -> 13 passed.
  - `.venv/bin/pytest -q backend/tests/test_learning_filius_fls_upload_intent.py backend/tests/test_learning_filius_fls_submission_api.py backend/tests/learning_adapters/test_local_vision_filius_fls.py backend/tests/test_filius_evidence_v1.py` -> 25 passed.
  - `npm test -- --run src/lib/utils/submission-artifacts.test.ts src/lib/components/learning-unit/LearningSubmissionWorkspace.test.ts` -> 11 passed.
  - `npm test -- --run src/lib/components/learning-unit/LearningTaskCard.test.ts src/lib/utils/submission-artifacts.test.ts` -> 34 passed.

## Kontext / Problem

GUSTAV unterstützt für besondere Aufgabenformate bereits upload-only Abgaben:

- Scratch: `.sb3` wird validiert, deterministisch zu `scratch.evidence.v2` extrahiert und anschließend vom Feedback-LLM bewertet.
- Calliope: MakeCode `.hex` wird validiert, deterministisch zu `makecode.evidence.v1` extrahiert und anschließend vom Feedback-LLM bewertet.

Filius-Aufgaben sollen in dieselbe Architektur passen. Schüler laden eine Filius-Projektdatei (`.fls`) hoch. GUSTAV extrahiert daraus einen menschenlesbaren, reproduzierbaren Evidence-Text, zeigt diesen als Abgabe an und nutzt ausschließlich diesen Text für Analyse und Rückmeldung.

Eine echte inf-schule-Beispieldatei (`filius_webserver.fls`) bestätigt die technische Grundlage: `.fls` ist ein ZIP-Archiv mit `projekt/konfiguration.xml`. Diese XML ist ein `java.beans.XMLDecoder`-Dokument und enthält nacheinander Projektversion, Knoten, Kabel und Dokumentation. Weil `XMLDecoder` für untrusted data ein Deserialisierungsrisiko wäre, darf GUSTAV die Datei in der ersten Filius-Implementierung nicht per Java-Deserialisierung laden.

## Zielbild (vollständige erste Filius-Implementierung)

- Lehrkraft erstellt `Task.kind=filius`.
- Schüler können bei Filius-Tasks nur `.fls` hochladen.
- API validiert `.fls` früh beim Finalisieren der Abgabe:
  - kein ZIP oder defektes ZIP -> `400 invalid_filius_archive`
  - fehlendes `projekt/konfiguration.xml` -> `400 missing_filius_configuration`
  - XML nicht als erlaubtes Filius-XML interpretierbar -> `400 invalid_filius_configuration`
  - XML/Container überschreitet harte Limits -> `400 filius_configuration_too_large`
  - Storage-Bytes nicht abrufbar -> `503 filius_validation_unavailable`
- Worker-Pipeline bleibt wie bei Scratch/Calliope:
  - kein OCR, kein Vision-Modell
  - deterministische Extraktion aus `.fls` zu `# filius.evidence.v1`
  - Feedback-LLM bewertet Kriterien ausschließlich anhand dieses Evidence-Texts
- Schüler- und Lehreransicht rendern die Evidence als kompakten Topologiebericht, nicht als Roh-XML.
- Vollständig heißt: GUSTAV extrahiert alle fachlich relevanten, sicher und deterministisch aus der `.fls` lesbaren Filius-Simulationsdaten.
- Vollständig heißt nicht: Java-Objekte rekonstruieren, Filius-Code ausführen, Roh-XML übernehmen oder Passwörter in Evidence, Logs oder LLM-Kontext übernehmen.

## User Story

Als Informatiklehrkraft möchte ich Filius-Projekte als `.fls` einreichen lassen, damit GUSTAV Netzwerkaufgaben nachvollziehbar auswerten kann und Schüler eine verständliche Rückmeldung auf Basis ihrer tatsächlichen Projektkonfiguration erhalten.

## BDD-Szenarien

1. Filius-Task erstellen
   Given eine Lehrkraft erstellt eine Aufgabe mit `filius: {}`
   When die Teaching-API die Aufgabe speichert
   Then hat die Aufgabe `kind=filius` und gibt ein leeres `filius`-Config-Objekt zurück.

2. Upload-only UI
   Given `Task.kind=filius`
   When ein Schüler die Task-Seite öffnet
   Then sieht er nur ein Upload-Feld für `.fls`.

3. Upload-Intent erlaubt nur FLS
   Given `Task.kind=filius`
   When Upload-Intent mit `kind=file`, Dateiname `projekt.fls` und MIME `application/x.filius.fls` angefragt wird
   Then enthält die Response `accepted_mime_types=["application/x.filius.fls"]`.

4. Submission akzeptiert gültige FLS
   Given `Task.kind=filius` und eine gültige `.fls` mit `projekt/konfiguration.xml`
   When `POST .../submissions` mit `kind=file` und Filius-Metadata kommt
   Then Response `202`, Submission `analysis_status=pending`.

5. Submission lehnt falsche Abgabearten ab
   Given `Task.kind=filius`
   When ein Schüler Text, Bild, PDF, SB3 oder HEX einreicht
   Then Response `400 invalid_input` oder `400 invalid_file_payload`.

6. Nicht-Filius-Tasks lehnen FLS ab
   Given `Task.kind=native|visual|scratch|calliope`
   When ein Schüler `.fls` einreicht
   Then Response `400 mime_not_allowed` beim Upload-Intent oder `400 invalid_file_payload` beim Finalisieren.

7. Security: defekter Container
   Given eine Datei mit `.fls`-Endung, die kein gültiges ZIP ist
   When sie finalisiert wird
   Then Response `400 invalid_filius_archive`.

8. Security: fehlende Konfiguration
   Given ein gültiges ZIP ohne `projekt/konfiguration.xml`
   When es finalisiert wird
   Then Response `400 missing_filius_configuration`.

9. Security: XML nicht erlaubt
   Given `konfiguration.xml` enthält DOCTYPE/DTD, externe Entities oder unbekannte ausführungsnahe Klassen
   When sie geparst wird
   Then Response `400 invalid_filius_configuration`.

10. Worker: Evidence -> Feedback
    Given eine gültige Filius-Submission
    When der Worker den Job verarbeitet
    Then `text_md` beginnt mit `# filius.evidence.v1`, `analysis_json` bleibt im bestehenden Kriterien-Schema und `feedback_md` wird aus der Evidence erzeugt.

## Contract-first: OpenAPI-Änderungen

- `Task.kind`-Enums erweitern: `native|h5p|visual|scratch|calliope|filius`.
- Neues Schema `FiliusTaskConfig`:
  - leeres Objekt
  - `additionalProperties: false`
  - Beschreibung: upload-only Filius-Projektdatei `.fls`, MIME `application/x.filius.fls`.
- `Task`, `TaskCreate`, `TaskUpdate`, `TeacherUnitNodeEditorTask`, `LearningTask`:
  - optionales Feld `filius`
  - mutually exclusive zu `h5p`, `visual`, `scratch`, `calliope`.
- Learning Upload-Intent:
  - MIME-Beschreibung und Enum um `application/x.filius.fls` erweitern.
  - Beschreibung ergänzt: Für `Task.kind=filius` nur `.fls`.
- Learning Submissions:
  - file-MIME-Enum um `application/x.filius.fls` erweitern.
  - Task-type rules um Filius ergänzen.
  - 400/503 detail codes ergänzen:
    - `invalid_filius_archive`
    - `missing_filius_configuration`
    - `invalid_filius_configuration`
    - `filius_configuration_too_large`
    - `filius_validation_unavailable`

## Datenbank / Migration

- `public.unit_tasks.kind`-Check um `filius` erweitern.
- `public.learning_submissions` file-MIME-Check um `application/x.filius.fls` erweitern.
- Storage-Bucket-Allowlist `submissions` additiv um `application/x.filius.fls` erweitern.
- Keine Filius-spezifischen Spalten in der ersten Implementierung.

## KISS / DRY: zentrale Abgabeformat-Policy

Filius wird als vollständiges Feature umgesetzt; es werden keine fachlich relevanten Filius-Bestandteile bewusst auf später verschoben. Die Komplexität wird stattdessen durch eine kleine zentrale Format-Policy begrenzt.

### Entscheidung

Vor der Filius-Verdrahtung wird die bestehende Scratch/Calliope-Matrix in eine kleine interne Policy in `backend/storage/learning_policy.py` überführt.

Diese Policy beschreibt pro upload-only Format nur die Upload-/Submission-Regeln:

- `task_kind`
- erlaubte Submission-Art (`file`)
- erlaubte MIME-Typen
- Dateiendung für Storage-Keys
- Upload-Hinweis für die UI
- API-Detail-Code, falls Storage-Bytes für die frühe Validierung nicht geladen werden können

Diese Policy ist keine Plugin-Architektur. Sie ist nur eine einfache, typisierte Tabelle plus wenige Helper, damit Upload-Intent, Submission-Finalisierung, Repo-Guards und UI dieselbe Quelle der Wahrheit verwenden.

Worker-Backends, Evidence-Builder und Parser-Implementierungen bleiben bewusst außerhalb dieser Policy. Der Worker darf die Policy nutzen, um unterstützte MIME-Typen zu kennen; die eigentliche Extraktion bleibt aber in klar getrennten Formatmodulen (`backend/scratch`, `backend/makecode`, `backend/filius`).

Falls die Policy später zu groß wird, darf sie nach `backend/learning/submission_formats.py` umziehen. Diese Auslagerung ist kein Bestandteil der ersten Filius-Implementierung.

### Format-Matrix

- Scratch: `scratch` -> `application/x.scratch.sb3` -> `.sb3`
- Calliope: `calliope` -> `application/x.makecode.hex` -> `.hex`
- Filius: `filius` -> `application/x.filius.fls` -> `.fls`

Native, Visual und H5P bleiben fachlich unverändert. Visual bleibt Upload-only für Bild/PDF, Native bleibt Text plus Bild/PDF, H5P bleibt eigener synchroner Submission-Typ.

### Nicht-Ziele

- keine generische Submission-Plugin-Schicht
- keine dynamischen Imports aus Konfiguration
- keine neue Datenbanktabelle für Formatregeln
- keine Worker- oder Parser-Registry in der Upload-Policy
- keine Java-Deserialisierung
- keine Aufweichung der bisherigen Security-Guards

## Parser-Strategie

### Entscheidung

Die erste Filius-Implementierung nutzt einen Python-Allowlist-Parser:

- ZIP wird wie bei Scratch streng begrenzt gelesen.
- `projekt/konfiguration.xml` wird nie mit Java `XMLDecoder` deserialisiert.
- XML wird als Datenformat per allowlisted Parser interpretiert.
- Unbekannte, nicht fachlich ausgewertete XML-Teile werden nicht ausgeführt und nicht ungefiltert in Evidence übernommen.

### Begründung

Filius speichert Projekte als Java-XMLDecoder-Format. Ein Java-Worker mit Filius-Klassen wäre funktional attraktiv, würde aber untrusted Schülerdateien in einen Deserialisierungspfad bringen. Für GUSTAV im Schulkontext ist die sichere Default-Architektur daher: nur Daten extrahieren, keine Objekte rekonstruieren, keine Methoden ausführen.

Ein isolierter Java-Worker bleibt als spätere technische Ausweichstrategie möglich, falls reale Filius-Dateien mit dem Allowlist-Parser nicht zuverlässig genug abdeckbar sind. Dieser Worker müsste dann in einem eigenen Container ohne Netzwerk, ohne Secrets, mit read-only RootFS, CPU-/RAM-Limits und klarer JSON-Schnittstelle laufen. Diese Option ist kein Bestandteil der ersten Implementierung.

### Parser-Allowlist v1

Die Allowlist ist die zentrale Datenstruktur des Filius-Parsers. Sie wird im Code explizit gepflegt und getestet. Sie beschreibt, welche Java-Klassen und welche Properties aus dem XML fachlich ausgewertet werden dürfen. Alles andere wird weder ausgeführt noch roh in Evidence übernommen.

Erlaubte Hauptbereiche:

- Projektstruktur:
  - Versionsstring als erstes XML-Objekt.
  - Knotenliste aus `filius.gui.netzwerksicht.GUIKnotenItem`.
  - Kabelliste aus `filius.gui.netzwerksicht.GUIKabelItem`.
  - Dokumentationsliste aus `filius.gui.netzwerksicht.GUIDocuItem`.
- Hardware/Knoten:
  - bekannte Knotenklassen aus `filius.hardware.knoten.*`, mindestens Rechner/Notebook/Switch/Vermittlungsrechner/Modem.
  - ausgewertete Properties: Name/Label, GUI-Position, Netzwerkinterfaces, Systemsoftware.
  - unbekannte Hardwareklassen werden als `unknown`-Knoten mit Java-Klasse und auswertbaren Basisdaten geführt, nicht abgelehnt.
- Netzwerkinterfaces:
  - Properties: IP, Subnetzmaske, Gateway, DNS, MAC, Port, Wireless-Flag.
  - mehrere Interfaces pro Knoten sind erlaubt und werden stabil sortiert.
- Links:
  - `GUIKabelItem.kabelpanel.ziel1/ziel2` zur Zuordnung der Endpunkte.
  - Wireless-Flag aus dem Kabelobjekt, falls persistent vorhanden.
- Systemsoftware:
  - `InternetKnotenBetriebssystem` mit Dateisystem, installierten Anwendungen, Weiterleitungstabelle, DHCP/RIP/IP-Forwarding-Indizien, Standard-Gateway und DNS-Server-Feld, soweit persistent vorhanden.
- Anwendungen:
  - bekannte Standard-Anwendungen werden mit Java-Klasse, Anzeigename und fachlich relevanter Konfiguration aufgenommen.
  - unbekannte Standard-Anwendungen werden als `unknown_application` mit Java-Klasse gezählt, nicht abgelehnt.
- Routing:
  - manuelle Routen aus `Weiterleitungstabelle.manuelleTabelle`.
  - automatische Routen werden nur aus Interfaces/Gateways abgeleitet und klar als `derived` markiert.
- Firewall:
  - `Firewall`, `FirewallRule`, `FirewallWebKonfig`.
  - Properties: `activated`, `defaultPolicy`, `dropICMP`, `filterSYNSegmentsOnly`, `filterUdp`, `srcIP`, `srcMask`, `destIP`, `destMask`, `protocol`, `port`, `action`.
- Dateisystem:
  - Nur fachlich relevante Simulationspfade: `/dns/hosts`, `/webserver/*`, `/www.conf/vhosts`, E-Mail-Konfigurations-/Mailbox-Dateien, soweit sie als Filius-Dateisystemdaten persistiert sind.
  - Alle Dateiinhalte sind bounded, escaped und mit Truncation-Hinweisen versehen.
- E-Mail:
  - Mailserver-/Client-Apps, Domains, Server, Ports, Konten, simulierte E-Mail-Adressen, Betreff und bounded Mailkörper werden aufgenommen.
  - Passwörter werden nie aufgenommen.
- Dokumentation:
  - `GUIDocuItem` mit Typ, Text, Position, Größe, Farbe als einfache Werte, soweit vorhanden.
- Eigene Anwendungen:
  - `projekt/anwendungen/**` nur als Pfad, Größe und SHA-256.
  - Keine Ausführung, keine Quelltextanalyse, kein Inhalt im LLM-Kontext.

### Fehler- und Unknown-Semantik

Harte API-Fehler:

- `invalid_filius_archive`: kein ZIP, kaputtes ZIP, negative/inkonsistente ZIP-Metadaten.
- `missing_filius_configuration`: `projekt/konfiguration.xml` fehlt.
- `filius_configuration_too_large`: ZIP, XML, Dateianzahl, Dateisystemauszüge oder Evidence überschreiten harte Limits.
- `invalid_filius_configuration`: XML ist syntaktisch kaputt, enthält DOCTYPE/DTD/externe Entities, verletzt die erwartete Filius-Grundstruktur oder nutzt ausführungsnahe/gefährliche XMLDecoder-Konstrukte außerhalb der Allowlist.
- `filius_validation_unavailable`: Storage-Bytes können zur frühen Validierung nicht geladen werden.

Keine API-Fehler:

- unbekannte, passive Filius-Klassen oder Properties innerhalb einer ansonsten validen Projektdatei.
- fachlich noch nicht ausgewertete, aber nicht gefährliche XML-Teile.
- abgeschnittene, zu lange Simulationsinhalte.

Diese Fälle erscheinen stattdessen im Evidence-Abschnitt `Parser Notes` mit Zählern, Klassennamen und Truncation-Hinweisen. Roh-XML wird dort nicht ausgegeben.

## Evidence-Format `filius.evidence.v1`

Die Evidence ist ein kompakter Topologiebericht. Kompakt heißt: fachlich relevante Netzwerkdaten bleiben enthalten; Java-/Swing-/XML-Rauschen wird entfernt.

Der Output ist deterministisch: gleicher Input erzeugt byte-stabilen Markdown-Output. Listen werden stabil sortiert, synthetische IDs werden aus der Reihenfolge der normalisierten Daten vergeben, und alle nutzergesteuerten Texte werden Markdown-sicher escaped.

### Stabile Abschnittsreihenfolge

`filius.evidence.v1` wird immer in dieser Reihenfolge gerendert:

1. `# filius.evidence.v1`
2. `## Project`
3. `## Parser Notes`
4. `## Nodes`
5. `## Links`
6. `## Routing`
7. `## Firewall`
8. `## DNS`
9. `## Web`
10. `## Email`
11. `## Documentation`
12. `## Custom Applications`

Leere Abschnitte bleiben sichtbar mit `none`, damit Kriterien nicht zwischen „nicht vorhanden“ und „nicht extrahiert“ raten müssen.

### Sortierung und IDs

- Knoten: `n1`, `n2`, ... nach stabiler GUI-/XML-Reihenfolge; bei Gleichstand nach normalisiertem Namen und Klasse.
- Interfaces: `n1-if1`, `n1-if2`, ... nach XML-Reihenfolge, danach IP/MAC.
- Links: `e1`, `e2`, ... nach normalisierten Endpunkt-IDs.
- Anwendungen, Routen, Firewall-Regeln, DNS-/Web-/E-Mail-Einträge: stabil nach fachlichen Schlüsselwerten, dann Originalreihenfolge.

### Limits und Truncation

Die Grenzwerte werden als Konstanten im Filius-Modul definiert und in `Parser Notes` ausgegeben.

### Limit-Stichprobe

Die Defaults orientieren sich an vier realen inf-schule-Dateien:

| Datei | `.fls` Bytes | ZIP-Einträge | unkomprimiert gesamt | `konfiguration.xml` |
| --- | ---: | ---: | ---: | ---: |
| `E-Mail_Netzwerk.fls` | 3.476 | 2 | 37.631 | 37.631 |
| `filius_mehrere_netze.fls` | 3.758 | 2 | 49.106 | 49.106 |
| `filius_ClientServer.fls` | 4.589 | 2 | 75.700 | 75.700 |
| `filius_webserver.fls` | 5.572 | 2 | 90.362 | 90.362 |

Die größten beobachteten Mengen in dieser Stichprobe sind: 16 Knoten, 17 Kabel, 10 installierte Anwendungen, 6 Doku-Elemente, 3 E-Mail-Konten, ca. 410 `<object>`-Elemente und ca. 919 `<void>`-Elemente. Die Limits liegen bewusst deutlich darüber, damit umfangreiche Unterrichtsprojekte funktionieren, aber ZIP-Bombs und Prompt-Kontext-Explosionen früh abgefangen werden.

### Konkrete Defaults

- `FILIUS_MAX_INPUT_BYTES = LEARNING_MAX_UPLOAD_BYTES` (aktuell 10 MiB, aus zentraler Learning-Upload-Policy)
- `FILIUS_MAX_ZIP_ENTRIES = 256`
- `FILIUS_MAX_TOTAL_UNCOMPRESSED_BYTES = 50_000_000`
- `FILIUS_MAX_CONFIGURATION_XML_BYTES = 8_000_000`
- `FILIUS_MAX_CUSTOM_APP_BYTES = 2_000_000` je Datei unter `projekt/anwendungen/**`
- `FILIUS_MAX_NODES = 256`
- `FILIUS_MAX_LINKS = 512`
- `FILIUS_MAX_INTERFACES = 512`
- `FILIUS_MAX_APPLICATIONS = 512`
- `FILIUS_MAX_ROUTES = 512`
- `FILIUS_MAX_FIREWALL_RULES = 512`
- `FILIUS_MAX_FILESYSTEM_FILES = 256`
- `FILIUS_MAX_EMAIL_ACCOUNTS = 128`
- `FILIUS_MAX_EMAIL_MESSAGES = 512`
- `FILIUS_MAX_DOCUMENTATION_ITEMS = 256`
- `FILIUS_MAX_TEXT_FIELD_CHARS = 2_000`
- `FILIUS_MAX_FILE_EXTRACT_CHARS = 4_000`
- `FILIUS_MAX_EMAIL_BODY_CHARS = 4_000`
- `FILIUS_MAX_EVIDENCE_CHARS = 65_536`

Wenn ein fachlicher Inhalt gekürzt wird, bleibt der Datensatz erhalten und enthält einen klaren Hinweis wie `[truncated: original_chars=12345 shown_chars=4000]`.

### Enthalten

- Projekt:
  - Filius-Version aus dem Versionsstring
  - Schema `filius.evidence.v1`
  - Datei-/Parser-Limits und Truncation-Hinweise, falls relevant
- Knoten:
  - stabile synthetische IDs (`n1`, `n2`, ...)
  - Java-Klasse und normalisierter Gerätetyp (`computer`, `notebook`, `switch`, `router`, `modem`, `unknown`)
  - sichtbarer Name bzw. Label, soweit vorhanden
  - Interfaces mit IP, Subnetzmaske, Gateway, DNS, MAC, Wireless-Flag
  - DHCP-Konfiguration, RIP-Flag, IP-Forwarding-Indizien soweit persistent vorhanden
- Links:
  - stabile synthetische IDs (`e1`, ...)
  - Start-/Zielknoten aus `GUIKabelItem.kabelpanel.ziel1/ziel2`
  - Wireless-Flag, soweit persistent vorhanden
- Anwendungen:
  - installierte Standard-Anwendungen mit Java-Klasse und Aktivitätsstatus, z. B. Webserver, DNS-Server, Terminal, Browser, E-Mail, Firewall
- Routing:
  - manuelle Einträge aus `Weiterleitungstabelle.manuelleTabelle`
  - abgeleitete Netze aus Interface-IP/Subnetzmaske
  - abgeleitete Default-Gateway-Sicht, aber klar als abgeleitet markiert
- Firewall:
  - installierte Firewall/App-Konfiguration
  - `activated`, `defaultPolicy`, `dropICMP`, `filterSYNSegmentsOnly`, `filterUdp`
  - Regeln mit `srcIP`, `srcMask`, `destIP`, `destMask`, `protocol`, `port`, `action`
  - Protokoll-Codes normalisiert: `-1=*`, `1=ICMP`, `6=TCP`, `17=UDP`; Action `0=DROP`, `1=ACCEPT`
- Sichere Dateisystem-Auszüge:
  - `/dns/hosts`
  - `/webserver/*`
  - `/www.conf/vhosts`
  - jeweils bounded, textuell, mit Pfad und gekürztem Inhalt
- E-Mail:
  - Mailserver-/Client-Apps, Domain, Server/Ports
  - Kontennamen und simulierte E-Mail-Adressen
  - Betreff und bounded Mailkörper, wenn in der Filius-Datei persistent vorhanden
  - niemals Passwörter
  - Nachrichtenanzahl und Truncation-Hinweise
- Dokumentation:
  - `GUIDocuItem` mit Typ, Text, Position und Größe
- Eigene Anwendungen:
  - Dateien unter `projekt/anwendungen/**` nur als Pfad, Größe und SHA-256
  - keine Ausführung, keine Quelltextanalyse, kein Inhalt im LLM-Kontext

### Bewusst nicht enthalten

- Swing-/GUI-Rohdetails ohne fachliche Bedeutung: Icon-Pfade, Look-and-feel-Klassen, MouseListener, Font-Objekte außer dokumentationsnahen Basisdaten.
- Java-Objekt-IDs als fachliche IDs. GUSTAV erzeugt eigene stabile IDs.
- Thread-Namen und Prioritäten.
- Vollständige Roh-XML.
- Passwörter.
- Vollständige unbounded Mailboxen oder Dateiinhalte.

## Security / Hardening

- ZIP-Bomb-Schutz:
  - maximale Dateianzahl
  - maximale komprimierte und unkomprimierte Gesamtgröße
  - maximales `konfiguration.xml`
  - keine Extraktion auf Dateisystem
- Pfadschutz:
  - nur `projekt/konfiguration.xml` und optional `projekt/anwendungen/**`
  - keine absoluten Pfade, keine `..`-Segmente
- XML-Schutz:
  - DTD/DOCTYPE/externe Entities ablehnen
  - keine Java-Deserialisierung
  - nur erlaubte Klassen/Properties auswerten
- Prompt-Injection-Hardening:
  - Nutzertexte JSON-/Markdown-sicher escapen
  - harte Längenlimits pro Feld und Gesamt-Evidence
  - Truncation explizit markieren
- Datenschutz / Simulationsdaten:
  - keine Passwörter
  - E-Mail-Adressen und Mailkörper aus Filius gelten als Simulationsdaten und dürfen bounded in Evidence erscheinen
  - keine vollständigen Evidence-Reports in Logs
  - keine Netzwerkzugriffe aus Dateiinhalten oder URLs

## Relevante Implementierungsstellen

- OpenAPI: `api/openapi.yml`
- Teaching Task Service: `backend/teaching/services/tasks.py`
- Learning Upload Policy: `backend/storage/learning_policy.py`
- Learning API: `backend/web/routes/learning.py`
- Learning Repo Guards: `backend/learning/repo_db.py`
- Worker Evidence-Branch: `backend/learning/adapters/local_vision.py`
- Evidence Rendering UI: `backend/web/evidence_rendering.py`, `backend/web/main.py`
- Storage/DB Migrationen: `supabase/migrations/`, `supabase/config.toml`
- Neue Module:
  - `backend/storage/filius_validation.py`
  - `backend/filius/evidence_v1.py`
  - `backend/filius/__init__.py`
- Kleine zentrale Format-Policy/Helper:
  - in `backend/storage/learning_policy.py`
  - nur für Upload-/Submission-Regeln, nicht als Worker-/Parser-Registry

## Dokumentation

Die Umsetzung aktualisiert nicht nur den API-Vertrag, sondern auch die kanonischen Referenzdocs. Filius ändert öffentlich sichtbare Aufgabenformate, Upload-MIME-Regeln, Storage-Allowlists und die Learning-AI-Pipeline. Diese Dokumentationsänderungen gehören in denselben PR wie die Implementierung.

### Pflichtänderungen

- `docs/references/learning.md`:
  - Learning Upload-Intent und Submission-Regeln um `Task.kind=filius` und `application/x.filius.fls` ergänzen.
  - Scratch, Calliope und Filius als upload-only Formate mit deterministischer Evidence statt OCR beschreiben.
  - Filius-Fehlercodes dokumentieren: `invalid_filius_archive`, `missing_filius_configuration`, `invalid_filius_configuration`, `filius_configuration_too_large`, `filius_validation_unavailable`.
- `docs/references/learning_ai.md`:
  - Worker-/Vision-Pipeline ergänzen: Scratch, Calliope und Filius erzeugen deterministische Evidence und laufen danach durch die normale Text-Feedback-Pipeline.
  - Klarstellen: Filius nutzt keinen OCR-/Vision-Aufruf, keine Java-Deserialisierung und loggt keine Roh-Evidence.
- `docs/references/storage_and_gateway.md`:
  - `submissions`-Bucket-Allowlist um `application/x.filius.fls` ergänzen.
  - Learning-Upload-MIME-Liste aktualisieren: PDF, SB3, HEX, FLS plus Bilder für native/visual Pfade.
  - Hinweis auf bounded serverseitige Validierung von `.fls`-Archiven aufnehmen.
- `docs/references/teaching.md`:
  - Task-Dokumentation aktualisieren: `Task.kind = native|h5p|visual|scratch|calliope|filius`.
  - `FiliusTaskConfig` als leeres upload-only Config-Objekt dokumentieren.
  - bestehende veraltete Aussage `kind` sei aktuell stets `native` entfernen.
- `docs/database_schema.md`:
  - `public.unit_tasks.kind`-Check um vollständige Kind-Liste inklusive `filius` dokumentieren.
  - `public.learning_submissions` file-MIME-Check inklusive `.fls` dokumentieren.
  - festhalten: keine Filius-spezifischen Spalten.
- `docs/ARCHITECTURE.md`:
  - Teaching-Aufgabenabschnitt aktualisieren: Task-Kinds inklusive Scratch/Calliope/Filius.
  - Learning-AI-Überblick ergänzen: deterministische Evidence-Extractor als Vorstufe zur Feedback-Pipeline.
- `docs/references/LLM-Prompts.md`:
  - ergänzen, dass `student_text_md` bei Scratch/Calliope/Filius ein deterministischer Evidence-Report ist.
  - klarstellen: Das LLM bewertet nur Evidence, nicht Originaldateien.
- `docs/references/teaching_live.md`:
  - Teacher-Latest-Submission-Doku aktualisieren: `text_body`/Textrepräsentation kann bei Filius `filius.evidence.v1` enthalten.
  - Evidence-Rendering für Datei-/Spezialformate erwähnen.
- `docs/glossary.md`:
  - Begriffe ergänzen: `Evidence`, `Abgabeformat/Task.kind`, optional `Filius-Projektdatei`.
  - Begrifflich sauber trennen: `Abgabe` ist der persistierte Submission-Datensatz; `Evidence` ist die deterministische Textrepräsentation einer Datei-Abgabe.
- `docs/references/security_checklist.md`:
  - Untrusted Archive/XML-Regeln ergänzen: bounded ZIP-Lesen, keine Dateisystem-Extraktion, keine Java-Deserialisierung, keine Roh-Evidence in Logs.
- `docs/references/make_targets.md`:
  - Falls `make verify-preflight-db` den `unit_tasks_kind_check` prüft, Hinweis von `inkl. calliope` auf `inkl. filius` aktualisieren.
- `docs/CHANGELOG.md`:
  - Unter `Unreleased` Einträge für API, DB/Storage, AI/Evidence, Docs und Tests ergänzen.
- `README.md`:
  - Kurze Feature-Zeile ergänzen: GUSTAV unterstützt upload-only Aufgabenformate wie Scratch, Calliope und Filius mit deterministischer Evidence-Auswertung.

### Nicht notwendig

- `docs/ROADMAP.md`: bleibt Platzhalter, keine Änderung nötig.
- `.env.example` und `docs/references/config_matrix.md`: nur ändern, falls im Code neue Filius-spezifische ENV-Variablen eingeführt werden. Nach aktuellem Plan werden Limits als Modul-Konstanten umgesetzt, daher keine neue ENV-Doku.
- `docs/tests/storage_strategy.md`: keine Pflichtänderung, da es primär Teaching-Material-Storage beschreibt.

### Acceptance Criteria für Docs

- Keine kanonische Referenzdoc nennt nur `native|h5p|visual`, wenn sie Task-Kinds vollständig aufzählt.
- Keine Learning-/Storage-Referenz listet Upload-MIMEs ohne `application/x.filius.fls`.
- Keine AI-Doku beschreibt Filius als OCR-/Vision-Pfad.
- Keine Doku behauptet, simulierte Filius-Mailkörper würden grundsätzlich ausgeschlossen; sie sind bounded, escaped und ohne Passwörter erlaubt.

## Tests

### Contract Tests

- OpenAPI enthält `FiliusTaskConfig`.
- Alle relevanten `Task.kind`-Enums enthalten `filius`.
- Submission-file-MIME enthält `application/x.filius.fls`.
- Upload-Intent-Beschreibung nennt Filius/FLS.
- 400/503-Beschreibungen nennen Filius-Detailcodes.

### Parser Unit Tests

- gültige `.fls` mit minimalem Knoten/Link-Setup erzeugt Evidence.
- `.fls` mit Webserver-Dateien extrahiert nur erlaubte Webpfade.
- `.fls` mit DNS-Hosts extrahiert DNS-Evidence.
- `.fls` mit manuellen Routen extrahiert manuelle Routen und abgeleitete Netze getrennt.
- `.fls` mit Firewall-Regeln extrahiert Policies und Regeln normalisiert.
- `.fls` mit E-Mail-Konten und simulierten Nachrichten extrahiert Konten, Adressen, Betreff und bounded Mailkörper, aber nie Passwörter.
- `projekt/anwendungen/**` wird nur als Hash/Metadaten sichtbar.
- defektes ZIP, fehlende XML, zu große XML, Pfadtraversal, DTD/DOCTYPE und unbekannte gefährliche XML-Strukturen werden stabil abgelehnt.
- unbekannte passive Filius-Klassen werden als `unknown`/`ignored` in `Parser Notes` markiert und führen nicht zu `400`.

### Evidence Golden-File Tests

- Golden Files sichern byte-stabile `filius.evidence.v1`-Ausgabe für:
  - minimale Topologie
  - Web/DNS/VHosts
  - Routing und abgeleitete Netze
  - Firewall-Regeln
  - E-Mail-Simulationsdaten mit gekürztem Mailkörper
  - Dokumentation und eigene Anwendungen
- Golden Files prüfen Abschnittsreihenfolge, Sortierung, synthetische IDs, Escaping und Truncation-Hinweise.

### API / Integration Tests

- Teaching API erstellt und aktualisiert Filius-Tasks.
- Filius-Task akzeptiert Upload-Intent nur für `application/x.filius.fls`.
- Nicht-Filius-Tasks lehnen Filius-MIME ab.
- Filius-Submission akzeptiert gültige `.fls` und validiert früh.
- Filius-Submission lehnt Text/Bild/PDF/SB3/HEX ab.
- Storage-Policy und Bucket-Provisioning enthalten Filius-MIME.
- Zentrale Format-Policy wird von Upload-Intent, Submission-Finalisierung und Repo-Guard konsistent genutzt:
  - Scratch/Calliope-Verhalten bleibt unverändert.
  - Filius ergänzt die Matrix additiv.
  - Unsupported upload-only MIME-Typen werden bei falschem `Task.kind` abgelehnt.

### Worker / UI Tests

- `local_vision` erzeugt `# filius.evidence.v1` statt OCR/Vision aufzurufen.
- Evidence wird in Schüler- und Lehreransicht mit `filius-evidence`-Wrapper gerendert.
- Roh-XML und Passwörter erscheinen nicht in gerendertem HTML.
- Simulierte Mailkörper erscheinen nur escaped, bounded und mit Truncation-Hinweis, falls gekürzt.

## Quellen / Recherche

- Bestehende GUSTAV-Implementierung:
  - `docs/plan/2026-02-18-scratch-sb3-pipeline.md`
  - `docs/plan/2026-02-23-calliope-makecode-hex-upload-pipeline.md`
  - `backend/storage/sb3_validation.py`
  - `backend/storage/makecode_hex_validation.py`
  - `backend/scratch/sb3_evidence_v2.py`
  - `backend/makecode/hex_evidence_v1.py`
- Filius / inf-schule:
  - `https://inf-schule.de/rechnernetze/filius`
  - `https://inf-schule.de/rechnernetze/filius/internet/erkundung_www`
  - `https://inf-schule.de/rechnernetze/filius/vernetzungrechnernetze/erkundung_mehrerenetze`
  - `https://inf-schule.de/rechnernetze/filius/clientserver/erkundung_clientserver`
  - `https://inf-schule.de/rechnernetze/anwendung/email/filiusemail`
  - Beispiel `filius_webserver.fls`: ZIP mit `projekt/konfiguration.xml`, XMLDecoder-Struktur, Knoten/Kabel/Doku-Listen.
  - Limit-Stichprobe: `filius_webserver.fls`, `filius_mehrere_netze.fls`, `filius_ClientServer.fls`, `E-Mail_Netzwerk.fls`.
- Filius-Quellen:
  - `SzenarioVerwaltung.java`: Projekt-Speichern/Laden
  - `NetzwerkInterface.java`: IP, Subnetzmaske, Gateway, DNS, MAC, Wireless
  - `InternetKnotenBetriebssystem.java`: Dateisystem, installierte Anwendungen, Weiterleitungstabelle, DHCP/RIP
  - `Weiterleitungstabelle.java`: manuelle vs. automatisch abgeleitete Routen
  - `Firewall.java` und `FirewallRule.java`: Firewall-Policies und Regeln
  - `EmailKonto.java` und `EmailServer.java`: E-Mail-Konten enthalten Passwörter und müssen redigiert werden
