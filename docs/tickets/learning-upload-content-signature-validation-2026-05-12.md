# Ticket: Upload content signature validation for learning submissions

## Summary

On 2026-05-12, multiple non-H5P submissions failed because the declared upload
type did not match the uploaded bytes. The failures were first observed in the
new classroom upload flow.

The failed cases included uploads declared as PDF or PNG/image submissions, but
the stored bytes began with ZIP magic bytes and contained Filius-style project
entries. Storage integrity checks matched the submitted bytes, so this was not
evidence of object corruption. The system accepted a mismatched file type and
only discovered the problem later in feedback processing.

No learner names, user IDs, storage object paths, hashes, or other PII are
included in this ticket.

## Status

Completed on 2026-05-14.

- API submissions validate stored upload bytes before persistence and queueing.
- Wrong-content uploads return `400 invalid_upload_content`; missing validation bytes fail closed with `503 submission_validation_unavailable`.
- Worker-side image/PDF/file fallback treats deterministic signature mismatches as permanent `invalid_upload_content`, while storage fetch failures remain transient.
- Learners see: „Die Datei passt nicht zum erwarteten Dateityp. Bitte wähle die richtige Datei aus.“
- WebP remains out of scope for this ticket because the current Learning upload contract accepts only `image/png` and `image/jpeg` for image uploads.

Verification commands:
- `.venv/bin/pytest -q backend/tests/test_openapi_learning_upload_intents_contract.py`
- `.venv/bin/pytest -q backend/tests/test_submission_content_signatures.py`
- `.venv/bin/pytest -q backend/tests/test_learning_upload_content_signature_validation.py`
- `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_vision_pdf_remote_wrong_content.py backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py`
- `.venv/bin/pytest -q backend/tests/test_learning_submission_storage_verification.py backend/tests/test_learning_scratch_sb3_upload_only_api.py backend/tests/test_learning_calliope_hex_upload_only_api.py backend/tests/test_learning_filius_fls_submission_api.py`
- `npm test -- --run src/routes/learning/courses/[courseId]/units/[unitId]/page-contract.test.ts`
- `npm run check`
- `make verify`

## Impact

- Learners receive slow or generic feedback failures for files that should have
  been rejected immediately.
- Worker retry capacity is spent on deterministic wrong-file-type submissions.
- Teachers can interpret the symptom as broken image/PDF feedback even though
  the real issue is upload content validation.
- Provider calls may be attempted for invalid visual submissions, depending on
  where the mismatch is detected.

## Observed Context

- A PDF-declared upload was not a PDF; bytes started with ZIP magic instead of
  `%PDF-`.
- A PNG/image-declared upload was not an image; bytes started with ZIP magic
  instead of PNG image bytes.
- The ZIP contents were consistent with a Filius project structure.
- Existing repository validation rejects some wrong task/mime combinations, but
  it relies on declared `mime_type` and `submission_kind`; it does not validate
  file signatures.
- Worker-side PDF handling can classify wrong remote PDF content as transient,
  which causes retries even though the payload is deterministically invalid for
  the selected task.

## Files Of Interest

- `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte`
  - `canonicalUploadMimeType(...)` derives the MIME type sent with a submission.
  - `createUploadSubmission(...)` sends `kind`, `mime_type`, `size_bytes`, and
    `sha256` to the learning submission endpoint.
  - This frontend logic should continue to provide useful hints, but must not
    be the only validation layer.
- `backend/learning/repo_db.py`
  - `_validate_task_submission_kind(...)` currently enforces task-kind and
    declared MIME compatibility at the repository boundary.
  - It should either be complemented by signature validation before persistence
    or receive already validated content metadata from the web/storage layer.
- `backend/learning/adapters/local_vision.py`
  - PDF/image extraction detects some wrong-content cases only during feedback
    processing.
  - Wrong content currently reaches paths such as `pdf_images_unavailable`,
    which can be treated as transient.
- `backend/learning/adapters/local_feedback.py`
  - Visual/PDF feedback turns unavailable image/PDF extraction into feedback
    errors and can retry deterministic invalid payloads.
- `backend/tests/test_learning_submission_kind_guard.py`
  - Existing tests cover declared task/mime guard behavior.
  - Add tests for content-signature mismatch coverage at the new validation
    boundary.
- `backend/tests/learning_adapters/test_local_vision_pdf_remote_wrong_content.py`
  - Existing wrong-content behavior is documented as transient.
  - Update or complement tests once deterministic upload mismatches become
    permanent validation errors.

## Required Behavior

- Validate uploaded content by signature/magic bytes before enqueueing feedback
  work for file/image submissions.
- Reject mismatches between task kind, declared MIME type, and detected content
  type with a clear localized error.
- Do not rely solely on browser-provided MIME type, filename extension, or
  frontend canonicalization.
- Treat deterministic signature mismatches as non-retriable if they are caught
  in the worker as a fallback.
- Detect at least:
  - PDF: `%PDF-` header,
  - PNG/JPEG/WebP images: expected image signatures or a trusted image parser,
  - Filius: ZIP container with Filius project structure,
  - Scratch `.sb3`: ZIP container with Scratch project structure,
  - Calliope/MakeCode HEX: expected text/HEX structure.
- Keep error reporting PII-free and avoid logging object paths, hashes, or user
  identifiers.

## Test Scenarios

- Filius ZIP uploaded to a visual/image task is rejected before feedback work is
  queued.
- Filius ZIP uploaded as a PDF/native file is rejected before PDF rendering or
  vision extraction.
- Valid PNG image upload still creates a visual feedback submission.
- Valid PDF upload still creates a PDF/native feedback submission.
- Declared MIME `image/png` with ZIP bytes returns a deterministic validation
  error, not a transient worker retry.
- Declared MIME `application/pdf` with ZIP bytes returns a deterministic
  validation error, not `pdf_images_unavailable`.

## Acceptance Criteria

1. Wrong-content uploads are rejected before normal feedback processing starts.
2. The learner receives a clear wrong-file-type message.
3. The worker does not consume retry budget for deterministic signature
   mismatches.
4. Existing valid Filius, image, PDF, Scratch, and Calliope upload paths remain
   compatible.
5. Regression tests cover both declared MIME mismatches and byte-signature
   mismatches.
