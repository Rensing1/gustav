# Plan: PDF pages are always stitched into a single image

Status: KISS version (agreed)

Owner: Learning/AI

Date: 2025-11-10

## Goal
Always convert submitted PDFs into a single stitched image before OCR. This simplifies the Vision adapter logic (one model call), improves consistency, and reduces outline-like hallucinations from multi-image prompts.

## User Story
As a teacher, when a student submits a PDF, the system should extract text reliably so I can read the student’s content in the history. I don’t care how many pages the PDF has — the system should handle it and return a readable transcript.

## Scope & Non-Goals
- In-scope: Stitch all rendered PDF pages vertically into one image (no resizing, no limits, no separators); call the Vision model once with that single image; persist transcript as before.
- Out-of-scope: Any format/size adjustments, page caps, separators, new APIs, or UI changes. Text and image uploads remain unchanged.

## BDD Scenarios (Given–When–Then)
1) Happy path (small PDF)
   - Given a 2-page PDF rendered successfully
   - When the worker processes the submission
   - Then the Vision adapter stitches pages into one PNG, calls the model once (images=[1]), and stores verbatim transcript

2) Many pages
   - Given a large PDF with many pages
   - When the worker processes the submission
   - Then all available rendered pages are stitched in order; the model is called once; transcript is returned

4) Missing derived pages
   - Given a PDF with derived pages not yet persisted locally
   - When the worker tries to stitch
   - Then it attempts Supabase fetch (service role) to retrieve derived pages; if none found, classify as transient and retry

5) Corrupt page image
   - Given one derived PNG is unreadable
   - When stitching
   - Then that page is skipped; if no pages usable, treat as transient (retry)

6) Security boundary
   - Given RLS and storage integrity checks
   - When reading pages from local root
   - Then path containment and optional sha256 verification hold; no path traversal

## Design
- Rendering unchanged: `backend/vision/pipeline.py` + `pdf_renderer.py` produce per-page PNGs.
- New minimal stitcher `stitch_images_vertically(pages_png: list[bytes]) -> bytes`:
  - No resizing, no separators, no limits. Concatenate all pages vertically in original pixel sizes using Pillow.
  - Return final PNG bytes.
- Vision adapter (`backend/learning/adapters/local_vision.py`):
  - For PDFs: fetch rendered pages (local root first, Supabase as fallback), stitch into a single PNG, call Ollama once with `images=[stitched]` and a strict verbatim transcription prompt (temperature=0).
  - Text submissions remain pass-through; JPEG/PNG continue as single-image calls.

## Configuration
None for behavior toggles — the stitching logic has no knobs in this KISS version.

Runtime dependency (worker):
- pypdfium2 (PDFium bindings) is required to render PDF pages to images before stitching.
  - Added to `backend/web/requirements.txt` so the worker image includes it.
  - Rebuild and restart the learning-worker after updating dependencies.

## Tests (TDD)
1) Unit: stitcher
   - Concatenates two dummy images; resulting image has the original page widths and combined height (sum of both), no separators.

2) Adapter integration: stitched call
   - With two derived page PNGs on disk, assert one `ollama.Client.generate` call with a single image, and transcript unwrapped (no code fences).

3) Worker E2E (local): PDF extracted flow
   - After rendering hook (existing dev/helper), worker completes submission; analysis_json.text contains stitched OCR result.

4) Error cases
   - No derived pages → transient retry.
   - Corrupt page PNG → skip; if zero usable → transient retry.

## Security & Privacy
- Maintain current path containment checks and optional sha256 verification before reading any bytes.
- Never log raw student content.
- Keep transcripts in `analysis_json.text` only for uploads; text submissions remain 1:1 preserved.

## Performance Considerations
- No resizing or caps. This is intentionally simple. Note: very large PDFs may consume more memory/latency; we accept this trade-off for now per product decision. Temperature=0 to reduce hallucinations.

## Rollout
- No DB or API changes; no migrations.
- Ship behind configuration with sane defaults; same behavior in local and prod.
- Monitor logs for Vision retries and timeouts.

## Step-by-step Implementation
1) Add `stitch_images_vertically` in `backend/vision/pipeline.py` (pure Pillow logic, docstring, tests).
2) Update `local_vision.py` PDF path:
   - Load derived pages (local→Supabase fallback), apply `stitch_pages`, call model once.
   - Keep strict, verbatim prompt and code-fence unwrapping.
3) Tests:
   - Add `test_vision_pdf_stitch_unit.py` for stitcher.
   - Adapt `test_learning_vision_pdf_images_param.py` or add `test_learning_vision_pdf_stitched.py` to assert single-call images=[1].
   - Ensure worker E2E for PDF stays green.
4) Docs: Update `docs/CHANGELOG.md` and this plan’s status.

## Open Questions for Felix
- Transcript formatting: reine Fließtext-Transkription ohne künstliche Seiten‑Überschriften? (Vorschlag: kein „Seite N“, reiner OCR‑Text.)

## Acceptance Criteria
- PDFs always go through stitching, single model call, transcript is verbatim, readable, and free of boilerplate outlines.
- Text submissions remain unchanged; image submissions unchanged.
- All targeted tests pass locally and in CI.

## Option 1: Worker fetches original PDF from Supabase and renders (Recommended)

Motivation
- Remove dependency on pre-rendered derived images in dev/prod. Ensure the worker can always produce a single stitched image for any PDF by fetching the original from Supabase Storage with service credentials.

Design Overview
- When processing a PDF submission, the worker ensures a stitched PNG exists via the following order:
  1) Try local `derived/<submission_id>/stitched.png` under `STORAGE_VERIFY_ROOT`.
  2) If missing, fetch the original PDF from Supabase Storage using `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` and `storage_key` from the job.
  3) Render pages via `process_pdf_bytes`, stitch vertically with `stitch_images_vertically`, and (best-effort) persist `derived/<submission_id>/stitched.png` back to local root and/or Supabase for re-use.
- Only then call the vision model once with `images=[stitched]`. Never call without images.

Security
- Path containment for any local writes; no raw student content in logs.
- Optional integrity checks: compare `size_bytes` and `sha256` from job payload against the fetched bytes.
- Use service role key only from server-side env; never expose to clients.

Env/Config
- Requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (already present in `.env` and compose service envs).
- No API contract changes.

Implementation Steps
1) Extend `_ensure_pdf_stitched_png` to:
   - If local stitched not found, try Supabase GET for original PDF: `GET {SUPABASE_URL}/storage/v1/object/submissions/{storage_key}` with service role auth headers.
   - Verify `size_bytes`/`sha256` if provided; render pages → stitch → return bytes; best-effort persist stitched for reuse.
   - Return `None` if fetch/render fails, so caller raises `VisionTransientError('pdf_images_unavailable')`.
2) Add concise telemetry:
   - `learning.vision.pdf_ensure_stitched action=load|fetch|render persisted=true|false submission_id=<id>`
3) Keep the adapter rule: for PDFs, never call the model without `images`.

BDD Scenarios (Added)
- Given a PDF stored only in Supabase (no local artifacts), when the worker processes the job, then it fetches the original, renders, stitches, and calls the model once with the stitched image.
- Given network failure or 404 when fetching original PDF, when the worker processes, then it marks a transient error (`pdf_images_unavailable`) and requeues with backoff.
- Given a `sha256` mismatch on fetched bytes, when the worker verifies, then it treats as transient (retry) or failure per policy (start with transient + log).

Tests
- Unit (adapter helper):
  - Mock Supabase GET returning bytes; assert render+stitch happens; stitched bytes returned; best-effort persistence attempted.
  - Mock GET 404; assert `None` returned and that caller raises transient.
  - Mock `sha256` mismatch; assert transient path taken (logged).
- Integration/Adapter:
  - With only remote original: exactly one `ollama.generate(images=[1])` call; no prompt echo.
- Worker E2E:
  - Submit a PDF with only Supabase storage; worker completes after fetching and rendering.

Risks & Mitigations
- Rendering CPU cost: acceptable trade-off; keep DPI=300 and page_limit=100.
- Network dependency on Supabase: handled via transient retries with backoff; logs make cause visible.

Rollout
- Implement + tests; rebuild images; verify with a real PDF submission.
- Optional later: persist stitched back to Supabase for reuse across retries and environments.
