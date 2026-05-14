# Learning Upload Content Signature Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject wrong-content learning uploads before persistence and feedback processing.

**Architecture:** The Learning API already validates declared MIME type, task kind, storage integrity, and task-specific formats. This plan adds a small byte-signature validation layer after storage bytes are loaded once and before `CreateSubmissionUseCase` persists a submission or queues worker jobs. Existing Scratch, Filius, and Calliope validators stay the source of truth for deep format validation and receive the already-loaded bytes instead of loading the same object again.

**Tech Stack:** FastAPI route layer, Python storage validators, OpenAPI contract, pytest, SvelteKit/Vitest contract tests.

---

## Summary

User Story: Als Lernende:r möchte ich falsche Dateien sofort verständlich zurückgewiesen bekommen, damit keine ungültige Abgabe erst später als generischer Feedback-Fehler scheitert.

BDD-Szenarien:

- Given eine gültige PNG/JPEG/PDF-Datei, When die Submission finalisiert wird, Then wird sie wie bisher mit `202` angenommen.
- Given eine Filius-/ZIP-Datei wird als PNG oder PDF deklariert, When die Submission finalisiert wird, Then antwortet die API mit `400 invalid_upload_content` und legt keine Submission/Queue-Job an.
- Given Inhaltsbytes können serverseitig nicht geladen werden, When eine Datei-/Bild-Submission finalisiert wird, Then antwortet die API fail-closed mit `503 submission_validation_unavailable`.
- Given ein Calliope-HEX-Soft-Fall als textartige HEX-Datei, Then bleibt die bestehende `202`-Fallback-Evidence-Regel erhalten; binäre ZIP-Inhalte als HEX werden aber mit `invalid_upload_content` abgelehnt.

## Key Changes

- Contract-first: `api/openapi.yml` für `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions` um den neuen `400`-Detailcode `invalid_upload_content` ergänzen.
- Backend: neuen kleinen Validator in `backend/storage/submission_content_signatures.py` einführen. Alle MIME-Vergleiche nutzen die Konstanten aus `backend/storage/mime_types.py`.
  - `image/png`: PNG-Magic + Pillow-Verify `PNG`
  - `image/jpeg`: JPEG-Magic + Pillow-Verify `JPEG`
  - `application/pdf`: muss mit `%PDF-` beginnen
  - `application/x.scratch.sb3` und `application/x.filius.fls`: ZIP-Magic nur generisch prüfen; bestehende SB3/Filius-Validatoren bleiben danach für Strukturdetails zuständig
  - `application/x.makecode.hex`: ZIP-/Binärinhalte ablehnen, textartige HEX-Inhalte aber an die bestehende Calliope-Soft-Regel weiterreichen
- Learning API: in `backend/web/routes/learning.py` nach Storage-Integrity-Check und vor Persistence/Queueing Bytes einmal via `_load_storage_bytes_for_validation(...)` laden, generisch prüfen und dieselben Bytes an Scratch/Calliope/Filius-Spezialvalidatoren weitergeben. Bei Mismatch `400 invalid_upload_content`; bei nicht ladbaren Bytes `503 submission_validation_unavailable`.
- Worker-Fallback: Bild/PDF- und Datei-Adapter behandeln deterministische Signaturmismatches als permanenten Fehler `invalid_upload_content`, damit Altbestände oder anders hineingeratene falsche Uploads kein Retry-Budget verbrauchen.
- Frontend: `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte` behandelt `invalid_upload_content` mit der deutschen Meldung: `Die Datei passt nicht zum erwarteten Dateityp. Bitte wähle die richtige Datei aus.`
- Docs: Referenzen aktualisieren, weil sich API-Fehlersemantik, Upload-Sicherheitskette und Worker-Fallback-Verhalten ändern. Keine Updates für `README.md`, `docs/references/config_matrix.md`, `.env.example` oder `docs/research/*`, da weder neues Setup noch neue ENV-Variablen noch Feedback-Wissenschaft betroffen sind.
- Ticket abschließen: `docs/tickets/learning-upload-content-signature-validation-2026-05-12.md` nach grüner Verifikation mit Status und Prüfbefehlen aktualisieren.

## Implementation Tasks

### Task 1: Contract And OpenAPI Test

**Files:**

- Modify: `api/openapi.yml`
- Modify: `backend/tests/test_openapi_learning_upload_intents_contract.py`

- [ ] Add a failing OpenAPI test asserting that `invalid_upload_content` appears in the Submission `400` contract.
- [ ] Update the OpenAPI Submission `400` description to include `invalid_upload_content`.
- [ ] Run `.venv/bin/pytest -q backend/tests/test_openapi_learning_upload_intents_contract.py`.

### Task 2: Byte-Signature Validator

**Files:**

- Create: `backend/storage/submission_content_signatures.py`
- Test: `backend/tests/test_submission_content_signatures.py`

- [ ] Add unit tests for valid PNG, JPEG, PDF, SB3, FLS, and text-like HEX inputs.
- [ ] Add unit tests rejecting ZIP bytes declared as PNG, PDF, JPEG, or HEX.
- [ ] Implement `validate_submission_content_signature(mime_type: str, data: bytes) -> None`.
- [ ] Raise `ValueError("invalid_upload_content")` for deterministic mismatches.
- [ ] Preserve existing Calliope soft behavior by accepting text-like HEX at this layer; deeper `invalid_hex_file` and `missing_makecode_source` handling remains in the existing Calliope validator/worker path.
- [ ] Run `.venv/bin/pytest -q backend/tests/test_submission_content_signatures.py`.

### Task 3: Learning API Gate

**Files:**

- Modify: `backend/web/routes/learning.py`
- Test: `backend/tests/test_learning_upload_content_signature_validation.py`

- [ ] Add API tests using a fake repo to verify wrong-content image/PDF/HEX payloads return `400 invalid_upload_content` before `create_submission`.
- [ ] Add API tests proving valid PNG/JPEG/PDF bytes still return `202`.
- [ ] Add API test proving missing validation bytes returns `503 submission_validation_unavailable`.
- [ ] Wire the new validator after `_verify_storage_object(...)` and before Scratch/Calliope/Filius task-specific validation and persistence.
- [ ] Refactor the Scratch/Calliope/Filius validation blocks in this route to reuse the already-loaded bytes instead of calling `_load_storage_bytes_for_validation(...)` a second time.
- [ ] Ensure validation logs only low-cardinality reason, MIME, task kind, and byte count; no storage keys, hashes, user IDs, or object paths.
- [ ] Run `.venv/bin/pytest -q backend/tests/test_learning_upload_content_signature_validation.py`.

### Task 4: Worker Fallback For Legacy/Bypassed Mismatches

**Files:**

- Modify: `backend/learning/adapters/local_vision.py`
- Modify: `backend/learning/adapters/local_feedback.py`
- Test: `backend/tests/learning_adapters/test_local_vision_pdf_remote_wrong_content.py`
- Test: `backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py`

- [ ] Add or update adapter tests so PDF/image bytes with a deterministic signature mismatch raise permanent `invalid_upload_content`, not transient `pdf_images_unavailable`, `image_unavailable`, or `visual_feedback_failed`.
- [ ] Reuse `validate_submission_content_signature(...)` in the worker-side byte-loading paths for image/PDF inputs before OCR or visual feedback calls.
- [ ] Keep missing bytes/transient storage failures transient; only loaded bytes that contradict the declared MIME are permanent.
- [ ] Run `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_vision_pdf_remote_wrong_content.py backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py`.

### Task 5: Preserve Existing Upload Families

**Files:**

- Modify: `backend/tests/test_learning_api_contract.py`
- Modify: `backend/tests/test_learning_submission_storage_verification.py`
- Modify Scratch/Calliope/Filius tests only if the one-load API refactor changes their monkeypatch boundary.

- [ ] Run existing Scratch, Calliope, Filius, and storage-verification API tests.
- [ ] Update existing generic image/PDF happy-path tests that currently submit only metadata to provide valid stored PNG/PDF bytes through `STORAGE_VERIFY_ROOT` or to monkeypatch `_load_storage_bytes_for_validation` with valid bytes.
- [ ] Keep Calliope tests `test_calliope_submission_accepts_missing_makecode_source` and `test_calliope_submission_accepts_invalid_hex_file_soft_extraction_error` at `202`.
- [ ] Run:

```bash
.venv/bin/pytest -q \
  backend/tests/test_learning_submission_storage_verification.py \
  backend/tests/test_learning_scratch_sb3_upload_only_api.py \
  backend/tests/test_learning_calliope_hex_upload_only_api.py \
  backend/tests/test_learning_filius_fls_submission_api.py
```

### Task 6: Learner-Facing Message

**Files:**

- Modify: `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte`
- Modify: `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/page-contract.test.ts`

- [ ] Add a route contract test asserting that `invalid_upload_content` maps to the new German wrong-file-content message.
- [ ] Update `submitUploadFeedback(...)` catch handling to show `Die Datei passt nicht zum erwarteten Dateityp. Bitte wähle die richtige Datei aus.`
- [ ] Run `npm test -- --run src/routes/learning/courses/[courseId]/units/[unitId]/page-contract.test.ts` from `frontend/`.
- [ ] Run `npm run check` from `frontend/`.

### Task 7: Documentation Updates

**Files:**

- Modify: `docs/references/learning.md`
- Modify: `docs/references/storage_and_gateway.md`
- Modify: `docs/references/learning_ai.md`
- Modify: `docs/CHANGELOG.md`

- [ ] Update `docs/references/learning.md` in the submissions endpoint section so `invalid_upload_content` appears beside the other `400` detail codes.
- [ ] Update `docs/references/learning.md` in the security section to state that uploaded storage bytes are validated against the declared MIME/task kind before persistence and queueing. Mention the supported content signatures for this ticket: PNG, JPEG, PDF, Scratch SB3 ZIP, Filius FLS ZIP, and text-like MakeCode HEX.
- [ ] Update `docs/references/storage_and_gateway.md` in the Security section to describe the end-to-end learning upload guard: private bucket, presigned upload, storage integrity verification, byte-signature validation, then persistence/queueing. State that signature mismatch fails closed with `invalid_upload_content` and logs must not include storage keys, hashes, user IDs, or object paths.
- [ ] Update `docs/references/learning_ai.md` in the architecture or worker lifecycle section to clarify that the API is the primary validation gate and worker-side signature checks are fallback protection for legacy or bypassed mismatches. Deterministic mismatches are permanent, while storage fetch failures remain transient.
- [ ] Add an `Unreleased` changelog entry under Security or API for the new upload content-signature validation and the new `invalid_upload_content` detail code.
- [ ] Do not update `README.md`, `docs/references/config_matrix.md`, `.env.example`, `docs/glossary.md`, or `docs/research/*` unless implementation introduces a new setup step, ENV variable, glossary term, or feedback-science behavior.
- [ ] Keep the WebP scope explicit: current contracts allow image uploads only for `image/png` and `image/jpeg`; WebP requires a separate contract-first change.
- [ ] Run `rg -n "invalid_upload_content|content-signature|Byte-Signatur|Signatur|WebP" docs/references docs/CHANGELOG.md api/openapi.yml` and confirm the docs consistently describe the implemented scope.

### Task 8: Ticket Closure And Full Verification

**Files:**

- Modify: `docs/tickets/learning-upload-content-signature-validation-2026-05-12.md`

- [ ] Add a `Status` section with completion date, behavior summary, and verification commands.
- [ ] Run the focused backend, frontend, and docs grep commands from Tasks 1-7.
- [ ] Run `make verify`.
- [ ] Commit after all checks pass.

## Acceptance Criteria

- Wrong-content uploads are rejected before normal feedback processing starts.
- The learner receives a clear wrong-file-type/content message.
- The worker does not consume retry budget for deterministic signature mismatches.
- Existing valid Filius, image, PDF, Scratch, and Calliope upload paths remain compatible.
- Regression tests cover declared MIME mismatches and byte-signature mismatches.
- Public API, reference docs, changelog, and ticket status describe the new validation behavior and the intentionally unchanged WebP/env/setup scope.

## Assumptions

- New API detail code: `invalid_upload_content`.
- No schema migration is needed.
- Validation is fail-closed for file/image submissions when bytes cannot be loaded.
- Existing MIME/task-kind guards remain unchanged.
- Calliope soft fallback for text-like HEX extraction failures remains intentional.
- WebP is out of scope for this ticket because current `ALLOWED_IMAGE_MIME` accepts only PNG and JPEG. Add WebP only in a separate contract-first change if the product should support it.
