# Plan: Simplify learning feedback to DSPy-only pipeline

## Context
- Current feedback implementation in `backend/learning/adapters` uses a hybrid approach:
  - DSPy Signatures (`FeedbackAnalysisSignature`, `FeedbackSynthesisSignature`) and helpers in `backend/learning/adapters/dspy/`.
  - Legacy prompt-building and direct Ollama calls in `backend/learning/adapters/dspy/feedback_program.py` and `backend/learning/adapters/local_feedback.py`.
- This hybrid increases complexity (two code paths, two prompt contracts) and makes it harder to teach/understand the architecture for students and teachers.
- You expressed the explicit goal: future feedback should use **DSPy only**, with a clean, simple architecture and no legacy fallback.

## User Story
**As** Felix (Product Owner, teacher)\
**I want** the learning feedback pipeline to rely exclusively on DSPy Signatures and Modules\
**So that** the architecture stays simple, testable, and easy to explain to students, and we can later plug in DSPy Optimizers without extra refactoring.

## Scope
- Feedback for learning submissions (criteria-based analysis + textual feedback) in the `learning` bounded context.
- Backends:
  - `backend/learning/adapters/dspy/feedback_program.py`
  - `backend/learning/adapters/dspy/programs.py`
  - `backend/learning/adapters/dspy/signatures.py`
  - `backend/learning/adapters/local_feedback.py` (only where it touches the DSPy path)
- Make DSPy the **single source of truth** for:
  - Input/Output contracts (Signatures, typed data classes).
  - Prompt construction and LM orchestration (via DSPy Modules + LM configuration).
  - Extensibility (DSPy Optimizers for examples/parameters).

## Out of Scope
- Changes to vision/OCR prompts or pipelines (`local_vision.py` etc.).
- Changes to teaching UI or learning UI (cards, dashboards).
- Changes to storage/upload mechanics or file-processing.
- Switching away from Ollama as the underlying LM host (we keep the same models, just the orchestration moves into DSPy).

## Assumptions
- DSPy will be available in the production environment (importable without optional stubs).
- Ollama/LiteLLM integration can be configured via DSPy’s LM abstraction, reusing existing environment variables (`OLLAMA_BASE_URL`, `AI_FEEDBACK_MODEL`, timeouts).
- The existing `criteria.v2` schema and feedback Markdown format remain valid and should not be changed as part of this plan.
- Tests already cover the observable behavior of the feedback pipeline (analysis JSON + feedback_md) and will be extended rather than rewritten from scratch.

## Risks & Mitigations
- **Risk:** Removing legacy fallback paths could hide useful defensive behavior (e.g. default feedback if DSPy fails).
  - **Mitigation:** Keep deterministic, non-LM fallback logic *inside* the DSPy-based path (e.g. if `feedback_md` missing, synthesize a minimal feedback from `CriteriaAnalysis`), and ensure tests cover all error modes.
- **Risk:** DSPy configuration errors (LM setup, signatures) break the pipeline.
  - **Mitigation:** Centralize LM configuration in one place (e.g. a `get_feedback_lm()` helper) and add targeted tests for import/config errors.
- **Risk:** Increased coupling between adapters and DSPy internals.
  - **Mitigation:** Keep a thin port-style abstraction: `local_feedback` calls a single function (or Module) that returns `FeedbackResult` without knowing about DSPy details.
- **Risk:** Complexity for students reading DSPy code.
  - **Mitigation:** Follow KISS: small DSPy Modules, clear docstrings, use descriptive field names and avoid meta-magic; document the pipeline in `docs/references/LLM-Prompts.md`.

## BDD Scenarios (Given-When-Then)
1. **Happy path: DSPy-only analysis and feedback**
   - Given a valid learner submission with text and a list of criteria
   - And DSPy and the configured LM are available
   - When the learning backend generates feedback for the submission
   - Then the system uses DSPy Signatures and Modules (no legacy prompt builder) to produce a `criteria.v2` analysis and `feedback_md`
   - And the HTTP API response matches the existing contract (schema, fields, value ranges).

2. **DSPy-only path on missing legacy environment flags**
   - Given a valid learner submission and criteria
   - And DSPy is importable
   - And no legacy feature flags or environment variables for the old prompt path are set
   - When feedback is requested
   - Then the backend still uses the DSPy pipeline exclusively
   - And does not attempt to call the legacy `_lm_call` or `_build_*_prompt` helpers.

3. **LM configuration error with deterministic fallback**
   - Given DSPy is importable
   - But the LM configuration is invalid (e.g. `OLLAMA_BASE_URL` missing)
   - When feedback is requested
   - Then the DSPy pipeline fails fast at configuration level
   - And returns a deterministic, non-LM fallback `FeedbackResult` (default analysis + default feedback_md)
   - And the HTTP API responds with a safe, documented error or fallback body (no unhandled exceptions).

4. **Partial LM failure during analysis**
   - Given a valid learner submission and criteria
   - And the DSPy analysis step raises an exception (e.g. timeout)
   - When feedback is requested
   - Then the system does not call any legacy prompt path
   - And it returns a deterministic `criteria.v2` default analysis
   - And a minimal but pedagogically safe feedback text is generated without LM calls.

5. **Partial LM failure during feedback synthesis**
   - Given a valid learner submission and criteria
   - And the DSPy analysis step completes successfully and returns structured `CriteriaAnalysis`
   - And the DSPy feedback synthesis step fails (e.g. timeout or invalid output)
   - When feedback is requested
   - Then the system keeps the existing analysis JSON
   - And synthesizes a minimal textual feedback from the `CriteriaAnalysis` object (e.g. “Stärken/Hinweise”) without using any legacy prompt builders.

6. **No-DSPy environment is unsupported (hard failure)**
   - Given DSPy is not importable in the runtime environment
   - When feedback is requested
   - Then the backend fails with a clear, logged error that DSPy is required
   - And no hidden legacy path is used as a fallback
   - And tests document this behavior as unsupported configuration.

## Tasks
1. **Clarify and document DSPy contracts**
   - Review and, if needed, refine `FeedbackAnalysisSignature` and `FeedbackSynthesisSignature` to match the current `criteria.v2` analysis JSON and the desired `feedback_md`.
   - Update `docs/references/LLM-Prompts.md` to reflect that DSPy Signatures and Modules are now the primary contract for learning feedback (not legacy prompt builders).

2. **Introduce clear DSPy Modules for feedback**
   - Implement small, focused DSPy Modules in `backend/learning/adapters/dspy/programs.py` with the following interfaces (Variant B mit Sub-Modulen):
     - `CriteriaAnalysisModule(dspy.Module)`:
       - **forward-Inputs:** `student_text_md: str`, `criteria: list[str]`, `teacher_instructions_md: str | None`, `solution_hints_md: str | None`.
       - **Output:** `CriteriaAnalysis` (inkl. `schema="criteria.v2"`, `score`, `criteria_results`).
     - `FeedbackSynthesisModule(dspy.Module)`:
       - **forward-Inputs:** `student_text_md: str`, `analysis: CriteriaAnalysis`, `teacher_instructions_md: str | None`.
       - **Output:** `feedback_md: str` (Markdown-Fließtext).
     - `FeedbackPipelineModule(dspy.Module)`:
       - Intern hält das Modul zwei Sub-Module: `analysis_module: CriteriaAnalysisModule` und `synthesis_module: FeedbackSynthesisModule`.
       - **forward-Inputs:** `student_text_md: str`, `criteria: list[str]`, `teacher_instructions_md: str | None`, `solution_hints_md: str | None`.
       - **Output:** ein einfaches DTO, z.B. `FeedbackResultDTO`, mit Feldern `analysis: CriteriaAnalysis` und `feedback_md: str`.
   - Ensure these Modules encapsulate LM configuration (e.g. via a helper to construct DSPy’s LM with `OLLAMA_BASE_URL` and `AI_FEEDBACK_MODEL`) and keep business-facing types (`CriteriaAnalysis`, `FeedbackResultDTO`) frei von DSPy-spezifischen Details.

3. **Refactor feedback_program to use DSPy exclusively**
   - In `backend/learning/adapters/dspy/feedback_program.py`, remove or isolate legacy functions (`_build_analysis_prompt`, `_build_feedback_prompt`, `_lm_call`, `_run_*_model`).
   - Replace the current hybrid pipeline with one clear path:
     - Call DSPy Modules for analysis and synthesis.
     - Handle exceptions and fallbacks (default `CriteriaAnalysis`, default feedback text) *inside* this DSPy-oriented code.
   - Ensure that only one entrypoint (e.g. `run_feedback_pipeline(...)`) is used by `local_feedback` to obtain a `FeedbackResult`.

4. **Align local_feedback adapter with DSPy-only design**
   - Update `backend/learning/adapters/local_feedback.py` to:
     - Call only the DSPy-based `run_feedback_pipeline(...)` (or equivalent).
     - Remove any direct references to legacy prompt builders or Ollama client usage that bypasses DSPy.
   - Keep the adapter responsible only for:
     - Collecting inputs (student text, criteria, context).
     - Calling the DSPy-based pipeline.
     - Mapping the result to the public `FeedbackResult`.

5. **Strengthen tests for the DSPy-only pipeline**
   - Extend or add pytest cases to cover all BDD scenarios above:
     - Happy path DSPy-only.
     - LM config errors.
     - Analysis failure → deterministic fallback.
     - Feedback synthesis failure → deterministic feedback from analysis.
     - Missing DSPy import → explicit unsupported configuration.
   - Remove or adjust tests that expect legacy prompt-builder behavior or direct `_lm_call` usage.

6. **Prepare for future DSPy Optimizers**
   - Introduce a minimal abstraction for “trainable” DSPy Modules (e.g. a function that returns a configured Module instance).
   - Sketch (but not yet implement) how DSPy Optimizers (e.g. few-shot bootstrapping) could be attached later without changing the public feedback API.
   - Document this in the code (docstrings) and, if needed, append a short section to `docs/references/LLM-Prompts.md`.

## Test Plan
- Run focused tests for learning feedback:
  - `.venv/bin/pytest -q backend/tests/learning/test_feedback_dspy.py`
  - `.venv/bin/pytest -q backend/tests/learning/test_feedback_adapter.py`
- Add or adjust tests as needed to cover:
  - DSPy-only happy path (analysis + feedback).
  - LM configuration errors and deterministic fallbacks.
  - Failure modes for analysis and feedback synthesis.
- Once green, run the broader learning test suite to detect regressions:
  - `.venv/bin/pytest -q backend/tests/learning`
