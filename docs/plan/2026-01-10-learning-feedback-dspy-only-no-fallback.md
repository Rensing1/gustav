# Plan: Learning Feedback – DSPy-only (no prompt builders, no Ollama fallback)

## Context
The current learning feedback implementation is a hybrid:

- **DSPy structured path** (Signatures + Predict) for analysis + feedback text.
- **Legacy + fallback paths**:
  - Prompt-builder templates in `backend/learning/adapters/dspy/feedback_program.py` (`_build_*_prompt`, sizing helpers).
  - Direct `ollama` client calls and “degrade-to-ollama” logic in `backend/learning/adapters/local_feedback.py`.
  - Deterministic fallback outputs (default analysis/feedback strings) in both text and visual DSPy pipelines.

This hybrid violates our current design goals (KISS/DRY, “one source of truth”) and makes the system harder to reason about for learners and maintainers.

There is an older plan, `docs/plan/2025-11-18-dspy-only-feedback-pipeline.md`, which still allowed deterministic fallbacks. This document supersedes it with stricter “fail fast + retry” semantics and extends the scope to **visual** DSPy feedback as well.

## Decisions (agreed 2026-01-10)
1. **DSPy-only orchestration** for learning feedback:
   - No prompt-builder templates as a second prompt contract.
   - No direct `ollama` fallback calls from the feedback adapter.
2. **No deterministic fallback outputs**:
   - If analysis or synthesis cannot be produced, we raise an error (do not fabricate default analysis or default feedback text).
3. **DSPy and config are required**:
   - If `dspy` is missing or config is incomplete → log error and raise (worker will retry).
4. **Empty criteria is allowed**:
   - If a teacher provides no rubric criteria, feedback generation is still legitimate.
   - The criteria-based scoring step is skipped and `analysis_json` is `{}`.
5. **No additional input clipping in the feedback pipeline**:
   - Input sizes are validated upstream (e.g. text body limit), and the DSPy pipeline does not truncate on its own.

## User Story
**As** a product owner and teacher\
**I want** learning feedback to be generated exclusively via DSPy\
**So that** there is exactly one prompt/contract source (DSPy Signatures/Modules), the code stays teachable, and failures are handled consistently via retries instead of hidden fallbacks.

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
- Test suite updates to reflect the new semantics.
- Documentation alignment:
  - `docs/references/LLM-Prompts.md`

### Out of scope
- API contract changes (`api/openapi.yml`) – no endpoint behavior changes intended.
- Database schema changes/migrations.
- Vision/OCR extraction pipeline changes (`backend/learning/adapters/local_vision.py`), except where required for visual feedback I/O (PDF → PNG stitching is already used by `analyze_visual`).

## Target Behavior (error semantics)
### High-level rule
**Any failure to produce valid DSPy outputs is an error and should trigger worker retries.**

### Error classification in the worker
The worker distinguishes:
- `FeedbackTransientError` → retry with backoff until MAX_RETRIES, then mark `feedback_failed`.
- `FeedbackPermanentError` → mark failed immediately (no retry).

For this refactor we want the following mapping:
- Missing `dspy` import → **transient** (environment must be fixed; worker retries until it fails).
- Missing config (e.g. model/base URL env) → **transient**.
- DSPy runtime errors (timeouts, network/model errors, invalid output) → **transient**.
- Unsupported MIME in visual feedback (not image/png/jpeg/pdf) → **permanent** (input is not processable).

## BDD Scenarios (Given–When–Then)
### Text feedback (Task.kind != "visual")
1. **Happy path**
   - Given `dspy` is importable and configured
   - And criteria is non-empty
   - When the worker calls `FeedbackAdapter.analyze(...)`
   - Then the system returns `FeedbackResult` with:
     - `analysis_json.schema == "criteria.v2"`
     - non-empty `feedback_md`
   - And no direct `ollama.Client.generate(...)` is called anywhere in the feedback adapter path.

2. **DSPy missing**
   - Given importing `dspy` fails
   - When feedback is requested
   - Then we log a clear error reason (e.g. `dspy_unavailable`)
   - And raise `FeedbackTransientError` (worker retries until it fails).

3. **Config missing**
   - Given `dspy` is importable but required env config is missing/empty
   - When feedback is requested
   - Then we log `missing_model` / `missing_base_url`
   - And raise `FeedbackTransientError`.

4. **Empty criteria (allowed)**
   - Given `criteria=[]`
   - When feedback is requested
   - Then we still return a non-empty `feedback_md` generated by DSPy
   - And `analysis_json` is `{}` (no rubric scoring possible).

5. **DSPy returns empty/None feedback**
   - Given DSPy runs but returns no usable `feedback_md`
   - When feedback is requested
   - Then we raise `FeedbackTransientError` (no synthetic feedback).

### Visual feedback (Task.kind == "visual")
6. **Happy path**
   - Given `dspy` is importable and configured for a vision-capable model
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
   - Then raise `FeedbackTransientError` (no default analysis/feedback).

9. **Unsupported MIME**
   - Given a non-supported MIME type
   - When visual feedback is requested
   - Then raise `FeedbackPermanentError("unsupported_mime")`.

## Test Plan (TDD: Red → Green → Refactor)
### Step 1: Update tests to encode the new contract (RED)
Key changes (expected):

- Remove tests that require Ollama fallback:
  - `backend/tests/learning_adapters/test_local_feedback_degrade_fallback.py`
  - `backend/tests/learning_adapters/test_ollama_raw_mode.py`
  - `backend/tests/learning_adapters/test_local_adapters_ollama_client_signature.py` (feedback part only; vision part stays)
- Remove tests that require prompt-builder templates / sizing:
  - `backend/tests/learning_adapters/test_dspy_prompt_sizing.py`
- Adapt tests to expect **errors instead of deterministic fallbacks**:
  - `backend/tests/learning_adapters/test_local_feedback.py` (stop mocking `ollama`; mock DSPy path)
  - `backend/tests/learning_adapters/test_local_feedback_dspy.py`
  - `backend/tests/learning_adapters/test_feedback_program_dspy.py`
  - `backend/tests/learning_adapters/test_feedback_program_dspy_prompt.py`
  - `backend/tests/learning_adapters/test_feedback_program_dspy_structured.py`
  - `backend/tests/learning_adapters/test_visual_feedback_program_dspy_structured.py`

New/updated assertions should encode:
- no direct ollama usage
- errors on:
  - missing dspy
  - missing config
  - empty feedback
  - invalid analysis structure
 - empty criteria produces DSPy feedback and `analysis_json={}`

### Step 2: Minimal implementation to make tests pass (GREEN)
- Refactor `backend/learning/adapters/local_feedback.py` to:
  - require DSPy + required env config
  - raise `FeedbackTransientError` for the error cases above
  - remove the direct Ollama fallback and degrade logic
- Refactor `backend/learning/adapters/dspy/feedback_program.py` to:
  - remove prompt builders and legacy runner hooks
  - use only `dspy_programs.run_structured_analysis` and `dspy_programs.run_structured_feedback`
  - validate outputs strictly and raise on invalid/empty results
  - handle `criteria=[]` as a dedicated DSPy feedback path that skips rubric analysis and returns `analysis_json={}`
- Refactor `backend/learning/adapters/dspy/programs.py` to:
  - remove deterministic “synthesize feedback if missing” branches (raise instead)
- Refactor `backend/learning/adapters/dspy/visual_feedback_program.py` to:
  - remove default analysis/feedback fallbacks and “skipped” behavior
  - propagate errors (mapped to transient by the adapter)
  - handle `criteria=[]` as a dedicated DSPy feedback path that skips rubric analysis and returns `analysis_json={}`

### Step 3: Refactor for clarity (REFACTOR)
- Reduce branching and duplicate error mapping.
- Ensure docstrings explain “why” and permissions clearly.
- Ensure logs do not include student text (privacy).

## Verification
Suggested commands (local = prod):
- `.venv/bin/pytest -q`
- Optional focus while iterating:
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_dspy.py`
  - `.venv/bin/pytest -q backend/tests/learning_adapters/test_visual_feedback_program_dspy_structured.py`

## Documentation updates
- Update `docs/references/LLM-Prompts.md` to reflect:
  - Visual tasks use the **visual DSPy pipeline** (image/PDF → analysis → feedback), not OCR-text.
  - Text feedback is DSPy-only (no direct Ollama fallback).
  - Prompt-builder templates are removed (Signatures/Modules are the contract).

## Risks
- Without deterministic fallbacks, a misconfigured environment or flaky LM will cause retries and eventually failed submissions.
- Strict validation may expose weaknesses in model adherence to `criteria.v2`.

Mitigations:
- Strong observability (structured logs: reason codes).
- Clear operator runbooks: which env vars must be set; how to confirm `dspy` is installed.
