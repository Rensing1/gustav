# Plan: Learning AI — DSPy-only (Feedback + Vision text extraction) via OpenAI-compatible endpoint (no Ollama)

Update (2026-01-13):
- Extend the previous “DSPy-only feedback” plan to also remove **direct Ollama calls from Vision/OCR**.
- Switch from Ollama-specific configuration to a **single OpenAI-compatible endpoint** (e.g. Lemonade server) that operators can point to.

## Context
The learning AI implementation currently has two forms of Ollama coupling:

1) **Feedback** is a hybrid:
   - A DSPy structured path (Signatures + `dspy.Predict`) exists, but
   - legacy prompt builders and direct `ollama` calls still exist as fallbacks.

2) **Vision text extraction** (“OCR” / handwriting / diagrams) still calls the `ollama` Python client directly.

This setup is suboptimal operationally (configuration complexity, portability, performance tuning) and prevents operators from choosing their own OpenAI-compatible LLM/VLM runtime (e.g. Lemonade) by simply configuring:
- one endpoint in `.env`, and
- a list of model names for different purposes (feedback, vision, visual feedback).

This document supersedes `docs/plan/2025-11-18-dspy-only-feedback-pipeline.md` and extends the “DSPy-only, fail-fast + retry” semantics to Vision text extraction as well.

## Decisions
1. **Single OpenAI-compatible endpoint for all models**
   - One endpoint is shared across feedback LLMs and vision-capable models (VLMs); only the model name changes per use case.
   - Proposed env vars:
     - `AI_API_BASE_URL` (required): OpenAI-compatible base URL (e.g. Lemonade)
     - `AI_API_KEY` (optional): API key/token (some servers require none)
   - Existing model selectors remain (same intent as today):
     - `AI_FEEDBACK_MODEL` (text feedback model)
     - `AI_VISION_MODEL` (vision / text extraction model)
     - `AI_VISUAL_MODEL` (optional override for visual feedback; falls back to `AI_VISION_MODEL`)
   - Migration note: `OLLAMA_BASE_URL` / `OLLAMA_HOST` / `OLLAMA_API_BASE` become deprecated and should be removed from Learning code paths.

2. **DSPy-only orchestration for Learning AI**
   - No prompt-builder templates as a second prompt contract.
   - No direct `ollama` client calls in Learning adapters (Feedback *and* Vision).

3. **DSPy Signatures are the single prompt/contract source**
   - Feedback continues to use existing Signatures.
   - Vision text extraction gets a dedicated Signature that outputs Markdown text.

4. **No deterministic fallback outputs**
   - If structured analysis/feedback (or OCR text extraction) cannot be produced, raise an error.
   - The worker handles retries; we do not fabricate default analysis/feedback/OCR text.

5. **DSPy and config are required**
   - If `dspy` is missing, or the endpoint/model env vars are missing → log a reason code and raise (worker retries).

6. **Empty criteria is allowed (Feedback only)**
   - If a teacher provides no rubric criteria, feedback generation is still legitimate.
   - The criteria-based scoring step is skipped and `analysis_json` is `{}`.

7. **No additional input clipping inside Learning AI**
   - Input sizes are validated upstream (upload limits, text length limits).
   - DSPy code does not truncate on its own (avoids “hidden” behavior).

## User Story
**As** an operator (self-hosted school admin) and product owner\
**I want** Learning AI (Vision text extraction + feedback) to be generated exclusively via DSPy and an OpenAI-compatible endpoint\
**So that** deployment is portable (Lemonade/OAI-compatible servers), model choice is configurable via `.env`, the code stays teachable (single prompt contract), and failures are handled consistently via retries instead of hidden fallbacks.

## Scope
### In scope
- Text feedback pipeline (analysis → feedback) for learning submissions:
  - `backend/learning/adapters/local_feedback.py`
  - `backend/learning/adapters/dspy/feedback_program.py`
  - `backend/learning/adapters/dspy/programs.py`
  - `backend/learning/adapters/dspy/signatures.py`
- Visual feedback pipeline (image/PDF → analysis → feedback):
  - `backend/learning/adapters/local_feedback.py` (`analyze_visual`)
  - `backend/learning/adapters/dspy/visual_feedback_program.py`
  - `backend/learning/adapters/dspy/programs.py`
  - `backend/learning/adapters/dspy/signatures.py`
- Vision text extraction (image/PDF → Markdown text) via DSPy Signature:
  - `backend/learning/adapters/local_vision.py` (remove direct `ollama` calls)
  - `backend/learning/adapters/dspy/signatures.py` (add `VisionTextExtractionSignature`)
  - `backend/learning/adapters/dspy/programs.py` (add `run_structured_vision_text_extraction(...)`)
- Configuration consolidation:
  - `backend/learning/config.py` (replace Ollama-specific base URL parsing with `AI_API_BASE_URL`)
  - Worker DSPy bootstrap (configure LM from `AI_API_BASE_URL` and model name)
  - `.env.example` and `docker-compose.yml` alignment (documented + tested)
- Test suite updates to reflect the new semantics (TDD: red → green → refactor).
- Documentation alignment:
  - `docs/references/LLM-Prompts.md`
  - `docs/references/learning_ai.md` (remove “Ollama-only” wording; document endpoint+models)

### Out of scope
- API contract changes (`api/openapi.yml`) – no endpoint behavior changes intended.
- Database schema changes/migrations.
- UI behavior changes (student/teacher pages).

## Target Behavior (error semantics)
### High-level rule
**Any failure to produce valid DSPy outputs is an error and should trigger worker retries.**

### Error classification in the worker
The worker distinguishes:
- `FeedbackTransientError` → retry with backoff until MAX_RETRIES, then mark `feedback_failed`.
- `FeedbackPermanentError` → mark failed immediately (no retry).
- `VisionTransientError` → retry with backoff until MAX_RETRIES, then mark `vision_failed`.
- `VisionPermanentError` → mark failed immediately (no retry).

Mapping rules:
- Missing `dspy` import → transient.
- Missing config (endpoint/model) → transient.
- DSPy runtime errors (timeouts, network/model errors, invalid output, empty output) → transient.
- Unsupported MIME types → permanent.

## BDD Scenarios (Given–When–Then)
### Text feedback (Task.kind != "visual")
1. **Happy path**
   - Given `dspy` is importable and configured
   - And `AI_API_BASE_URL` is set
   - And criteria is non-empty
   - When the worker calls `FeedbackAdapter.analyze(...)`
   - Then the system returns `FeedbackResult` with:
     - `analysis_json.schema == "criteria.v2"`
     - non-empty `feedback_md`
   - And the adapter does not call `ollama.Client.*` anywhere.

2. **DSPy missing**
   - Given importing `dspy` fails
   - When feedback is requested
   - Then we log a clear error reason (e.g. `dspy_unavailable`)
   - And raise `FeedbackTransientError`.

3. **Config missing**
   - Given `dspy` is importable but `AI_API_BASE_URL` or `AI_FEEDBACK_MODEL` is missing/empty
   - When feedback is requested
   - Then we log `missing_endpoint` / `missing_model`
   - And raise `FeedbackTransientError`.

4. **Empty criteria (allowed)**
   - Given `criteria=[]`
   - When feedback is requested
   - Then we still return a non-empty `feedback_md` generated by DSPy
   - And `analysis_json` is `{}`.

5. **DSPy returns empty/None feedback**
   - Given DSPy runs but returns no usable `feedback_md`
   - When feedback is requested
   - Then we raise `FeedbackTransientError`.

### Visual feedback (Task.kind == "visual")
6. **Happy path**
   - Given `dspy` is importable and configured for a vision-capable model
   - And `AI_API_BASE_URL` is set
   - And the submission is image/png|image/jpeg|application/pdf
   - And criteria is non-empty
   - When the worker calls `FeedbackAdapter.analyze_visual(...)`
   - Then the system returns a valid `criteria.v2` analysis and non-empty `feedback_md`.

7. **Empty criteria (allowed)**
   - Given `criteria=[]`
   - When visual feedback is requested
   - Then we still return a non-empty `feedback_md` generated by DSPy
   - And `analysis_json` is `{}`.

8. **Any DSPy failure**
   - Given analysis or synthesis fails
   - When visual feedback is requested
   - Then raise `FeedbackTransientError`.

9. **Unsupported MIME**
   - Given a non-supported MIME type
   - When visual feedback is requested
   - Then raise `FeedbackPermanentError("unsupported_mime")`.

### Vision text extraction (“OCR” / handwriting) (Submission.kind=image|file)
10. **Happy path**
   - Given `dspy` is importable and configured for `AI_VISION_MODEL`
   - And `AI_API_BASE_URL` is set
   - And the submission is image/png|image/jpeg|application/pdf
   - When the worker calls `VisionAdapter.extract(...)`
   - Then the system returns `VisionResult` with non-empty `text_md` (Markdown)
   - And the adapter does not call `ollama.Client.*` anywhere.

11. **DSPy missing**
   - Given importing `dspy` fails
   - When Vision extraction is requested
   - Then we log `dspy_unavailable`
   - And raise `VisionTransientError`.

12. **Config missing**
   - Given `dspy` is importable but `AI_API_BASE_URL` or `AI_VISION_MODEL` is missing/empty
   - When Vision extraction is requested
   - Then we log `missing_endpoint` / `missing_model`
   - And raise `VisionTransientError`.

13. **Unsupported MIME**
   - Given a non-supported MIME type
   - When Vision extraction is requested
   - Then raise `VisionPermanentError("unsupported_mime")`.

14. **DSPy returns empty/None OCR text**
   - Given DSPy runs but returns no usable Markdown text
   - When Vision extraction is requested
   - Then raise `VisionTransientError`.

## Test Plan (TDD: Red → Green → Refactor)
### Step 1: Update tests to encode the new contract (RED)
Key changes (expected):

- Remove/update tests that require direct Ollama calls:
  - Feedback:
    - `backend/tests/learning_adapters/test_local_feedback_degrade_fallback.py`
    - `backend/tests/learning_adapters/test_ollama_raw_mode.py`
    - `backend/tests/learning_adapters/test_local_adapters_ollama_client_signature.py` (feedback portion)
  - Vision/OCR:
    - Replace tests that pin `_call_model(...)` behavior (Ollama SDK signature, images param) with DSPy-based tests that assert:
      - no `ollama` import/call is performed
      - `dspy.Predict(VisionTextExtractionSignature)` is invoked

- Replace Ollama-specific env validation tests with endpoint-based tests:
  - Update `backend/tests/test_learning_ai_config_ollama_validation.py` to validate `AI_API_BASE_URL`.

- Update host propagation tests:
  - Replace `OLLAMA_HOST`/`OLLAMA_API_BASE` assertions with `api_base == AI_API_BASE_URL` assertions.

- Adapt tests to expect **errors instead of deterministic fallbacks**:
  - Feedback: expect `FeedbackTransientError` for missing config/dspy/empty feedback.
  - Vision: expect `VisionTransientError` for missing config/dspy/empty OCR text.

### Step 2: Minimal implementation to make tests pass (GREEN)
- Introduce a shared DSPy LM configuration helper (single endpoint, different model names):
  - Use `AI_API_BASE_URL` for `api_base` for all calls.
  - Use `AI_API_KEY` if present (or a safe placeholder if required by the client library).
  - Ensure the same endpoint is used for feedback + visual feedback + vision extraction.
- Implement `VisionTextExtractionSignature` + `run_structured_vision_text_extraction(...)`.
- Refactor `backend/learning/adapters/local_vision.py` to call DSPy programs only (no direct Ollama SDK).
- Keep existing PDF→PNG stitching logic unchanged; only replace the “call model” step.

### Step 3: Refactor for clarity (REFACTOR)
- Reduce branching and duplicate error mapping.
- Ensure docstrings explain “why” and permissions clearly.
- Ensure logs do not include student text or image bytes (privacy).

## Verification
Suggested commands (local = prod):
- `.venv/bin/pytest -q`
- Optional focus while iterating:
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_dspy.py`
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_visual_feedback_program_dspy_structured.py`
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_vision.py`

## Documentation updates
- Update `docs/references/LLM-Prompts.md`:
  - Feedback and vision extraction use only DSPy Signatures/Modules (single prompt contract).
  - Visual tasks use the visual DSPy pipeline (image/PDF → analysis → feedback).
- Update `docs/references/learning_ai.md`:
  - Replace Ollama-specific wording with OpenAI-compatible endpoint + model variables.
  - Document privacy expectations for operators (where the endpoint runs, what data is sent).

## Risks
- Without deterministic fallbacks, a misconfigured endpoint/model will cause retries and eventually failed submissions.
- Strict validation may expose weaknesses in model adherence to the output contracts.
- Allowing an arbitrary endpoint is an operator decision with privacy implications.

Mitigations:
- Strong observability (structured logs: reason codes only, no content).
- Clear operator runbooks: required env vars, how to smoke-test the endpoint and models.
